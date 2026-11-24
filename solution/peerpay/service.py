"""The PeerPay use cases (DESIGN.md §3–§5, §9–§12).

Each use case runs in one UnitOfWork, so it is either completely done or not done at all, and
money only ever moves by appending ledger entries. Slow work (the bank) happens outside the
transaction, and events are published only after the commit, so nobody is ever notified about
a change that was rolled back.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .bank import BankAdapter
from .commands import SendTransfer, TopUp
from .errors import (
    InsufficientFunds, NotAllowed, NothingToCancel, TransferExpired, TransferNotFound,
    UnknownRecipient
)
from .events import EventBus
from .models import Status, Transfer
from .money import ZERO, Money
from .repository import DbPath, UnitOfWork
from .values import PhoneNumber

type Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class PendingItem:
    transfer: Transfer
    sender_name: str


@dataclass(frozen=True, slots=True)
class Statement:
    received_count: int
    received_total: Money
    sent_count: int
    sent_total: Money
    lines: list[str]


class WalletService:
    """The use cases. Each method opens its own unit of work, so the service holds no state."""

    def __init__(self, db_path: DbPath, bank: BankAdapter, clock: Clock, bus: EventBus) -> None:
        self.db_path = db_path
        self.bank = bank
        self.clock = clock
        self.bus = bus

    def uow(self) -> UnitOfWork:
        return UnitOfWork(self.db_path)

    def balance(self, user_id: int) -> Money:
        with self.uow() as uow:
            return uow.ledger.balance(user_id)

    def top_up(self, cmd: TopUp) -> None:
        """Pulls the money from the user's bank, then records what the bank actually pulled."""

        with self.uow() as uow:
            user = uow.users.get(cmd.user_id)

        pulled = self.bank.pull(user.bank_account, cmd.amount)

        with self.uow() as uow:
            uow.ledger.add(cmd.user_id, pulled, kind="deposit", created_at=self.clock())

    def send(self, cmd: SendTransfer) -> Transfer:
        """Debits the sender and creates a PENDING transfer, atomically (DESIGN.md §4)."""

        now = self.clock()

        with self.uow() as uow:
            recipient = uow.users.by_phone(cmd.recipient)

            if recipient is None:
                raise UnknownRecipient(str(cmd.recipient))

            if recipient.id == cmd.sender_id:
                raise NotAllowed("you cannot send money to yourself")

            if uow.ledger.balance(cmd.sender_id) < cmd.amount:
                raise InsufficientFunds()

            transfer = uow.transfers.add(
                cmd.sender_id, recipient.id, cmd.amount,
                note=str(cmd.note), created_at=now
            )
            uow.ledger.add(
                cmd.sender_id, -cmd.amount,
                kind="transfer_out", created_at=now, transfer_id=transfer.id
            )

        self.bus.publish("sent", transfer)

        return transfer

    def pending(self, user_id: int) -> list[PendingItem]:
        """The user's incoming pending transfers, each with the sender's name."""

        with self.uow() as uow:
            return [
                PendingItem(transfer, uow.users.get(transfer.sender_id).name)
                for transfer in uow.transfers.pending_to(user_id)
            ]

    def accept(self, user_id: int, transfer_id: int) -> None:
        now = self.clock()

        with self.uow() as uow:
            transfer = self._pending_to(uow, user_id, transfer_id)

            if transfer.is_expired(now):
                raise TransferExpired(transfer_id)

            transfer = transfer.moved_to(Status.ACCEPTED, now)
            uow.transfers.save_status(transfer)
            uow.ledger.add(
                user_id, transfer.amount,
                kind="transfer_in", created_at=now, transfer_id=transfer.id
            )

        self.bus.publish("accepted", transfer)

    def decline(self, user_id: int, transfer_id: int) -> None:
        with self.uow() as uow:
            transfer = self._pending_to(uow, user_id, transfer_id)
            transfer = self._refund(uow, transfer, Status.DECLINED)

        self.bus.publish("declined", transfer)

    def cancel_last(self, sender_id: int) -> Transfer:
        with self.uow() as uow:
            transfer = uow.transfers.last_pending_of(sender_id)

            if transfer is None:
                raise NothingToCancel()

            transfer = self._refund(uow, transfer, Status.CANCELLED)

        self.bus.publish("cancelled", transfer)

        return transfer

    def expire_pending(self) -> int:
        """The nightly job: refunds every transfer that was not accepted in time.

        Returns how many transfers expired.
        """

        now = self.clock()
        expired: list[Transfer] = []

        with self.uow() as uow:
            for transfer in uow.transfers.pending():
                if transfer.is_expired(now):
                    expired.append(self._refund(uow, transfer, Status.EXPIRED))

        for transfer in expired:
            self.bus.publish("expired", transfer)

        return len(expired)

    def adjust(self, phone: PhoneNumber, amount: Money, *, reason: str) -> None:
        """A manual correction by the support team: a ledger entry like any other (bug S4)."""

        with self.uow() as uow:
            user = uow.users.by_phone(phone)

            if user is None:
                raise UnknownRecipient(str(phone))

            uow.ledger.add(
                user.id, amount, kind="adjustment", created_at=self.clock(), note=reason
            )

    def statement(self, user_id: int) -> Statement:
        with self.uow() as uow:
            received = uow.transfers.accepted_to(user_id)
            sent = uow.transfers.accepted_from(user_id)
            lines = []

            for transfer in uow.transfers.of(user_id):
                other = uow.users.get(transfer.other_party(user_id))
                direction = "from" if transfer.recipient_id == user_id else "to"
                lines.append(
                    f"#{transfer.id} {transfer.status:<9} {str(transfer.amount):>10}"
                    f"  {direction} {other.name} ({other.phone.masked()})"
                )

        return Statement(
            received_count=len(received),
            received_total=sum((t.amount for t in received), ZERO),
            sent_count=len(sent),
            sent_total=sum((t.amount for t in sent), ZERO),
            lines=lines
        )

    @staticmethod
    def _pending_to(uow: UnitOfWork, user_id: int, transfer_id: int) -> Transfer:
        transfer = uow.transfers.get(transfer_id)

        if (
            transfer is None
            or transfer.recipient_id != user_id
            or transfer.status != Status.PENDING
        ):
            raise TransferNotFound(transfer_id)

        return transfer

    def _refund(self, uow: UnitOfWork, transfer: Transfer, status: Status) -> Transfer:
        """Settles ``transfer`` with ``status`` and gives the money back to the sender."""

        now = self.clock()
        transfer = transfer.moved_to(status, now)
        uow.transfers.save_status(transfer)
        uow.ledger.add(
            transfer.sender_id, transfer.amount,
            kind="refund", created_at=now, transfer_id=transfer.id
        )

        return transfer

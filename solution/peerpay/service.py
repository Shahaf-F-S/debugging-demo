"""The PeerPay use cases (DESIGN.md §3, §4, §7, §8).

Each use case runs in one UnitOfWork, so it is either completely done or not done at all (bug C4).
Slow work (the bank) happens outside the transaction, and notifications are sent only after the
commit, so nobody is ever told about a change that was rolled back.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .bank import BankAdapter
from .errors import (
    InsufficientFunds, NotAllowed, TransferExpired, TransferNotFound, UnknownRecipient
)
from .models import Status, Transfer
from .money import Money
from .notifier import Notifier
from .repository import DbPath, UnitOfWork
from .validation import SendRequest

type Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class PendingItem:
    transfer: Transfer
    sender_name: str
    sender_phone: str                           # masked, for display


class WalletService:
    """The use cases. Each method opens its own unit of work, so the service holds no state."""

    def __init__(
        self,
        db_path: DbPath,
        bank: BankAdapter,
        clock: Clock,
        notifier: Notifier
    ) -> None:
        self.db_path = db_path
        self.bank = bank
        self.clock = clock
        self.notifier = notifier

    def uow(self) -> UnitOfWork:
        return UnitOfWork(self.db_path)

    def balance(self, user_id: int) -> Money:
        with self.uow() as uow:
            return uow.accounts.balance(user_id)

    def top_up(self, user_id: int, amount: Money) -> None:
        """Pulls the money from the user's bank, then credits what the bank actually pulled."""

        with self.uow() as uow:
            user = uow.users.get(user_id)

        pulled = self.bank.pull(user.bank_account, amount)

        with self.uow() as uow:
            uow.accounts.credit(user_id, pulled)

    def send(self, sender_id: int, request: SendRequest) -> Transfer:
        """Debits the sender and creates a PENDING transfer, atomically (DESIGN.md §3)."""

        with self.uow() as uow:
            recipient = uow.users.by_phone(request.recipient)

            if recipient is None:
                raise UnknownRecipient(str(request.recipient))

            if recipient.id == sender_id:
                raise NotAllowed("you cannot send money to yourself")

            if not uow.accounts.debit(sender_id, request.amount):
                raise InsufficientFunds()

            transfer = uow.transfers.add(
                sender_id, recipient.id, request.amount,
                note=str(request.note), created_at=self.clock()
            )

        self.notifier.push(
            recipient.id,
            f"You received {transfer.amount} (transfer #{transfer.id}). Accept it within 30 days."
        )

        return transfer

    def pending(self, user_id: int) -> list[PendingItem]:
        """The user's incoming pending transfers, with each sender's name and masked phone."""

        with self.uow() as uow:
            items = []

            for transfer in uow.transfers.pending_to(user_id):
                sender = uow.users.get(transfer.sender_id)
                items.append(PendingItem(transfer, sender.name, sender.phone.masked()))

        return items

    def accept(self, user_id: int, transfer_id: int) -> None:
        now = self.clock()

        with self.uow() as uow:
            transfer = uow.transfers.get(transfer_id)

            if (
                transfer is None
                or transfer.recipient_id != user_id
                or transfer.status is not Status.PENDING
            ):
                raise TransferNotFound(transfer_id)

            if transfer.is_expired(now):
                raise TransferExpired(transfer_id)

            transfer = transfer.settled(Status.ACCEPTED, now)
            uow.transfers.save_status(transfer)
            uow.accounts.credit(user_id, transfer.amount)

        self.notifier.push(
            transfer.sender_id,
            f"Your transfer #{transfer.id} of {transfer.amount} was accepted."
        )

    def expire_pending(self) -> int:
        """The nightly job: refunds every transfer that was not accepted in time.

        Returns how many transfers expired.
        """

        now = self.clock()
        expired: list[Transfer] = []

        with self.uow() as uow:
            for transfer in uow.transfers.pending():
                if transfer.is_expired(now):
                    transfer = transfer.settled(Status.EXPIRED, now)
                    uow.transfers.save_status(transfer)
                    uow.accounts.credit(transfer.sender_id, transfer.amount)
                    expired.append(transfer)

        for transfer in expired:
            self.notifier.push(
                transfer.sender_id,
                f"Your transfer #{transfer.id} of {transfer.amount} expired."
                " The money is back in your wallet."
            )

        return len(expired)

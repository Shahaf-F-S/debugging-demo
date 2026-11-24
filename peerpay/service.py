"""PeerPay use cases (DESIGN.md §3–§5, §9–§12). Amounts are Money.

Every use case runs in one UnitOfWork: it is completely done, or not done at all.
Events are published only after the unit of work has committed.
"""
from collections.abc import Callable
from datetime import datetime

from .commands import SendTransfer, TopUp
from .errors import InsufficientFunds, NotAllowed, NothingToCancel, TransferExpired, TransferNotFound, UnknownRecipient
from .models import Status, Transfer
from .money import ZERO, Money
from .repository import UnitOfWork
from .values import PhoneNumber

Clock = Callable[[], datetime]


class WalletService:
    def __init__(self, db_path, bank, clock: Clock, bus):
        self.db_path = db_path
        self.bank = bank
        self.clock = clock
        self.bus = bus

    def uow(self) -> UnitOfWork:
        return UnitOfWork(self.db_path)

    def balance(self, user_id) -> Money:
        with self.uow() as uow:
            return uow.repo.account(user_id).balance

    def top_up(self, cmd: TopUp) -> None:
        with self.uow() as uow:
            user = uow.users.get(cmd.user_id)
        pulled = self.bank.pull(user.bank_account, cmd.amount)       # outside the transaction: the bank is slow
        with self.uow() as uow:
            account = uow.repo.account(cmd.user_id)
            account.balance += pulled
            uow.repo.save_account(account)
            uow.repo.add_ledger(cmd.user_id, pulled, "deposit", self.clock())

    def send(self, cmd: SendTransfer) -> Transfer:
        with self.uow() as uow:
            recipient = uow.users.by_phone(cmd.recipient)
            if recipient is None:
                raise UnknownRecipient(cmd.recipient)
            if recipient.id == cmd.sender_id:
                raise NotAllowed("you cannot send money to yourself")
            sender = uow.repo.account(cmd.sender_id)
            if sender.balance < cmd.amount:
                raise InsufficientFunds()
            sender.balance -= cmd.amount
            uow.repo.save_account(sender)
            transfer = uow.repo.insert_transfer(cmd.sender_id, recipient.id, cmd.amount, str(cmd.note), self.clock())
            uow.repo.add_ledger(cmd.sender_id, -cmd.amount, "transfer_out", self.clock(), transfer.id)
        self.bus.publish("sent", transfer)
        return transfer

    def pending(self, user_id) -> list[tuple[Transfer, str]]:
        """The user's incoming pending transfers, each with the sender's name."""
        with self.uow() as uow:
            return [(t, uow.users.get(t.sender_id).name) for t in uow.repo.pending_to(user_id)]

    def accept(self, user_id, transfer_id) -> None:
        now = self.clock()
        with self.uow() as uow:
            transfer = self._pending_to(uow, user_id, transfer_id)
            if transfer.is_expired(now):
                raise TransferExpired(transfer_id)
            transfer = transfer.moved_to(Status.ACCEPTED, now)
            uow.repo.save_status(transfer)
            account = uow.repo.account(user_id)
            account.balance += transfer.amount
            uow.repo.save_account(account)
            uow.repo.add_ledger(user_id, transfer.amount, "transfer_in", now, transfer.id)
        self.bus.publish("accepted", transfer)

    def decline(self, user_id, transfer_id) -> None:
        with self.uow() as uow:
            transfer = self._refund(uow, self._pending_to(uow, user_id, transfer_id), Status.DECLINED)
        self.bus.publish("declined", transfer)

    def cancel_last(self, sender_id) -> Transfer:
        with self.uow() as uow:
            transfer = uow.repo.last_pending_of(sender_id)
            if transfer is None:
                raise NothingToCancel()
            transfer = self._refund(uow, transfer, Status.CANCELLED)
        self.bus.publish("cancelled", transfer)
        return transfer

    def expire_pending(self) -> int:
        """The nightly job: refund every transfer that was not accepted in time."""
        now = self.clock()
        with self.uow() as uow:
            expired = [self._refund(uow, t, Status.EXPIRED) for t in uow.repo.pending() if t.is_expired(now)]
        for transfer in expired:
            self.bus.publish("expired", transfer)
        return len(expired)

    def adjust(self, phone: PhoneNumber, amount: Money, reason) -> None:
        """A manual correction by the support team: a ledger entry like any other."""
        with self.uow() as uow:
            user = uow.users.by_phone(phone)
            if user is None:
                raise UnknownRecipient(phone)
            account = uow.repo.account(user.id)
            account.balance += amount
            uow.repo.save_account(account)
            uow.repo.add_ledger(user.id, amount, "adjustment", self.clock(), note=reason)

    def statement(self, user_id) -> dict:
        with self.uow() as uow:
            received = uow.repo.transfers_to(user_id)
            sent = uow.repo.transfers_from(user_id)
            lines = []
            for transfer in uow.repo.transfers_of(user_id):
                other = uow.users.get(transfer.other_party(user_id))
                direction = "from" if transfer.recipient_id == user_id else "to"
                lines.append(f"#{transfer.id} {transfer.status:<9} {str(transfer.amount):>10}"
                             f"  {direction} {other.name} ({other.phone.masked()})")
        return {
            "received_count": len(received),
            "received_total": sum((t.amount for t in received), ZERO),
            "sent_count": len(sent),
            "sent_total": sum((t.amount for t in sent), ZERO),
            "lines": lines,
        }

    @staticmethod
    def _pending_to(uow, user_id, transfer_id) -> Transfer:
        transfer = uow.repo.transfer(transfer_id)
        if transfer is None or transfer.recipient_id != user_id or transfer.status != Status.PENDING:
            raise TransferNotFound(transfer_id)
        return transfer

    def _refund(self, uow, transfer, status) -> Transfer:
        now = self.clock()
        transfer = transfer.moved_to(status, now)
        uow.repo.save_status(transfer)
        account = uow.repo.account(transfer.sender_id)
        account.balance += transfer.amount
        uow.repo.save_account(account)
        uow.repo.add_ledger(transfer.sender_id, transfer.amount, "refund", now, transfer.id)
        return transfer

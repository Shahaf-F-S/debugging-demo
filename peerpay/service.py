"""PeerPay use cases (DESIGN.md §3–§5, §9–§12). Amounts are Money."""
from datetime import timedelta

from .errors import (InsufficientFunds, NotAllowed, NothingToCancel, TransferExpired,
                     TransferNotFound, UnknownRecipient, ValidationError)
from .models import ACCEPTED, CANCELLED, DECLINED, EXPIRED, PENDING
from .money import ZERO, Money
from .repository import Repository, UserDirectory
from .validation import mask_phone, validate_send

EXPIRY = timedelta(days=30)


class WalletService:
    def __init__(self, conn, bank, clock, bus):
        self.conn = conn
        self.bank = bank
        self.clock = clock
        self.bus = bus
        self.users = UserDirectory(conn)
        self.repo = Repository(conn)

    def balance(self, user_id) -> Money:
        return self.repo.account(user_id).balance

    def top_up(self, user_id, amount: Money):
        if not amount.is_positive():
            raise ValidationError(["amount must be positive"])
        user = self.users.get(user_id)
        amount = self.bank.pull(user.bank_account, amount)
        with self.conn:
            account = self.repo.account(user_id)
            account.balance += amount
            self.repo.save_account(account)
            self.repo.add_ledger(user_id, amount, "deposit", self.clock())

    def send(self, sender_id, phone, amount: Money, note=""):
        errors = validate_send(amount, phone, note)
        if errors:
            raise ValidationError(errors)
        recipient = self.users.by_phone(phone)
        if recipient is None:
            raise UnknownRecipient(phone)
        if recipient.id == sender_id:
            raise NotAllowed("you cannot send money to yourself")
        with self.conn:
            sender = self.repo.account(sender_id)
            if sender.balance < amount:
                raise InsufficientFunds()
            sender.balance -= amount
            self.repo.save_account(sender)
            transfer = self.repo.insert_transfer(sender_id, recipient.id, amount, note, self.clock())
            self.repo.add_ledger(sender_id, -amount, "transfer_out", self.clock(), transfer.id)
        self.bus.publish("sent", transfer)
        return transfer

    def pending(self, user_id):
        return self.repo.pending_to(user_id)

    def accept(self, user_id, transfer_id):
        transfer = self._pending_to(user_id, transfer_id)
        if self.clock() - transfer.created_at >= EXPIRY:
            raise TransferExpired(transfer_id)
        with self.conn:
            self.repo.set_status(transfer.id, ACCEPTED, self.clock())
            account = self.repo.account(user_id)
            account.balance += transfer.amount
            self.repo.save_account(account)
            self.repo.add_ledger(user_id, transfer.amount, "transfer_in", self.clock(), transfer.id)
        self.bus.publish("accepted", transfer)

    def decline(self, user_id, transfer_id):
        self._refund(self._pending_to(user_id, transfer_id), DECLINED)

    def cancel_last(self, sender_id):
        transfer = self.repo.last_pending_of(sender_id)
        if transfer is None:
            raise NothingToCancel()
        self._refund(transfer, CANCELLED)
        return transfer

    def expire_pending(self) -> int:
        """The nightly job: refund every transfer that was not accepted in time."""
        expired = self.repo.pending_created_before(self.clock() - EXPIRY)
        for transfer in expired:
            self._refund(transfer, EXPIRED)
        return len(expired)

    def adjust(self, user_id, amount: Money, reason):
        """A manual correction by the support team: a ledger entry like any other."""
        with self.conn:
            account = self.repo.account(user_id)
            account.balance += amount
            self.repo.save_account(account)
            self.repo.add_ledger(user_id, amount, "adjustment", self.clock(), note=reason)

    def statement(self, user_id) -> dict:
        received = self.repo.transfers_to(user_id)
        sent = self.repo.transfers_from(user_id)
        lines = []
        for transfer in self.repo.transfers_of(user_id):
            other = self.users.get(transfer.other_party(user_id))
            direction = "from" if transfer.recipient_id == user_id else "to"
            lines.append(f"#{transfer.id} {transfer.status:<9} {str(transfer.amount):>10}"
                         f"  {direction} {other.name} ({mask_phone(other.phone)})")
        return {
            "received_count": len(received),
            "received_total": sum((t.amount for t in received), ZERO),
            "sent_count": len(sent),
            "sent_total": sum((t.amount for t in sent), ZERO),
            "lines": lines,
        }

    def _pending_to(self, user_id, transfer_id):
        transfer = self.repo.transfer(transfer_id)
        if transfer is None or transfer.recipient_id != user_id or transfer.status != PENDING:
            raise TransferNotFound(transfer_id)
        return transfer

    def _refund(self, transfer, status):
        with self.conn:
            self.repo.set_status(transfer.id, status, self.clock())
            account = self.repo.account(transfer.sender_id)
            account.balance += transfer.amount
            self.repo.save_account(account)
            self.repo.add_ledger(transfer.sender_id, transfer.amount, "refund", self.clock(), transfer.id)
        self.bus.publish(status.lower(), transfer)

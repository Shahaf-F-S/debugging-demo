"""PeerPay use cases (DESIGN.md §3, §4, §7, §8). Amounts are int agorot."""

from datetime import timedelta

from .bank_gateway import BankError
from .errors import (
    InsufficientFunds, NotAllowed, TopUpFailed, TransferExpired, TransferNotFound,
    UnknownRecipient, ValidationError
)
from .models import ACCEPTED, EXPIRED, PENDING
from .money import format_amount
from .repository import Repository, UserDirectory
from .validation import mask_phone, validate_send

EXPIRY = timedelta(days=30)


class WalletService:
    def __init__(self, conn, bank, clock, notifier):
        self.conn = conn
        self.bank = bank
        self.clock = clock
        self.notifier = notifier
        self.users = UserDirectory(conn)
        self.repo = Repository(conn)

    def balance(self, user_id):
        return self.repo.account(user_id).balance

    def top_up(self, user_id, amount):
        if amount <= 0:
            raise ValidationError(["amount must be positive"])

        user = self.users.get(user_id)

        try:
            self.bank.pull(user.bank_account, amount)

        except BankError as e:
            raise TopUpFailed(str(e)) from e

        account = self.repo.account(user_id)
        account.balance += amount
        self.repo.save_account(account)

    def send(self, sender_id, phone, amount, note=""):
        errors = validate_send(amount, phone)

        if errors:
            raise ValidationError(errors)

        recipient = self.users.by_phone(phone)

        if recipient is None:
            print("no such user:", phone)

            return

        if recipient.id == sender_id:
            raise NotAllowed("you cannot send money to yourself")

        sender = self.repo.account(sender_id)

        if sender.balance < amount:
            return False

        sender.balance -= amount
        self.repo.save_account(sender)
        transfer = self.repo.insert_transfer(
            sender_id, recipient.id, amount, note=note, created_at=self.clock()
        )

        self.notifier.push(
            recipient.id,
            f"You received {format_amount(amount)} (transfer #{transfer.id})."
            " Accept it within 30 days."
        )

        return True

    def pending(self, user_id):
        """Incoming pending transfers, as (transfer, sender name, masked sender phone) tuples."""

        items = []

        for transfer in self.repo.pending_to(user_id):
            sender = self.users.get(transfer.sender_id)
            sender.phone = mask_phone(sender.phone)
            items.append((transfer, sender.name, sender.phone))

        return items

    def accept(self, user_id, transfer_id):
        transfer = self._pending_to(user_id, transfer_id)

        if self.clock() - transfer.created_at >= EXPIRY:
            raise TransferExpired(transfer_id)

        self.repo.set_status(transfer.id, ACCEPTED, settled_at=self.clock())
        account = self.repo.account(user_id)
        account.balance += transfer.amount
        self.repo.save_account(account)

        self.notifier.push(
            transfer.sender_id,
            f"Your transfer #{transfer.id} of {format_amount(transfer.amount)} was accepted."
        )

    def expire_pending(self):
        """The nightly job: refunds every transfer that was not accepted in time."""

        expired = self.repo.pending_created_before(self.clock() - EXPIRY)

        for transfer in expired:
            self.repo.set_status(transfer.id, EXPIRED, settled_at=self.clock())
            account = self.repo.account(transfer.sender_id)
            account.balance += transfer.amount
            self.repo.save_account(account)

            self.notifier.push(
                transfer.sender_id,
                f"Your transfer #{transfer.id} of {format_amount(transfer.amount)} expired."
                " The money is back in your wallet."
            )

        return len(expired)

    def _pending_to(self, user_id, transfer_id):
        transfer = self.repo.transfer(transfer_id)

        if (
            transfer is None
            or transfer.recipient_id != user_id
            or transfer.status != PENDING
        ):
            raise TransferNotFound(transfer_id)

        return transfer

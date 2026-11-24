"""The data PeerPay works with, and the rules that belong to it. Entities are immutable:
a change is a new object, saved explicitly."""
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from .errors import InvalidTransition
from .money import Money
from .values import BankAccount, PhoneNumber

EXPIRY = timedelta(days=30)                     # DESIGN.md §5: the ONLY definition of "a month"


class Status(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


ALLOWED = {
    Status.PENDING: frozenset({Status.ACCEPTED, Status.DECLINED, Status.CANCELLED, Status.EXPIRED}),
}


@dataclass(frozen=True)
class User:
    id: int
    phone: PhoneNumber
    name: str
    bank_account: BankAccount
    password_hash: str
    last_login: datetime | None = None


@dataclass(frozen=True)
class Transfer:
    id: int
    sender_id: int
    recipient_id: int
    amount: Money
    note: str
    status: Status
    created_at: datetime
    settled_at: datetime | None = None

    @property
    def expires_at(self) -> datetime:
        return self.created_at + EXPIRY

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def moved_to(self, status: Status, at: datetime) -> "Transfer":
        """The state machine (DESIGN.md §5): returns the transfer in its new status."""
        if status not in ALLOWED.get(self.status, frozenset()):
            raise InvalidTransition(self.status, status)
        return dataclasses.replace(self, status=status, settled_at=at)

    def other_party(self, user_id: int) -> int:
        return self.recipient_id if user_id == self.sender_id else self.sender_id

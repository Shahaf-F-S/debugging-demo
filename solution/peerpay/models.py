"""The data PeerPay works with, and the rules that belong to it (DESIGN.md §5).

Entities are immutable: a change produces a new object, which is then saved explicitly. Nothing
can change an object behind its owner's back (bugs C6 and S4).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from .errors import InvalidTransition
from .money import Money
from .values import BankAccount, PhoneNumber

EXPIRY = timedelta(days=30)                     # the only definition of "a month" (bug C4)


class Status(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# The state machine: which status may follow which. A settled transfer never changes again.
ALLOWED: dict[Status, frozenset[Status]] = {
    Status.PENDING: frozenset({Status.ACCEPTED, Status.DECLINED, Status.CANCELLED, Status.EXPIRED})
}


@dataclass(frozen=True, slots=True)
class User:
    id: int
    phone: PhoneNumber
    name: str
    bank_account: BankAccount
    password_hash: str
    last_login: datetime | None = None


@dataclass(frozen=True, slots=True)
class Transfer:
    """Money on its way from one user to another; ``status`` says where it stands."""

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

    def moved_to(self, status: Status, at: datetime) -> Self:
        """Returns this transfer in its new status, settled ``at``.

        Raises InvalidTransition for a change that ``ALLOWED`` doesn't list, e.g. accepting a
        transfer that was already cancelled.
        """

        if status not in ALLOWED.get(self.status, frozenset()):
            raise InvalidTransition(self.status, status)

        return replace(self, status=status, settled_at=at)

    def other_party(self, user_id: int) -> int:
        return self.recipient_id if user_id == self.sender_id else self.sender_id

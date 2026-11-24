"""The data PeerPay works with, and the rules that belong to it (DESIGN.md §4).

Entities are immutable: a change produces a new object, which is then saved explicitly, so
nothing can change an object behind its owner's back (bug C5).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from .errors import InvalidTransition
from .money import Money
from .values import BankAccount, PhoneNumber

EXPIRY = timedelta(days=30)                     # the only definition of "a month" (bug S3)


class Status(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"


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

    def settled(self, status: Status, at: datetime) -> Self:
        """Returns this transfer settled with ``status`` at ``at``.

        Only a PENDING transfer can be settled, and only once: anything else raises
        InvalidTransition (accepting an expired transfer, accepting twice, ...).
        """

        if self.status is not Status.PENDING or status is Status.PENDING:
            raise InvalidTransition(self.status, status)

        return replace(self, status=status, settled_at=at)

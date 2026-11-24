"""The data PeerPay works with."""
from dataclasses import dataclass
from datetime import datetime

from .money import Money

# Transfer statuses (DESIGN.md §5)
PENDING = "PENDING"
ACCEPTED = "ACCEPTED"
DECLINED = "DECLINED"
CANCELLED = "CANCELLED"
EXPIRED = "EXPIRED"


@dataclass
class User:
    id: int
    phone: str
    name: str
    bank_account: str
    password_hash: str
    last_login: datetime | None = None


@dataclass
class Account:
    user_id: int
    balance: Money


@dataclass
class Transfer:
    id: int
    sender_id: int
    recipient_id: int
    amount: Money
    note: str
    status: str
    created_at: datetime
    settled_at: datetime | None = None

    def other_party(self, user_id: int) -> int:
        return self.recipient_id if user_id == self.sender_id else self.sender_id

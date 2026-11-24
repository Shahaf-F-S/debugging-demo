"""The data PeerPay works with."""

from dataclasses import dataclass
from datetime import datetime

# Transfer statuses (DESIGN.md §4)
PENDING = "PENDING"
ACCEPTED = "ACCEPTED"
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
    balance: int                # agorot


@dataclass
class Transfer:
    id: int
    sender_id: int
    recipient_id: int
    amount: int                 # agorot
    note: str
    status: str
    created_at: datetime
    settled_at: datetime | None = None

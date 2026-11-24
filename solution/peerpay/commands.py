"""Commands: one object per use case that changes money, fully described and already validated."""
from dataclasses import dataclass

from .money import Money
from .values import Note, PhoneNumber


@dataclass(frozen=True)
class TopUp:
    user_id: int
    amount: Money


@dataclass(frozen=True)
class SendTransfer:
    sender_id: int
    recipient: PhoneNumber
    amount: Money
    note: Note

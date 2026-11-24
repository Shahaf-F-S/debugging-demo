"""Commands (DESIGN.md §4): one immutable object per use case that moves money.

A command carries everything its use case needs, already validated and in types that can't be
mixed up, so the service can't be called with half-checked input or arguments in the wrong order.
"""

from dataclasses import dataclass

from .money import Money
from .values import Note, PhoneNumber


@dataclass(frozen=True, slots=True)
class TopUp:
    user_id: int
    amount: Money


@dataclass(frozen=True, slots=True)
class SendTransfer:
    sender_id: int
    recipient: PhoneNumber
    amount: Money
    note: Note

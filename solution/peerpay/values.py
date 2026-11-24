"""Value objects (DESIGN.md §2, §4): if one exists, it is valid.

Text from the outside world is parsed into these at the edge (the API). Everything inside works
with values that cannot be malformed, so a check can't be forgotten in one of several places.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol, Self

from .errors import ValidationError

MAX_NOTE = 140
MIN_PASSWORD = 8
_PHONE_RE = re.compile(r"05\d{8}")


class AccountChecker(Protocol):
    """Anything that can tell whether a bank account number exists: the bank, or a fake."""

    def validate_account(self, account_number: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """A mobile phone number, always held as ``05XXXXXXXX``."""

    digits: str

    def __post_init__(self) -> None:
        if not _PHONE_RE.fullmatch(self.digits):
            raise ValidationError(["invalid phone number"])

    @classmethod
    def parse(cls, text: str) -> Self:
        """``PhoneNumber.parse("052-123 4567") == PhoneNumber("0521234567")``."""

        return cls(re.sub(r"[\s-]", "", text))

    def masked(self) -> str:
        """``05*-***-4567``, for display. A new string: the number itself never changes (bug C6)."""

        return f"{self.digits[:2]}*-***-{self.digits[-4:]}"

    def __str__(self) -> str:
        return self.digits


@dataclass(frozen=True, slots=True)
class Note:
    """The free text attached to a transfer, at most ``MAX_NOTE`` characters (bug C5)."""

    text: str = ""

    def __post_init__(self) -> None:
        if len(self.text) > MAX_NOTE:
            raise ValidationError([f"note is longer than {MAX_NOTE} characters"])

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class BankAccount:
    """A bank account number.

    ``parse`` checks user input with the bank; numbers loaded from the database were checked
    when they were stored, so they are built directly.
    """

    number: str

    @classmethod
    def parse(cls, text: str, bank: AccountChecker) -> Self:
        if not bank.validate_account(text):
            raise ValidationError(["invalid bank account"])

        return cls(text)

    def __str__(self) -> str:
        return self.number


@dataclass(frozen=True, slots=True)
class Password:
    """A password that passed the length rule. Its value never shows in a repr, log or traceback."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.value) < MIN_PASSWORD:
            raise ValidationError([f"password must have at least {MIN_PASSWORD} characters"])

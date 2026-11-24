"""Value objects (DESIGN.md §2, §4). If one exists, it is valid: parse input into them at the edge."""
import re
from dataclasses import dataclass, field

from .errors import ValidationError

MAX_NOTE = 140
MIN_PASSWORD = 8


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    digits: str

    def __post_init__(self):
        if not re.fullmatch(r"05\d{8}", self.digits):
            raise ValidationError(["invalid phone number"])

    @classmethod
    def parse(cls, text: str) -> "PhoneNumber":
        """'052-123 4567' → PhoneNumber('0521234567')"""
        return cls(re.sub(r"[\s-]", "", text))

    def masked(self) -> str:
        """A new string for display, '05*-***-4567'. The number itself never changes."""
        return f"{self.digits[:2]}*-***-{self.digits[-4:]}"

    def __str__(self) -> str:
        return self.digits


@dataclass(frozen=True, slots=True)
class Note:
    text: str = ""

    def __post_init__(self):
        if len(self.text) > MAX_NOTE:
            raise ValidationError([f"note is longer than {MAX_NOTE} characters"])

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class BankAccount:
    number: str

    @classmethod
    def parse(cls, text: str, bank) -> "BankAccount":
        """User input is checked with the bank; numbers loaded from the DB were checked when stored."""
        if not bank.validate_account(text):
            raise ValidationError(["invalid bank account"])
        return cls(text)

    def __str__(self) -> str:
        return self.number


@dataclass(frozen=True, slots=True)
class Password:
    value: str = field(repr=False)              # never shows up in logs or tracebacks

    def __post_init__(self):
        if len(self.value) < MIN_PASSWORD:
            raise ValidationError([f"password must have at least {MIN_PASSWORD} characters"])

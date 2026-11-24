"""Validation of whole requests (DESIGN.md §2, §3, §6).

A request is parsed into value objects in one go, and every problem in it is reported at once.
Each call collects into a list of its own, so nothing leaks from one request into the next
(bug C1). All of it happens before anything changes: validate, then act.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .errors import ValidationError
from .money import Money
from .values import AccountChecker, BankAccount, Note, Password, PhoneNumber


@dataclass(frozen=True, slots=True)
class SendRequest:
    recipient: PhoneNumber
    amount: Money
    note: Note


@dataclass(frozen=True, slots=True)
class Registration:
    phone: PhoneNumber
    name: str
    bank_account: BankAccount
    password: Password


def collect[T](parse: Callable[[], T], errors: list[str]) -> T | None:
    """Runs ``parse``. On a ValidationError, adds its problems to ``errors`` and returns None."""

    try:
        return parse()

    except ValidationError as e:
        errors.extend(e.errors)

        return None


def positive(amount: Money) -> Money:
    if not amount.is_positive():
        raise ValidationError(["amount must be positive"])

    return amount


def required(name: str) -> str:
    if not name.strip():
        raise ValidationError(["name is required"])

    return name.strip()


def parse_send(phone_text: str, amount_text: str, note_text: str) -> SendRequest:
    """Parses one send request, or raises one ValidationError with all of its problems."""

    errors: list[str] = []
    recipient = collect(lambda: PhoneNumber.parse(phone_text), errors)
    amount = collect(lambda: positive(Money.parse(amount_text)), errors)
    note = collect(lambda: Note(note_text), errors)

    if recipient is None or amount is None or note is None:
        raise ValidationError(errors)

    return SendRequest(recipient, amount, note)


def parse_registration(
    phone_text: str,
    name: str,
    bank_account_text: str,
    password_text: str,
    bank: AccountChecker
) -> Registration:
    """Parses one registration, or raises one ValidationError with all of its problems."""

    errors: list[str] = []
    phone = collect(lambda: PhoneNumber.parse(phone_text), errors)
    clean_name = collect(lambda: required(name), errors)
    bank_account = collect(lambda: BankAccount.parse(bank_account_text, bank), errors)
    password = collect(lambda: Password(password_text), errors)

    if phone is None or clean_name is None or bank_account is None or password is None:
        raise ValidationError(errors)

    return Registration(phone, clean_name, bank_account, password)

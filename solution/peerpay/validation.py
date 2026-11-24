"""Validation (DESIGN.md §2, §4, §7): parse one request into value objects, collecting ALL its problems.

Every call starts from a fresh list of errors, so nothing leaks from one request into the next.
Validation happens before anything is changed (validate, then act).
"""
from .errors import ValidationError
from .money import Money
from .values import BankAccount, Note, Password, PhoneNumber


def parse_all(**parsers) -> dict:
    """Runs every parser (a function without arguments) and raises one ValidationError with all the problems.

    parse_all(phone=lambda: PhoneNumber.parse(text), ...) → {"phone": PhoneNumber(...), ...}
    """
    values, errors = {}, []
    for name, parse in parsers.items():
        try:
            values[name] = parse()
        except ValidationError as e:
            errors.extend(e.errors)
    if errors:
        raise ValidationError(errors)
    return values


def positive(amount: Money) -> Money:
    if not amount.is_positive():
        raise ValidationError(["amount must be positive"])
    return amount


def required(name: str) -> str:
    if not name.strip():
        raise ValidationError(["name is required"])
    return name.strip()


def parse_send(phone_text, amount_text, note_text) -> dict:
    return parse_all(
        recipient=lambda: PhoneNumber.parse(phone_text),
        amount=lambda: positive(Money.parse(amount_text)),
        note=lambda: Note(note_text),
    )


def parse_registration(phone_text, name, bank_account_text, password_text, bank) -> dict:
    return parse_all(
        phone=lambda: PhoneNumber.parse(phone_text),
        name=lambda: required(name),
        bank_account=lambda: BankAccount.parse(bank_account_text, bank),
        password=lambda: Password(password_text),
    )

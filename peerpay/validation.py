"""Input checks (DESIGN.md §2 and §4). Each check returns a list of error messages; empty means valid."""
import re

PHONE_RE = re.compile(r"05\d{8}")
MAX_NOTE = 140
MIN_PASSWORD = 8


def normalize_phone(text: str) -> str:
    """'052-123 4567' → '0521234567'"""
    return re.sub(r"[\s-]", "", text)


def mask_phone(phone: str) -> str:
    """'0521234567' → '05*-***-4567'"""
    return f"{phone[:2]}*-***-{phone[-4:]}"


def validate_registration(phone, name, bank_account, password, bank) -> list[str]:
    errors = []
    if not PHONE_RE.fullmatch(phone):
        errors.append("invalid phone number")
    if not name.strip():
        errors.append("name is required")
    if not bank.validate_account(bank_account):
        errors.append("invalid bank account")
    if len(password) < MIN_PASSWORD:
        errors.append(f"password must have at least {MIN_PASSWORD} characters")
    return errors


def validate_send(amount, recipient_phone, errors=[]) -> list[str]:
    if amount <= 0:
        errors.append("amount must be positive")
    if not PHONE_RE.fullmatch(recipient_phone):
        errors.append("invalid phone number")
    return errors

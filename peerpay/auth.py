"""Registration, login and password hashing (DESIGN.md §2)."""
import hashlib
import hmac
import os

from .errors import LoginFailed, ValidationError
from .validation import normalize_phone, validate_registration

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, iterations, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def register(wallet, phone, name, bank_account, password) -> int:
    phone = normalize_phone(phone)
    errors = validate_registration(phone, name, bank_account, password, wallet.bank)
    if not errors and wallet.users.by_phone(phone) is not None:
        errors.append("this phone number is already registered")
    if errors:
        raise ValidationError(errors)
    user = wallet.users.add(phone, name.strip(), bank_account, hash_password(password))
    return user.id


def login(wallet, phone, password) -> int:
    user = wallet.users.by_phone(normalize_phone(phone))
    if user is None or not verify_password(password, user.password_hash):
        raise LoginFailed()
    user.last_login = wallet.clock()
    wallet.users.save(user)
    return user.id

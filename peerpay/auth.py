"""Registration, login and password hashing (DESIGN.md §2)."""

import hashlib
import os

from .errors import LoginFailed, ValidationError
from .validation import normalize_phone, validate_registration

ITERATIONS = 600_000
SALT = os.urandom(16)


def hash_password(password):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), SALT, ITERATIONS)

    return f"pbkdf2_sha256${ITERATIONS}${digest.hex()}"


def verify_password(password, stored):
    _, iterations, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), SALT, int(iterations))

    return digest.hex() == digest_hex


def register(wallet, phone, name, bank_account, password):
    phone = normalize_phone(phone)
    errors = validate_registration(phone, name, bank_account, password, wallet.bank)

    if not errors and wallet.users.by_phone(phone) is not None:
        errors.append("this phone number is already registered")

    if errors:
        raise ValidationError(errors)

    user = wallet.users.add(phone, name.strip(), bank_account, hash_password(password))

    return user.id


def login(wallet, phone, password):
    user = wallet.users.by_phone(normalize_phone(phone))

    if user is None or not verify_password(password, user.password_hash):
        raise LoginFailed()

    user.last_login = wallet.clock()
    wallet.users.save(user)

    return user.id

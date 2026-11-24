"""Registration, login and password hashing (DESIGN.md §2)."""
import hashlib
import hmac
import os

from .errors import LoginFailed, ValidationError
from .validation import parse_registration
from .values import Password, PhoneNumber

ITERATIONS = 600_000


def hash_password(password: Password) -> str:
    salt = os.urandom(16)                       # per user, stored inside the hash below
    digest = hashlib.pbkdf2_hmac("sha256", password.value.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, iterations, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def register(wallet, phone, name, bank_account, password) -> int:
    form = parse_registration(phone, name, bank_account, password, wallet.bank)
    password_hash = hash_password(form["password"])            # slow on purpose: outside the transaction
    with wallet.uow() as uow:
        if uow.users.by_phone(form["phone"]) is not None:
            raise ValidationError(["this phone number is already registered"])
        return uow.users.add(form["phone"], form["name"], form["bank_account"], password_hash).id


def login(wallet, phone, password) -> int:
    try:
        phone = PhoneNumber.parse(phone)
    except ValidationError:
        raise LoginFailed() from None
    with wallet.uow() as uow:
        user = uow.users.by_phone(phone)
    if user is None or not verify_password(password, user.password_hash):   # slow: outside the transaction
        raise LoginFailed()
    with wallet.uow() as uow:
        uow.users.touch_last_login(user.id, wallet.clock())
    return user.id

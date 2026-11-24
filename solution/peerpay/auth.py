"""Registration, login and password hashing (DESIGN.md §2).

Passwords are hashed with PBKDF2-HMAC-SHA256 and a random salt per user, and stored in the
self-describing format ``pbkdf2_sha256$<iterations>$<salt>$<digest>``: the salt is never lost
(bug H1), and the iteration count can be raised later without breaking existing users.
"""

import hashlib
import hmac
import os

from .errors import LoginFailed, ValidationError
from .service import WalletService
from .validation import parse_registration
from .values import Password, PhoneNumber

ITERATIONS = 600_000


def hash_password(password: Password) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.value.encode(), salt, ITERATIONS)

    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, iterations, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
    )

    # compare_digest takes the same time wherever the first difference is: no timing leak
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def register(
    wallet: WalletService,
    phone: str,
    name: str,
    bank_account: str,
    password: str
) -> int:
    """Registers a user and returns the new user id.

    Raises one ValidationError listing every problem of the request. The slow hashing is done
    before the transaction starts, so the database isn't locked while it runs.
    """

    form = parse_registration(phone, name, bank_account, password, wallet.bank)
    password_hash = hash_password(form.password)

    with wallet.uow() as uow:
        if uow.users.by_phone(form.phone) is not None:
            raise ValidationError(["this phone number is already registered"])

        user = uow.users.add(
            form.phone, form.name, form.bank_account, password_hash=password_hash
        )

    return user.id


def login(wallet: WalletService, phone: str, password: str) -> int:
    """Returns the user's id, or raises LoginFailed without telling which half was wrong."""

    try:
        number = PhoneNumber.parse(phone)

    except ValidationError:
        raise LoginFailed() from None

    with wallet.uow() as uow:
        user = uow.users.by_phone(number)

    if user is None or not verify_password(password, user.password_hash):
        raise LoginFailed()

    with wallet.uow() as uow:
        uow.users.touch_last_login(user.id, wallet.clock())

    return user.id

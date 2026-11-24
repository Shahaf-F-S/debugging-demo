"""Every error the service can raise (DESIGN.md §5).

The API's error boundary (``api.endpoint``) turns each of them into an error response with the
error's ``code``; anything else that escapes is an unexpected bug and is reported as such.
"""

from collections.abc import Iterable
from typing import ClassVar


class WalletError(Exception):
    """The base of every expected failure. ``code`` is what the API reports to the client."""

    code: ClassVar[str] = "error"


class ValidationError(WalletError):
    """One request had invalid input. ``errors`` lists every problem found in it, not just one."""

    code = "invalid"

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class LoginFailed(WalletError):
    code = "login_failed"

    def __init__(self) -> None:
        super().__init__("wrong phone number or password")


class NotLoggedIn(WalletError):
    code = "not_logged_in"

    def __init__(self) -> None:
        super().__init__("please log in")


class UnknownRecipient(WalletError):
    code = "unknown_recipient"

    def __init__(self, phone: str) -> None:
        super().__init__(f"no PeerPay user has the phone number {phone}")


class InsufficientFunds(WalletError):
    code = "insufficient_funds"

    def __init__(self) -> None:
        super().__init__("not enough money in your wallet")


class NotAllowed(WalletError):
    code = "not_allowed"


class TransferNotFound(WalletError):
    code = "not_found"

    def __init__(self, transfer_id: int) -> None:
        super().__init__(f"you have no pending transfer #{transfer_id}")


class TransferExpired(WalletError):
    code = "expired"

    def __init__(self, transfer_id: int) -> None:
        super().__init__(f"transfer #{transfer_id} has expired")


class TopUpFailed(WalletError):
    code = "top_up_failed"


class InvalidTransition(WalletError):
    """A transfer was asked to change status in a way DESIGN.md §4 doesn't allow."""

    code = "invalid_transition"

    def __init__(self, current: str, wanted: str) -> None:
        super().__init__(f"a {current} transfer cannot become {wanted}")

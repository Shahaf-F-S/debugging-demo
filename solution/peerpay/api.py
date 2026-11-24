"""The PeerPay API: one method per request, each returning a JSON-ready dict.

Text from the outside world becomes value objects here, at the edge. Errors become responses in
exactly one place, the ``@endpoint`` decorator (DESIGN.md §5): a method returns its payload or
raises, and never builds an error response itself (bug S1).
"""

import functools
import logging
import secrets
from collections.abc import Callable
from typing import Any

from . import auth
from .bank import BankAdapter
from .bank_gateway import MockBank
from .clock import SystemClock
from .errors import NotLoggedIn, WalletError
from .money import Money
from .notifier import Notifier
from .repository import DbPath, create_schema
from .service import Clock, WalletService
from .validation import parse_send, positive

type Response = dict[str, Any]

log = logging.getLogger(__name__)


def endpoint[**P](method: Callable[P, Response]) -> Callable[P, Response]:
    """The error boundary around every API method.

    The method's payload is returned as ``{"ok": True, **payload}``; a WalletError becomes
    ``{"ok": False, "error": <code>, "message": <text>}``; anything else is an unexpected bug,
    which is logged with its traceback and reported as ``internal_error``.
    """

    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Response:
        try:
            return {"ok": True, **method(*args, **kwargs)}

        except WalletError as e:
            return {"ok": False, "error": e.code, "message": str(e)}

        except Exception:
            log.exception("unexpected error in %s", method.__name__)

            return {
                "ok": False,
                "error": "internal_error",
                "message": "something went wrong; it was logged"
            }

    return wrapper


class PeerPayAPI:
    """One PeerPay server: the composition root that builds all the parts and wires them up."""

    def __init__(
        self,
        db_path: DbPath,
        bank: MockBank | None = None,
        clock: Clock | None = None
    ) -> None:
        create_schema(db_path)
        self.notifier = Notifier()
        self.wallet = WalletService(
            db_path, BankAdapter(bank or MockBank(db_path)),
            clock=clock or SystemClock(), notifier=self.notifier
        )
        self._sessions: dict[str, int] = {}             # token -> user id

    def close(self) -> None:
        """Nothing to release: every unit of work closes its own connection."""

    def _user_id(self, token: str) -> int:
        if token not in self._sessions:
            raise NotLoggedIn()

        return self._sessions[token]

    @endpoint
    def register(self, phone: str, name: str, bank_account: str, password: str) -> Response:
        return {"user_id": auth.register(self.wallet, phone, name, bank_account, password)}

    @endpoint
    def login(self, phone: str, password: str) -> Response:
        user_id = auth.login(self.wallet, phone, password)
        token = secrets.token_urlsafe(16)
        self._sessions[token] = user_id

        return {"token": token}

    @endpoint
    def balance(self, token: str) -> Response:
        balance = self.wallet.balance(self._user_id(token))

        return {"balance": str(balance), "agorot": balance.agorot}

    @endpoint
    def top_up(self, token: str, amount_text: str) -> Response:
        self.wallet.top_up(self._user_id(token), positive(Money.parse(amount_text)))

        return {}

    @endpoint
    def send(self, token: str, phone: str, amount_text: str, note: str = "") -> Response:
        user_id = self._user_id(token)
        transfer = self.wallet.send(user_id, parse_send(phone, amount_text, note))

        return {"transfer_id": transfer.id, "message": "Sent ✓"}

    @endpoint
    def pending(self, token: str) -> Response:
        return {
            "pending": [
                {
                    "id": item.transfer.id,
                    "from": item.sender_name,
                    "phone": item.sender_phone,
                    "amount": str(item.transfer.amount),
                    "note": item.transfer.note,
                    "expires_at": item.transfer.expires_at.isoformat()
                }
                for item in self.wallet.pending(self._user_id(token))
            ]
        }

    @endpoint
    def accept(self, token: str, transfer_id: int) -> Response:
        self.wallet.accept(self._user_id(token), transfer_id)

        return {}

    @endpoint
    def notifications(self, token: str) -> Response:
        return {"messages": self.notifier.messages_for(self._user_id(token))}

    @endpoint
    def run_expiry(self) -> Response:
        """The nightly job (DESIGN.md §4). Called by the scheduler, not by users."""

        return {"expired": self.wallet.expire_pending()}

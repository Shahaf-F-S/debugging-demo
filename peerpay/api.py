"""The PeerPay API: one method per request. Every method returns a JSON-ready dict.

Input text becomes value objects here, at the edge. Errors become responses in exactly one place:
the @endpoint decorator (DESIGN.md §6).
"""
import functools
import logging
import secrets

from . import auth
from .bank import BankAdapter
from .bank_gateway import MockBank
from .clock import SystemClock
from .commands import SendTransfer, TopUp
from .errors import NotLoggedIn, WalletError
from .events import EventBus, Notifier, wire_notifications
from .money import Money
from .repository import create_schema
from .service import WalletService
from .validation import parse_send, positive

log = logging.getLogger(__name__)


def endpoint(method):
    """The error boundary: a method returns its payload, or raises; the response is built here."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return {"ok": True, **method(*args, **kwargs)}
        except WalletError as e:
            return {"ok": False, "error": e.code, "message": str(e)}
        except Exception:
            log.exception("unexpected error in %s", method.__name__)
            return {"ok": False, "error": "internal_error", "message": "something went wrong; it was logged"}
    return wrapper


class PeerPayAPI:
    def __init__(self, db_path, bank=None, clock=None):
        create_schema(db_path)
        self.clock = clock or SystemClock()
        self.notifier = Notifier()
        bus = EventBus()
        wire_notifications(bus, self.notifier)
        self.wallet = WalletService(db_path, BankAdapter(bank or MockBank(db_path)), self.clock, bus)
        self._sessions = {}                     # token -> user id

    def close(self):
        """Nothing to release: every unit of work closes its own connection."""

    def _user_id(self, token) -> int:
        if token not in self._sessions:
            raise NotLoggedIn()
        return self._sessions[token]

    # --- users ----------------------------------------------------------------------------

    @endpoint
    def register(self, phone, name, bank_account, password):
        return {"user_id": auth.register(self.wallet, phone, name, bank_account, password)}

    @endpoint
    def login(self, phone, password):
        user_id = auth.login(self.wallet, phone, password)
        token = secrets.token_urlsafe(16)
        self._sessions[token] = user_id
        return {"token": token}

    # --- wallet ---------------------------------------------------------------------------

    @endpoint
    def balance(self, token):
        balance = self.wallet.balance(self._user_id(token))
        return {"balance": str(balance), "agorot": balance.agorot}

    @endpoint
    def top_up(self, token, amount_text):
        self.wallet.top_up(TopUp(self._user_id(token), positive(Money.parse(amount_text))))
        return {}

    @endpoint
    def send(self, token, phone, amount_text, note=""):
        user_id = self._user_id(token)
        request = parse_send(phone, amount_text, note)
        transfer = self.wallet.send(SendTransfer(user_id, request["recipient"], request["amount"], request["note"]))
        return {"transfer_id": transfer.id, "message": "Sent ✓"}

    @endpoint
    def pending(self, token):
        return {"pending": [
            {
                "id": t.id,
                "from": sender_name,
                "amount": str(t.amount),
                "note": t.note,
                "expires_at": t.expires_at.isoformat(),
            }
            for t, sender_name in self.wallet.pending(self._user_id(token))
        ]}

    @endpoint
    def accept(self, token, transfer_id):
        self.wallet.accept(self._user_id(token), transfer_id)
        return {}

    @endpoint
    def decline(self, token, transfer_id):
        self.wallet.decline(self._user_id(token), transfer_id)
        return {}

    @endpoint
    def cancel_last(self, token):
        return {"transfer_id": self.wallet.cancel_last(self._user_id(token)).id}

    @endpoint
    def statement(self, token):
        s = self.wallet.statement(self._user_id(token))
        return {
            "received_count": s["received_count"],
            "received_total": str(s["received_total"]),
            "sent_count": s["sent_count"],
            "sent_total": str(s["sent_total"]),
            "lines": s["lines"],
        }

    @endpoint
    def notifications(self, token):
        return {"messages": self.notifier.messages_for(self._user_id(token))}

    # --- jobs -----------------------------------------------------------------------------

    @endpoint
    def run_expiry(self):
        """The nightly job (DESIGN.md §5). Called by the scheduler, not by users."""
        return {"expired": self.wallet.expire_pending()}

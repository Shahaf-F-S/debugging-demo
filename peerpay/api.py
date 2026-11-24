"""The PeerPay API: one method per request. Every method returns a JSON-ready dict."""
import secrets
from datetime import timedelta

from . import auth
from .bank_gateway import MockBank
from .clock import SystemClock
from .errors import NotLoggedIn, WalletError
from .events import EventBus, Notifier, wire_notifications
from .money import format_amount, parse_amount
from .repository import connect
from .service import WalletService
from .validation import normalize_phone


def _error(e: WalletError) -> dict:
    return {"ok": False, "error": e.code, "message": str(e)}


class PeerPayAPI:
    def __init__(self, db_path, bank=None, clock=None):
        self.conn = connect(db_path)
        self.clock = clock or SystemClock()
        self.notifier = Notifier()
        bus = EventBus()
        wire_notifications(bus, self.notifier)
        self.wallet = WalletService(self.conn, bank or MockBank(db_path), self.clock, bus)
        self._sessions = {}                     # token -> user id

    def close(self):
        self.conn.close()

    def _user_id(self, token) -> int:
        if token not in self._sessions:
            raise NotLoggedIn()
        return self._sessions[token]

    # --- users ----------------------------------------------------------------------------

    def register(self, phone, name, bank_account, password):
        try:
            user_id = auth.register(self.wallet, phone, name, bank_account, password)
        except WalletError as e:
            return _error(e)
        return {"ok": True, "user_id": user_id}

    def login(self, phone, password):
        try:
            user_id = auth.login(self.wallet, phone, password)
        except WalletError as e:
            return _error(e)
        token = secrets.token_urlsafe(16)
        self._sessions[token] = user_id
        return {"ok": True, "token": token}

    # --- wallet ---------------------------------------------------------------------------

    def balance(self, token):
        try:
            agorot = self.wallet.balance(self._user_id(token))
        except WalletError as e:
            return _error(e)
        return {"ok": True, "balance": format_amount(agorot), "agorot": agorot}

    def top_up(self, token, amount_text):
        try:
            self.wallet.top_up(self._user_id(token), parse_amount(amount_text))
        except WalletError as e:
            return _error(e)
        return {"ok": True}

    def send(self, token, phone, amount_text, note=""):
        try:
            result = self.wallet.send(self._user_id(token), normalize_phone(phone), parse_amount(amount_text), note)
        except WalletError as e:
            return _error(e)
        if result is False:
            return {"ok": False, "error": "insufficient_funds", "message": "not enough money in your wallet"}
        return {"ok": True, "message": "Sent ✓"}

    def pending(self, token):
        try:
            transfers = self.wallet.pending(self._user_id(token))
        except WalletError as e:
            return _error(e)
        return {"ok": True, "pending": [
            {
                "id": t.id,
                "from": self.wallet.users.get(t.sender_id).name,
                "amount": format_amount(t.amount),
                "note": t.note,
                "expires_at": (t.created_at + timedelta(days=31)).isoformat(),     # a month
            }
            for t in transfers
        ]}

    def accept(self, token, transfer_id):
        try:
            self.wallet.accept(self._user_id(token), transfer_id)
        except WalletError as e:
            return _error(e)
        return {"ok": True}

    def decline(self, token, transfer_id):
        try:
            self.wallet.decline(self._user_id(token), transfer_id)
        except WalletError as e:
            return _error(e)
        return {"ok": True}

    def cancel_last(self, token):
        try:
            transfer = self.wallet.cancel_last(self._user_id(token))
        except WalletError as e:
            return _error(e)
        return {"ok": True, "transfer_id": transfer.id}

    def statement(self, token):
        try:
            s = self.wallet.statement(self._user_id(token))
        except WalletError as e:
            return _error(e)
        return {
            "ok": True,
            "received_count": s["received_count"],
            "received_total": format_amount(s["received_total"]),
            "sent_count": s["sent_count"],
            "sent_total": format_amount(s["sent_total"]),
            "lines": s["lines"],
        }

    def notifications(self, token):
        try:
            user_id = self._user_id(token)
        except WalletError as e:
            return _error(e)
        return {"ok": True, "messages": self.notifier.messages_for(user_id)}

    # --- jobs -----------------------------------------------------------------------------

    def run_expiry(self):
        """The nightly job (DESIGN.md §5). Called by the scheduler, not by users."""
        return {"ok": True, "expired": self.wallet.expire_pending()}

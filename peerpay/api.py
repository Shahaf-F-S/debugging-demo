"""The PeerPay API: one method per request. Every method returns a JSON-ready dict."""

import secrets

from . import auth
from .bank_gateway import MockBank
from .clock import SystemClock
from .errors import NotLoggedIn, WalletError
from .money import format_amount, parse_amount
from .notifier import Notifier
from .repository import connect
from .service import EXPIRY, WalletService
from .validation import normalize_phone


def _error(e):
    return {"ok": False, "error": e.code, "message": str(e)}


class PeerPayAPI:
    def __init__(self, db_path, bank=None, clock=None):
        self.conn = connect(db_path)
        self.notifier = Notifier()
        self.wallet = WalletService(
            self.conn, bank or MockBank(db_path), clock or SystemClock(), self.notifier
        )
        self._sessions = {}                     # token -> user id

    def close(self):
        self.conn.close()

    def _user_id(self, token):
        if token not in self._sessions:
            raise NotLoggedIn()

        return self._sessions[token]

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
            result = self.wallet.send(
                self._user_id(token), normalize_phone(phone), parse_amount(amount_text),
                note=note
            )

        except WalletError as e:
            return _error(e)

        if result is False:
            return {
                "ok": False,
                "error": "insufficient_funds",
                "message": "not enough money in your wallet"
            }

        return {"ok": True, "message": "Sent ✓"}

    def pending(self, token):
        try:
            items = self.wallet.pending(self._user_id(token))

        except WalletError as e:
            return _error(e)

        return {
            "ok": True,
            "pending": [
                {
                    "id": t.id,
                    "from": name,
                    "phone": phone,
                    "amount": format_amount(t.amount),
                    "note": t.note,
                    "expires_at": (t.created_at + EXPIRY).isoformat()
                }
                for t, name, phone in items
            ]
        }

    def accept(self, token, transfer_id):
        try:
            self.wallet.accept(self._user_id(token), transfer_id)

        except WalletError as e:
            return _error(e)

        return {"ok": True}

    def notifications(self, token):
        return {"ok": True, "messages": self.notifier.messages_for(token)}

    def run_expiry(self):
        """The nightly job (DESIGN.md §4). Called by the scheduler, not by users."""

        return {"ok": True, "expired": self.wallet.expire_pending()}

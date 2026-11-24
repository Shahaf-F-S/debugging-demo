"""All SQL of PeerPay lives here (DESIGN.md §8). Money columns hold agorot."""
import sqlite3
from datetime import datetime

from .models import Account, Transfer, User
from .money import Money

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    phone         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    bank_account  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    last_login    TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    balance INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS transfers (
    id           INTEGER PRIMARY KEY,
    sender_id    INTEGER NOT NULL REFERENCES users(id),
    recipient_id INTEGER NOT NULL REFERENCES users(id),
    agorot       INTEGER NOT NULL CHECK (agorot > 0),
    note         TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 140),
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    settled_at   TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    agorot      INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    transfer_id INTEGER REFERENCES transfers(id),
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


def connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds")


def _time(text):
    return datetime.fromisoformat(text) if text else None


def _user(row) -> User:
    return User(row["id"], row["phone"], row["name"], row["bank_account"], row["password_hash"],
                _time(row["last_login"]))


def _transfer(row) -> Transfer:
    return Transfer(row["id"], row["sender_id"], row["recipient_id"], Money(row["agorot"]), row["note"],
                    row["status"], _time(row["created_at"]), _time(row["settled_at"]))


class UserDirectory:
    """Users rarely change, so every user that was loaded once is kept in memory."""

    def __init__(self, conn):
        self.conn = conn
        self._cache = {}

    def add(self, phone, name, bank_account, password_hash) -> User:
        cur = self.conn.execute(
            "INSERT INTO users (phone, name, bank_account, password_hash) VALUES (?, ?, ?, ?)",
            (phone, name, bank_account, password_hash),
        )
        self.conn.execute("INSERT INTO accounts (user_id, balance) VALUES (?, 0)", (cur.lastrowid,))
        return self.get(cur.lastrowid)

    def get(self, user_id) -> User | None:
        if user_id not in self._cache:
            row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            self._cache[user_id] = _user(row)
        return self._cache[user_id]

    def by_phone(self, phone) -> User | None:
        row = self.conn.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
        return self.get(row["id"]) if row else None

    def save(self, user: User) -> None:
        self.conn.execute(
            "UPDATE users SET phone = ?, name = ?, bank_account = ?, password_hash = ?, last_login = ?"
            " WHERE id = ?",
            (user.phone, user.name, user.bank_account, user.password_hash,
             _iso(user.last_login) if user.last_login else None, user.id),
        )


class Repository:
    """Accounts, ledger and transfers."""

    def __init__(self, conn):
        self.conn = conn

    # --- accounts -------------------------------------------------------------------------

    def account(self, user_id) -> Account:
        row = self.conn.execute("SELECT user_id, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
        return Account(row["user_id"], Money(row["balance"]))

    def save_account(self, account: Account) -> None:
        self.conn.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (account.balance.agorot, account.user_id))

    # --- ledger ---------------------------------------------------------------------------

    def add_ledger(self, user_id, amount: Money, kind, created_at, transfer_id=None, note="") -> None:
        self.conn.execute(
            "INSERT INTO ledger (user_id, agorot, kind, transfer_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount.agorot, kind, transfer_id, note, _iso(created_at)),
        )

    # --- transfers ------------------------------------------------------------------------

    def insert_transfer(self, sender_id, recipient_id, amount: Money, note, created_at) -> Transfer:
        cur = self.conn.execute(
            "INSERT INTO transfers (sender_id, recipient_id, agorot, note, status, created_at)"
            " VALUES (?, ?, ?, ?, 'PENDING', ?)",
            (sender_id, recipient_id, amount.agorot, note, _iso(created_at)),
        )
        return self.transfer(cur.lastrowid)

    def transfer(self, transfer_id) -> Transfer | None:
        row = self.conn.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
        return _transfer(row) if row else None

    def set_status(self, transfer_id, status, settled_at) -> None:
        self.conn.execute("UPDATE transfers SET status = ?, settled_at = ? WHERE id = ?",
                          (status, _iso(settled_at), transfer_id))

    def pending_to(self, user_id) -> list[Transfer]:
        rows = self.conn.execute(
            "SELECT * FROM transfers WHERE recipient_id = ? AND status = 'PENDING' ORDER BY id", (user_id,))
        return [_transfer(row) for row in rows]

    def pending_created_before(self, cutoff: datetime) -> list[Transfer]:
        rows = self.conn.execute(
            "SELECT * FROM transfers WHERE status = 'PENDING' AND created_at <= ? ORDER BY id", (_iso(cutoff),))
        return [_transfer(row) for row in rows]

    def last_pending_of(self, sender_id) -> Transfer | None:
        row = self.conn.execute(
            "SELECT * FROM transfers WHERE sender_id = ? AND status = 'PENDING' ORDER BY id DESC LIMIT 1",
            (sender_id,),
        ).fetchone()
        return _transfer(row) if row else None

    def transfers_to(self, user_id) -> list[Transfer]:
        """Accepted transfers that the user received."""
        rows = self.conn.execute(
            "SELECT * FROM transfers WHERE recipient_id = ? AND status = 'ACCEPTED' ORDER BY id", (user_id,))
        return [_transfer(row) for row in rows]

    def transfers_from(self, user_id) -> list[Transfer]:
        """Accepted transfers that the user sent."""
        rows = self.conn.execute(
            "SELECT * FROM transfers WHERE sender_id = ? AND status = 'ACCEPTED' ORDER BY id", (user_id,))
        return [_transfer(row) for row in rows]

    def transfers_of(self, user_id) -> list[Transfer]:
        """Every transfer the user sent or received, in any status."""
        rows = self.conn.execute(
            "SELECT * FROM transfers WHERE sender_id = ? OR recipient_id = ? ORDER BY id", (user_id, user_id))
        return [_transfer(row) for row in rows]

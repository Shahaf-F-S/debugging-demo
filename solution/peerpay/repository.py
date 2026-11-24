"""All SQL of PeerPay lives here (DESIGN.md §8). Money columns hold agorot.

A UnitOfWork is one transaction: every use case opens one, and it commits when the use case
succeeds, or rolls back when it raises. The repositories never commit by themselves.

The ledger is append-only and is the single source of truth for money (DESIGN.md §3): a balance
is not stored anywhere, it is the sum of the user's ledger entries. Repositories return immutable
objects in lists, keep no caches, and their writes change only what changed.
"""
import sqlite3
from datetime import datetime

from .models import Status, Transfer, User
from .money import Money
from .values import BankAccount, PhoneNumber

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    phone         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    bank_account  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    last_login    TEXT
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


def create_schema(db_path) -> None:
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


class UnitOfWork:
    """``with UnitOfWork(path) as uow:`` — one transaction, with the repositories that work inside it."""

    def __init__(self, db_path):
        self._db_path = db_path

    def __enter__(self) -> "UnitOfWork":
        self.conn = sqlite3.connect(self._db_path, timeout=5, isolation_level=None)   # we BEGIN/COMMIT ourselves
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("BEGIN IMMEDIATE")
        self.users = UserRepo(self.conn)
        self.ledger = LedgerRepo(self.conn)
        self.transfers = TransferRepo(self.conn)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.conn.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self.conn.close()
        return False


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds")


def _time(text):
    return datetime.fromisoformat(text) if text else None


def _user(row) -> User:
    return User(row["id"], PhoneNumber(row["phone"]), row["name"], BankAccount(row["bank_account"]),
                row["password_hash"], _time(row["last_login"]))


def _transfer(row) -> Transfer:
    return Transfer(row["id"], row["sender_id"], row["recipient_id"], Money(row["agorot"]), row["note"],
                    Status(row["status"]), _time(row["created_at"]), _time(row["settled_at"]))


class UserRepo:
    def __init__(self, conn):
        self.conn = conn

    def add(self, phone: PhoneNumber, name, bank_account: BankAccount, password_hash) -> User:
        cur = self.conn.execute(
            "INSERT INTO users (phone, name, bank_account, password_hash) VALUES (?, ?, ?, ?)",
            (str(phone), name, str(bank_account), password_hash),
        )
        return self.get(cur.lastrowid)

    def get(self, user_id) -> User | None:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user(row) if row else None

    def by_phone(self, phone: PhoneNumber) -> User | None:
        row = self.conn.execute("SELECT * FROM users WHERE phone = ?", (str(phone),)).fetchone()
        return _user(row) if row else None

    def touch_last_login(self, user_id, when: datetime) -> None:
        self.conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_iso(when), user_id))


class LedgerRepo:
    def __init__(self, conn):
        self.conn = conn

    def add(self, user_id, amount: Money, kind, created_at, transfer_id=None, note="") -> None:
        self.conn.execute(
            "INSERT INTO ledger (user_id, agorot, kind, transfer_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount.agorot, kind, transfer_id, note, _iso(created_at)),
        )

    def balance(self, user_id) -> Money:
        (agorot,) = self.conn.execute(
            "SELECT COALESCE(SUM(agorot), 0) FROM ledger WHERE user_id = ?", (user_id,)).fetchone()
        return Money(agorot)


class TransferRepo:
    def __init__(self, conn):
        self.conn = conn

    def add(self, sender_id, recipient_id, amount: Money, note, created_at) -> Transfer:
        cur = self.conn.execute(
            "INSERT INTO transfers (sender_id, recipient_id, agorot, note, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (sender_id, recipient_id, amount.agorot, note, Status.PENDING, _iso(created_at)),
        )
        return self.get(cur.lastrowid)

    def get(self, transfer_id) -> Transfer | None:
        row = self.conn.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
        return _transfer(row) if row else None

    def save_status(self, transfer: Transfer) -> None:
        self.conn.execute("UPDATE transfers SET status = ?, settled_at = ? WHERE id = ?",
                          (transfer.status, _iso(transfer.settled_at), transfer.id))

    def pending(self) -> list[Transfer]:
        return self._list("SELECT * FROM transfers WHERE status = ? ORDER BY id", (Status.PENDING,))

    def pending_to(self, user_id) -> list[Transfer]:
        return self._list("SELECT * FROM transfers WHERE recipient_id = ? AND status = ? ORDER BY id",
                          (user_id, Status.PENDING))

    def last_pending_of(self, sender_id) -> Transfer | None:
        row = self.conn.execute(
            "SELECT * FROM transfers WHERE sender_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
            (sender_id, Status.PENDING),
        ).fetchone()
        return _transfer(row) if row else None

    def accepted_to(self, user_id) -> list[Transfer]:
        return self._list("SELECT * FROM transfers WHERE recipient_id = ? AND status = ? ORDER BY id",
                          (user_id, Status.ACCEPTED))

    def accepted_from(self, user_id) -> list[Transfer]:
        return self._list("SELECT * FROM transfers WHERE sender_id = ? AND status = ? ORDER BY id",
                          (user_id, Status.ACCEPTED))

    def of(self, user_id) -> list[Transfer]:
        """Every transfer the user sent or received, in any status."""
        return self._list("SELECT * FROM transfers WHERE sender_id = ? OR recipient_id = ? ORDER BY id",
                          (user_id, user_id))

    def _list(self, sql, params) -> list[Transfer]:
        return [_transfer(row) for row in self.conn.execute(sql, params)]

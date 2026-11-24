"""All SQL of PeerPay (DESIGN.md §3, §8). Money columns hold agorot.

Every use case runs in one ``UnitOfWork``: one transaction that commits when the use case
succeeds and rolls back when it raises. The repositories inside it never commit by themselves.

The ledger is append-only and is the single source of truth for money: no balance is stored
anywhere, a balance is the sum of the user's ledger entries. Repositories return immutable
objects in lists, keep no caches, and write only what changed.
"""

import sqlite3
from datetime import datetime
from os import PathLike
from types import TracebackType
from typing import Literal, Self

from .models import Status, Transfer, User
from .money import Money
from .values import BankAccount, PhoneNumber

type DbPath = str | PathLike[str]
type LedgerKind = Literal["deposit", "transfer_out", "transfer_in", "refund", "adjustment"]

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


def create_schema(db_path: DbPath) -> None:
    conn = sqlite3.connect(db_path, timeout=5)

    try:
        conn.executescript(SCHEMA)

    finally:
        conn.close()


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds")


def _user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        phone=PhoneNumber(row["phone"]),
        name=row["name"],
        bank_account=BankAccount(row["bank_account"]),
        password_hash=row["password_hash"],
        last_login=datetime.fromisoformat(row["last_login"]) if row["last_login"] else None
    )


def _transfer(row: sqlite3.Row) -> Transfer:
    return Transfer(
        id=row["id"],
        sender_id=row["sender_id"],
        recipient_id=row["recipient_id"],
        amount=Money(row["agorot"]),
        note=row["note"],
        status=Status(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        settled_at=datetime.fromisoformat(row["settled_at"]) if row["settled_at"] else None
    )


class UserRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        phone: PhoneNumber,
        name: str,
        bank_account: BankAccount,
        password_hash: str
    ) -> User:
        row = self.conn.execute(
            "INSERT INTO users (phone, name, bank_account, password_hash) VALUES (?, ?, ?, ?)"
            " RETURNING *",
            (str(phone), name, str(bank_account), password_hash)
        ).fetchone()

        return _user(row)

    def get(self, user_id: int) -> User:
        """The user with this id. Ids come from the database itself, so a missing one is a bug."""

        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if row is None:
            raise LookupError(f"no user #{user_id}")

        return _user(row)

    def by_phone(self, phone: PhoneNumber) -> User | None:
        row = self.conn.execute("SELECT * FROM users WHERE phone = ?", (str(phone),)).fetchone()

        return _user(row) if row else None

    def touch_last_login(self, user_id: int, when: datetime) -> None:
        self.conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_iso(when), user_id))


class LedgerRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        user_id: int,
        amount: Money,
        *,
        kind: LedgerKind,
        created_at: datetime,
        transfer_id: int | None = None,
        note: str = ""
    ) -> None:
        self.conn.execute(
            "INSERT INTO ledger (user_id, agorot, kind, transfer_id, note, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount.agorot, kind, transfer_id, note, _iso(created_at))
        )

    def balance(self, user_id: int) -> Money:
        """Derived, never stored: the sum of the user's ledger entries."""

        (agorot,) = self.conn.execute(
            "SELECT COALESCE(SUM(agorot), 0) FROM ledger WHERE user_id = ?", (user_id,)
        ).fetchone()

        return Money(agorot)


class TransferRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        sender_id: int,
        recipient_id: int,
        amount: Money,
        *,
        note: str,
        created_at: datetime
    ) -> Transfer:
        row = self.conn.execute(
            "INSERT INTO transfers (sender_id, recipient_id, agorot, note, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
            (sender_id, recipient_id, amount.agorot, note, Status.PENDING, _iso(created_at))
        ).fetchone()

        return _transfer(row)

    def get(self, transfer_id: int) -> Transfer | None:
        row = self.conn.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()

        return _transfer(row) if row else None

    def save_status(self, transfer: Transfer) -> None:
        if transfer.settled_at is None:
            raise ValueError(f"transfer #{transfer.id} has no settlement time")

        self.conn.execute(
            "UPDATE transfers SET status = ?, settled_at = ? WHERE id = ?",
            (transfer.status, _iso(transfer.settled_at), transfer.id)
        )

    def pending(self) -> list[Transfer]:
        return self._list(
            "SELECT * FROM transfers WHERE status = ? ORDER BY id", (Status.PENDING,)
        )

    def pending_to(self, user_id: int) -> list[Transfer]:
        return self._list(
            "SELECT * FROM transfers WHERE recipient_id = ? AND status = ? ORDER BY id",
            (user_id, Status.PENDING)
        )

    def last_pending_of(self, sender_id: int) -> Transfer | None:
        """The sender's most recently created pending transfer (DESIGN.md §12).

        Ordered by id, the insertion order: timestamps can tie, ids can't (bug S3).
        """

        row = self.conn.execute(
            "SELECT * FROM transfers WHERE sender_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
            (sender_id, Status.PENDING)
        ).fetchone()

        return _transfer(row) if row else None

    def accepted_to(self, user_id: int) -> list[Transfer]:
        return self._list(
            "SELECT * FROM transfers WHERE recipient_id = ? AND status = ? ORDER BY id",
            (user_id, Status.ACCEPTED)
        )

    def accepted_from(self, user_id: int) -> list[Transfer]:
        return self._list(
            "SELECT * FROM transfers WHERE sender_id = ? AND status = ? ORDER BY id",
            (user_id, Status.ACCEPTED)
        )

    def of(self, user_id: int) -> list[Transfer]:
        """Every transfer the user sent or received, in any status."""

        return self._list(
            "SELECT * FROM transfers WHERE sender_id = ? OR recipient_id = ? ORDER BY id",
            (user_id, user_id)
        )

    def _list(self, sql: str, params: tuple[object, ...]) -> list[Transfer]:
        return [_transfer(row) for row in self.conn.execute(sql, params)]


class UnitOfWork:
    """``with UnitOfWork(path) as uow:`` runs one transaction, with the repositories used in it.

    ``BEGIN IMMEDIATE`` takes the write lock at the start, so a use case that reads and then
    writes can't interleave with another writer. Any exception rolls the whole use case back.
    """

    conn: sqlite3.Connection
    users: UserRepo
    ledger: LedgerRepo
    transfers: TransferRepo

    def __init__(self, db_path: DbPath) -> None:
        self._db_path = db_path

    def __enter__(self) -> Self:
        # isolation_level=None: sqlite3 must not open transactions by itself; we do it explicitly
        self.conn = sqlite3.connect(self._db_path, timeout=5, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("BEGIN IMMEDIATE")
        self.users = UserRepo(self.conn)
        self.ledger = LedgerRepo(self.conn)
        self.transfers = TransferRepo(self.conn)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None
    ) -> None:
        try:
            self.conn.execute("COMMIT" if exc_type is None else "ROLLBACK")

        finally:
            self.conn.close()

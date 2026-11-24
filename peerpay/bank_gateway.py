"""GIVEN: a mock of the bank. Not part of the exercise; treat it like a third-party library.

The bank moves money from a user's bank account into PeerPay's bank account. Every pull
is recorded in the ``bank_log`` table of the same (testing) database, so it can be
reconciled with the wallets (see check.py).
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from os import PathLike

_ACCOUNT_RE = re.compile(r"\d{2}-\d{3}-\d{6}")
MAX_PULL = Decimal("50000.00")


class BankError(Exception):
    """The bank refused the operation."""


@dataclass(frozen=True)
class Receipt:
    id: int
    account: str
    amount: Decimal                 # shekels


class MockBank:
    def __init__(self, db_path: str | PathLike[str]) -> None:
        self._db_path = db_path
        self._execute(
            "CREATE TABLE IF NOT EXISTS bank_log ("
            " id INTEGER PRIMARY KEY,"
            " account TEXT NOT NULL,"
            " shekels TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )

    def validate_account(self, account_number: str) -> bool:
        """Mock check: 'BB-BBB-AAAAAA' (bank-branch-account), digits summing to a multiple of 10."""

        if not _ACCOUNT_RE.fullmatch(account_number):
            return False

        return sum(int(c) for c in account_number if c.isdigit()) % 10 == 0

    def pull(self, account_number: str, amount: Decimal) -> Receipt:
        """Pulls ``amount`` SHEKELS, a Decimal with two decimal places, from a user's bank account.

        Returns a Receipt; ``Receipt.amount`` is the Decimal number of shekels that was pulled.
        """

        try:
            shekels = Decimal(amount).quantize(Decimal("0.01"))

        except (InvalidOperation, TypeError, ValueError):
            raise BankError(f"invalid amount: {amount!r}") from None

        if not self.validate_account(account_number):
            raise BankError(f"unknown bank account: {account_number}")

        if not Decimal("0") < shekels <= MAX_PULL:
            raise BankError(f"amount out of range: {shekels}")

        receipt_id = self._execute(
            "INSERT INTO bank_log (account, shekels, created_at) VALUES (?, ?, ?)",
            (account_number, str(shekels), datetime.now().isoformat())
        )

        return Receipt(receipt_id, account_number, shekels)

    def _execute(self, sql: str, params: tuple[object, ...] = ()) -> int:
        conn = sqlite3.connect(self._db_path, timeout=5)

        try:
            with conn:
                return conn.execute(sql, params).lastrowid or 0

        finally:
            conn.close()

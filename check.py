"""GIVEN: checks the invariants of a PeerPay database and prints every violation.

    python check.py              # checks testing.db
    python check.py other.db

Invariants (amounts in agorot):
  [1] each stored balance equals the sum of that user's ledger entries        (DESIGN.md §3)
  [2] wallets + pending transfers == deposits + support adjustments          (money is conserved)
  [3] the bank log (shekels × 100) equals the deposits in the ledger         (reconciliation, §1)
  [4] every stored phone number looks like 05XXXXXXXX                         (§2)
"""

import re
import sqlite3
import sys
from decimal import Decimal
from os import PathLike
from pathlib import Path

PHONE_RE = re.compile(r"05\d{8}")


def check(db_path: str | PathLike[str]) -> list[str]:
    """Returns one line per violated invariant; an empty list means the database is consistent."""

    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)

    try:
        return _problems(conn)

    finally:
        conn.close()


def _one(conn: sqlite3.Connection, sql: str) -> int:
    value: int = conn.execute(sql).fetchone()[0]

    return value


def _problems(conn: sqlite3.Connection) -> list[str]:
    problems: list[str] = []
    tables = {
        name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    if "accounts" in tables:                    # a stored balance exists: it must match the ledger
        rows = conn.execute(
            "SELECT a.user_id, a.balance,"
            " COALESCE((SELECT SUM(l.agorot) FROM ledger l WHERE l.user_id = a.user_id), 0)"
            " FROM accounts a ORDER BY a.user_id"
        )

        for user_id, balance, ledger_total in rows:
            if balance != ledger_total:
                problems.append(
                    f"[1] user {user_id}: stored balance {balance} != ledger total {ledger_total}"
                )

        wallets = _one(conn, "SELECT COALESCE(SUM(balance), 0) FROM accounts")

    else:                                       # the balance is derived from the ledger
        wallets = _one(conn, "SELECT COALESCE(SUM(agorot), 0) FROM ledger")

    pending = _one(
        conn, "SELECT COALESCE(SUM(agorot), 0) FROM transfers WHERE status = 'PENDING'"
    )
    deposits = _one(conn, "SELECT COALESCE(SUM(agorot), 0) FROM ledger WHERE kind = 'deposit'")
    adjustments = _one(
        conn, "SELECT COALESCE(SUM(agorot), 0) FROM ledger WHERE kind = 'adjustment'"
    )

    if wallets + pending != deposits + adjustments:
        problems.append(
            f"[2] wallets {wallets} + pending {pending} != deposits {deposits}"
            f" + adjustments {adjustments}"
        )

    if "bank_log" in tables:
        pulled = sum(
            (Decimal(shekels) for (shekels,) in conn.execute("SELECT shekels FROM bank_log")),
            Decimal(0)
        )

        if pulled * 100 != deposits:
            problems.append(
                f"[3] the bank pulled {pulled * 100} agorot,"
                f" but the ledger has {deposits} in deposits"
            )

    for user_id, phone in conn.execute("SELECT id, phone FROM users ORDER BY id"):
        if not PHONE_RE.fullmatch(phone):
            problems.append(f"[4] user {user_id}: stored phone number {phone!r} is not 05XXXXXXXX")

    return problems


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / "testing.db"

    if not Path(path).exists():
        raise SystemExit(f"{path} does not exist (run demo.py first)")

    found = check(path)

    for problem in found:
        print(problem)

    print(f"{len(found)} problem(s) found" if found else "OK: all invariants hold")
    sys.exit(1 if found else 0)

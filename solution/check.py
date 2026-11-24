"""GIVEN: checks the invariants of a PeerPay database and prints every violation.

    python check.py              # checks testing.db
    python check.py other.db

Invariants (amounts in agorot):
  [1] money is conserved: wallets + pending transfers == what the bank pulled × 100   (§1, §3)
  [2] every stored phone number looks like 05XXXXXXXX                               (§2, §7)
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


def _problems(conn: sqlite3.Connection) -> list[str]:
    problems: list[str] = []
    tables = {
        name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    wallets: int = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts").fetchone()[0]
    pending: int = conn.execute(
        "SELECT COALESCE(SUM(agorot), 0) FROM transfers WHERE status = 'PENDING'"
    ).fetchone()[0]
    pulled = Decimal(0)

    if "bank_log" in tables:
        pulled = sum(
            (Decimal(shekels) for (shekels,) in conn.execute("SELECT shekels FROM bank_log")),
            Decimal(0)
        )

    if wallets + pending != pulled * 100:
        problems.append(
            f"[1] wallets {wallets} + pending {pending} != {pulled * 100} pulled from the bank"
        )

    for user_id, phone in conn.execute("SELECT id, phone FROM users ORDER BY id"):
        if not PHONE_RE.fullmatch(phone):
            problems.append(f"[2] user {user_id}: stored phone number {phone!r} is not 05XXXXXXXX")

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

"""Support team tool: credit a user's wallet (a compensation, or a correction).

    python -m tools.support 0521234567 30.00 "compensation for ticket #812"
"""

import sqlite3
import sys
from pathlib import Path

from peerpay.money import parse_amount
from peerpay.validation import normalize_phone


def credit(db_path, phone, amount_text, reason):
    """Quick credit: one UPDATE, no need to start the whole app for it."""

    conn = sqlite3.connect(db_path)

    try:
        cur = conn.execute(
            "UPDATE accounts SET balance = balance + ?"
            " WHERE user_id = (SELECT id FROM users WHERE phone = ?)",
            (parse_amount(amount_text), normalize_phone(phone))
        )
        conn.commit()

    finally:
        conn.close()

    if cur.rowcount == 0:
        raise SystemExit(f"no user with phone number {phone}")

    print(f"credited {amount_text} to {phone} ({reason})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)

    credit(Path(__file__).resolve().parent.parent / "testing.db", *sys.argv[1:])

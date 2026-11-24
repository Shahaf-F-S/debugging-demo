"""Support team tool: credit a user's wallet (a compensation, or a correction).

    python -m tools.support 0521234567 30.00 "compensation for ticket #812"
"""
import sys
from pathlib import Path

from peerpay.api import PeerPayAPI
from peerpay.money import parse_amount
from peerpay.validation import normalize_phone


def credit(db_path, phone, amount_text, reason):
    api = PeerPayAPI(db_path)
    try:
        user = api.wallet.users.by_phone(normalize_phone(phone))
        if user is None:
            raise SystemExit(f"no user with phone number {phone}")
        api.wallet.adjust(user.id, parse_amount(amount_text), reason)
    finally:
        api.close()
    print(f"credited {amount_text} to {phone} ({reason})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    credit(Path(__file__).resolve().parent.parent / "testing.db", *sys.argv[1:])

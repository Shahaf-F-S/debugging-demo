"""Support team tool: credit a user's wallet (a compensation, or a correction).

    python -m tools.support 0521234567 30.00 "compensation for ticket #812"

It goes through the service like any other request (DESIGN.md §3, §8): one ledger entry, one transaction.
"""
import sys
from pathlib import Path

from peerpay.api import PeerPayAPI
from peerpay.money import Money
from peerpay.values import PhoneNumber


def credit(db_path, phone, amount_text, reason):
    api = PeerPayAPI(db_path)
    api.wallet.adjust(PhoneNumber.parse(phone), Money.parse(amount_text), reason)
    print(f"credited {amount_text} to {phone} ({reason})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    credit(Path(__file__).resolve().parent.parent / "testing.db", *sys.argv[1:])

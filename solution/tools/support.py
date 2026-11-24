"""The support team's tool: credit a user's wallet (a compensation, or a correction).

    python -m tools.support 0521234567 30.00 "compensation for ticket #812"

It goes through the service like any other request (DESIGN.md §3, §8): one ledger entry, in one
transaction, with nothing cached that could overwrite it (bug S4).
"""

import sys
from os import PathLike
from pathlib import Path

from peerpay.api import PeerPayAPI
from peerpay.errors import WalletError
from peerpay.money import Money
from peerpay.values import PhoneNumber


def credit(db_path: str | PathLike[str], phone: str, amount_text: str, reason: str) -> None:
    api = PeerPayAPI(db_path)

    try:
        api.wallet.adjust(PhoneNumber.parse(phone), Money.parse(amount_text), reason=reason)

    except WalletError as e:
        raise SystemExit(f"not credited: {e}") from None

    print(f"credited {amount_text} to {phone} ({reason})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)

    credit(Path(__file__).resolve().parent.parent / "testing.db", *sys.argv[1:])

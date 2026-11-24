"""GIVEN: a scripted day of PeerPay against testing.db, with test users and test passwords.

    python demo.py           # re-creates testing.db with the test users, then runs the day
    python demo.py --reuse   # keeps the existing testing.db and its users

Afterwards, run `python check.py` to check the database.
"""

import sys
from pathlib import Path
from typing import Any

from peerpay.api import PeerPayAPI

DB_PATH = Path(__file__).resolve().parent / "testing.db"

# phone, name, bank account (passes the mock bank's check), test password
TEST_USERS = [
    ("0547654321", "Dana", "12-345-678905", "dana-test-pass"),
    ("0521234567", "Yossi", "20-614-123452", "yossi-test-pass"),
    ("0509876543", "Noa", "31-102-555017", "noa-test-pass")
]


def fresh_db(path: Path = DB_PATH) -> None:
    """Deletes the database file and registers the test users."""

    path.unlink(missing_ok=True)
    api = PeerPayAPI(path)

    try:
        for phone, name, bank_account, password in TEST_USERS:
            response = api.register(phone, name, bank_account, password)

            if not response["ok"]:
                raise SystemExit(f"could not register {name}: {response['message']}")

    finally:
        api.close()


def show(title: str, response: dict[str, Any]) -> None:
    print(f"{title:<28} {response}")


def main(reuse: bool = False) -> None:
    if not reuse or not DB_PATH.exists():
        fresh_db()

    api = PeerPayAPI(DB_PATH)

    try:
        tokens: dict[str, str] = {}

        for phone, name, _bank, password in TEST_USERS:
            response = api.login(phone, password)
            show(f"{name} logs in", response)

            if not response["ok"]:
                return

            tokens[name] = response["token"]

        dana, yossi = tokens["Dana"], tokens["Yossi"]

        show("Dana tops up ₪100", api.top_up(dana, "100"))
        show("Dana sends Yossi ₪30", api.send(dana, "052-123-4567", "30", note="pizza"))
        first = api.pending(yossi)["pending"][0]
        show("Yossi's pending transfers", api.pending(yossi))
        show("Yossi accepts", api.accept(yossi, first["id"]))
        show("Dana sends Noa ₪20", api.send(dana, "050-987-6543", "20", note="cinema"))
        show("Nightly expiry job", api.run_expiry())

        for name in ("Dana", "Yossi", "Noa"):
            show(f"{name}'s balance", api.balance(tokens[name]))

    finally:
        api.close()

    print("\nNow run: python check.py")


if __name__ == "__main__":
    main(reuse="--reuse" in sys.argv)

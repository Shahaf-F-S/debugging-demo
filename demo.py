"""GIVEN: a scripted day of PeerPay, against testing.db.

    python demo.py           # re-creates testing.db (see seed.py), then runs the day
    python demo.py --reuse   # keeps the existing testing.db and its users

Afterwards, run `python check.py` to check the database.
"""

import sys
from typing import Any

from peerpay.api import PeerPayAPI
from seed import DB_PATH, TEST_USERS, fresh_db


def show(title: str, response: dict[str, Any]) -> None:
    print(f"{title:<34} {response}")


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

        dana, yossi, noa = tokens["Dana"], tokens["Yossi"], tokens["Noa"]

        show("Dana tops up ₪100", api.top_up(dana, "100"))
        show("Yossi tops up ₪50", api.top_up(yossi, "50"))
        show("Dana sends Yossi ₪30", api.send(dana, "052-123-4567", "30", note="pizza"))
        first = api.pending(yossi)["pending"][0]
        show("Yossi's pending transfers", api.pending(yossi))
        show("Yossi accepts", api.accept(yossi, first["id"]))
        show("Dana sends Noa ₪20", api.send(dana, "050-987-6543", "20", note="cinema"))
        show("Noa's pending transfers", api.pending(noa))
        show("Nightly expiry job", api.run_expiry())

        for name in ("Dana", "Yossi", "Noa"):
            show(f"{name}'s balance", api.balance(tokens[name]))

    finally:
        api.close()

    print("\nNow run: python check.py")


if __name__ == "__main__":
    main(reuse="--reuse" in sys.argv)

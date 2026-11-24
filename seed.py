"""GIVEN: the test users of the testing DB. These are test passwords for test accounts only.

    python seed.py      # re-creates testing.db with the users below (no money yet)
"""
from pathlib import Path

from peerpay.api import PeerPayAPI

DB_PATH = Path(__file__).resolve().parent / "testing.db"

# phone, name, bank account (passes the mock bank's check), test password
TEST_USERS = [
    ("0547654321", "Dana", "12-345-678905", "dana-test-pass"),
    ("0521234567", "Yossi", "20-614-123452", "yossi-test-pass"),
    ("0509876543", "Noa", "31-102-555017", "noa-test-pass"),
    ("0581112233", "Avi", "11-777-900008", "avi-test-pass"),
]


def fresh_db(path=DB_PATH):
    """Deletes the database file and registers the test users."""
    Path(path).unlink(missing_ok=True)
    api = PeerPayAPI(path)
    try:
        for phone, name, bank_account, password in TEST_USERS:
            response = api.register(phone, name, bank_account, password)
            if not response["ok"]:
                raise SystemExit(f"could not register {name}: {response['message']}")
    finally:
        api.close()


if __name__ == "__main__":
    fresh_db()
    print(f"{DB_PATH} re-created with {len(TEST_USERS)} test users")

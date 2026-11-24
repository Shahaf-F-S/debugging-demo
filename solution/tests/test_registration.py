import sqlite3
from pathlib import Path

from conftest import DANA
from peerpay.api import PeerPayAPI


def test_register_and_log_in(api: PeerPayAPI) -> None:
    assert api.register(*DANA)["ok"]
    assert api.login(DANA[0], DANA[3])["ok"]


def test_phone_number_can_be_typed_with_dashes(api: PeerPayAPI) -> None:
    assert api.register("054-765-4321", "Dana", DANA[2], DANA[3])["ok"]
    assert api.login("0547654321", DANA[3])["ok"]


def test_phone_number_can_register_only_once(api: PeerPayAPI) -> None:
    api.register(*DANA)
    response = api.register(DANA[0], "Another Dana", DANA[2], "another-pass")

    assert response["error"] == "invalid"


def test_invalid_bank_account_is_rejected(api: PeerPayAPI) -> None:
    response = api.register(DANA[0], DANA[1], "12-345-678900", DANA[3])

    assert response["error"] == "invalid"


def test_wrong_password_is_rejected(api: PeerPayAPI) -> None:
    api.register(*DANA)

    assert api.login(DANA[0], "not-my-password")["error"] == "login_failed"


def test_password_is_not_stored_in_plain_text(api: PeerPayAPI, db_path: Path) -> None:
    api.register(*DANA)
    conn = sqlite3.connect(db_path)

    try:
        (stored,) = conn.execute("SELECT password_hash FROM users").fetchone()

    finally:
        conn.close()

    assert DANA[3] not in stored

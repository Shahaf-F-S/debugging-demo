"""One test per planted bug (see docs/debugging-lab.md).

All of them pass on a correct PeerPay; each fails on the bug named in its name, and only on it.
They use the public API only, so the same file runs against the lab code and the solution.
Keep the C1 test LAST: the C1 bug leaks state into every later test of the same process.
"""

import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check import check
from conftest import DANA, YOSSI
from peerpay.api import PeerPayAPI
from peerpay.clock import FakeClock

ROOT = Path(__file__).resolve().parent.parent


def balance(api: PeerPayAPI, token: str) -> int:
    agorot: int = api.balance(token)["agorot"]

    return agorot


def test_c2_the_bank_is_charged_exactly_the_top_up(
    api: PeerPayAPI,
    tokens: dict[str, str],
    db_path: Path
) -> None:
    api.top_up(tokens["Dana"], "50")
    conn = sqlite3.connect(db_path)

    try:
        assert conn.execute("SELECT shekels FROM bank_log").fetchall() == [("50.00",)]

    finally:
        conn.close()


def test_c3_the_notifications_endpoint_shows_each_users_messages(
    api: PeerPayAPI,
    tokens: dict[str, str]
) -> None:
    api.top_up(tokens["Dana"], "100")
    api.send(tokens["Dana"], YOSSI[0], "30")
    shown = [
        message
        for token in tokens.values()
        for message in api.notifications(token)["messages"]
    ]

    assert api.notifier.outbox
    assert shown == [text for _, text in api.notifier.outbox]


def test_c3_the_notifications_endpoint_requires_a_login(api: PeerPayAPI) -> None:
    assert api.notifications("not-a-token")["error"] == "not_logged_in"


def test_c4_a_failed_send_changes_nothing(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    response = api.send(
        dana, YOSSI[0], "100",
        note="for the pizza, the drinks and the cinema " * 5
    )

    assert response["ok"] is False
    assert balance(api, dana) == 100_00
    assert api.pending(yossi)["pending"] == []


def test_c5_the_pending_list_never_changes_stored_data(
    api: PeerPayAPI,
    tokens: dict[str, str],
    db_path: Path
) -> None:
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.pending(yossi)

    assert api.login(DANA[0], DANA[3])["ok"]
    assert api.login(DANA[0], DANA[3])["ok"]
    assert [problem for problem in check(db_path) if problem.startswith("[2]")] == []


def test_s1_sending_to_an_unregistered_number_is_an_error(
    api: PeerPayAPI,
    tokens: dict[str, str]
) -> None:
    api.top_up(tokens["Dana"], "100")
    response = api.send(tokens["Dana"], "0500000000", "20")

    assert response["ok"] is False
    assert response["error"] == "unknown_recipient"


def test_s2_amounts_arrive_to_the_agora(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "19.99")

    assert api.pending(yossi)["pending"][0]["amount"] == "₪19.99"
    assert balance(api, dana) == 100_00 - 19_99


def test_s3_the_deadline_shown_is_the_real_deadline(
    api: PeerPayAPI,
    tokens: dict[str, str],
    clock: FakeClock
) -> None:
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.send(dana, YOSSI[0], "20")
    first, second = api.pending(yossi)["pending"]
    deadline = datetime.fromisoformat(first["expires_at"])
    clock.advance(seconds=(deadline - clock()).total_seconds() - 60)

    assert api.accept(yossi, first["id"])["ok"], "one minute before the deadline"

    clock.advance(minutes=2)

    assert api.accept(yossi, second["id"])["error"] == "expired", "one minute after it"


def test_h1_users_can_log_in_after_a_restart(
    api: PeerPayAPI,
    tokens: dict[str, str],
    db_path: Path
) -> None:
    """A restart is a new Python process."""

    script = (
        "import sys; from peerpay.api import PeerPayAPI; "
        "api = PeerPayAPI(sys.argv[1]); ok = api.login(sys.argv[2], sys.argv[3])['ok']; "
        "api.close(); sys.exit(0 if ok else 1)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(db_path), DANA[0], DANA[3]],
        cwd=ROOT
    )

    assert result.returncode == 0


def test_c1_one_invalid_request_does_not_poison_the_next(
    api: PeerPayAPI,
    tokens: dict[str, str]
) -> None:
    dana = tokens["Dana"]
    api.top_up(dana, "100")

    assert api.send(dana, "12345", "10")["error"] == "invalid"
    assert api.send(dana, YOSSI[0], "10")["ok"]

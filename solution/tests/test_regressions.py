"""TEACHER ONLY: one test per planted bug (see docs/debugging-lab.md).

All of them pass on a correct PeerPay; each fails on the bug named in its name.
Keep test_c1 LAST: the C1 bug leaks state into every later test in the same process.
"""
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check import check
from conftest import DANA, YOSSI
from tools import support

ROOT = Path(__file__).resolve().parent.parent


def balance(api, token):
    return api.balance(token)["agorot"]


def violations(db_path, *invariants):
    """check.py problems, limited to the given invariant numbers (so other bugs don't interfere)."""
    return [p for p in check(db_path) if p.startswith(tuple(f"[{i}]" for i in invariants))]


def test_c2_statement_total_includes_every_received_transfer(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.send(dana, YOSSI[0], "20")
    for item in api.pending(yossi)["pending"]:
        api.accept(yossi, item["id"])
    statement = api.statement(yossi)
    assert statement["received_count"] == 2
    assert statement["received_total"] == "₪50.00"


def test_c3_sending_to_an_unregistered_number_is_an_error(api, tokens):
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    response = api.send(dana, "0500000000", "20")
    assert response["ok"] is False
    assert response["error"] == "unknown_recipient"


def test_c4_the_deadline_shown_is_the_real_deadline(api, tokens, clock):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.send(dana, YOSSI[0], "20")
    first, second = api.pending(yossi)["pending"]
    deadline = datetime.fromisoformat(first["expires_at"])
    clock.advance(seconds=(deadline - clock()).total_seconds() - 60)       # one minute before
    assert api.accept(yossi, first["id"])["ok"]
    clock.advance(minutes=2)                                                # one minute after
    assert api.accept(yossi, second["id"])["error"] == "expired"


def test_c5_a_failed_send_changes_nothing(api, tokens, db_path):
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    response = api.send(dana, YOSSI[0], "100", note="for the pizza, the drinks and the cinema " * 5)
    assert response["ok"] is False
    assert balance(api, dana) == 100_00
    assert violations(db_path, 1, 2) == []


def test_c6_a_statement_never_changes_stored_data(api, tokens, db_path):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.accept(yossi, api.pending(yossi)["pending"][0]["id"])
    api.statement(dana)
    assert api.login(YOSSI[0], YOSSI[3])["ok"]
    assert api.login(YOSSI[0], YOSSI[3])["ok"]
    assert violations(db_path, 4) == []


def test_s1_each_event_uses_its_own_template(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    assert api.notifications(yossi)["messages"] == [
        "You received ₪30.00 (transfer #1). Accept it within 30 days."]
    api.accept(yossi, api.pending(yossi)["pending"][0]["id"])
    assert api.notifications(dana)["messages"] == ["Your transfer #1 of ₪30.00 was accepted."]


def test_s2_amounts_arrive_to_the_agora(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "19.99")
    assert api.pending(yossi)["pending"][0]["amount"] == "₪19.99"
    assert balance(api, dana) == 100_00 - 19_99


def test_s3_a_new_transfer_is_not_expired_on_a_long_running_server(api, tokens, clock):
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    clock.advance(days=35)                    # the server has been up for five weeks
    api.send(dana, YOSSI[0], "20")
    assert api.run_expiry()["expired"] == 0


def test_s3_cancel_last_cancels_the_most_recent_transfer(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "10", note="older")
    api.send(dana, YOSSI[0], "20", note="newer")
    api.cancel_last(dana)
    assert [item["note"] for item in api.pending(yossi)["pending"]] == ["older"]


def test_s4_a_support_credit_survives_the_next_transfer(api, tokens, db_path):
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "10")
    support.credit(db_path, DANA[0], "30", "compensation")
    api.send(dana, YOSSI[0], "10")
    assert balance(api, dana) == 100_00 - 10_00 - 10_00 + 30_00
    assert violations(db_path, 1, 2) == []


def test_s5_the_bank_is_charged_exactly_the_top_up(api, tokens, db_path):
    api.top_up(tokens["Dana"], "50")
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT shekels FROM bank_log").fetchall() == [("50.00",)]
    finally:
        conn.close()
    assert violations(db_path, 3) == []


def test_h1_users_can_log_in_after_a_restart(api, tokens, db_path):
    """A restart is a new Python process."""
    script = ("import sys; from peerpay.api import PeerPayAPI; "
              "api = PeerPayAPI(sys.argv[1]); ok = api.login(sys.argv[2], sys.argv[3])['ok']; "
              "api.close(); sys.exit(0 if ok else 1)")
    result = subprocess.run([sys.executable, "-c", script, str(db_path), DANA[0], DANA[3]], cwd=ROOT)
    assert result.returncode == 0


def test_c1_one_invalid_request_does_not_poison_the_next(api, tokens):
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    assert api.send(dana, "12345", "10")["error"] == "invalid"
    assert api.send(dana, YOSSI[0], "10")["ok"]

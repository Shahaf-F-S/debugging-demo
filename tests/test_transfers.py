from conftest import DANA, NOA, YOSSI


def balance(api, token):
    return api.balance(token)["agorot"]


def test_top_up_increases_balance(api, tokens):
    assert api.top_up(tokens["Dana"], "100")["ok"]
    assert balance(api, tokens["Dana"]) == 100_00


def test_sent_money_is_held_until_accepted(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    assert api.send(dana, YOSSI[0], "30", note="pizza")["ok"]
    assert balance(api, dana) == 70_00
    assert balance(api, yossi) == 0
    (item,) = api.pending(yossi)["pending"]
    assert (item["from"], item["amount"], item["note"]) == ("Dana", "₪30.00", "pizza")


def test_accept_credits_the_recipient(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    assert api.accept(yossi, api.pending(yossi)["pending"][0]["id"])["ok"]
    assert balance(api, yossi) == 30_00
    assert api.pending(yossi)["pending"] == []


def test_decline_refunds_the_sender(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    assert api.decline(yossi, api.pending(yossi)["pending"][0]["id"])["ok"]
    assert balance(api, dana) == 100_00


def test_sender_can_cancel_a_pending_transfer(api, tokens):
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    assert api.cancel_last(dana)["ok"]
    assert balance(api, dana) == 100_00
    assert api.pending(yossi)["pending"] == []


def test_transfer_expires_after_30_days(api, tokens, clock):
    dana, noa = tokens["Dana"], tokens["Noa"]
    api.top_up(dana, "100")
    api.send(dana, NOA[0], "20")
    clock.advance(days=31)
    assert api.run_expiry()["expired"] == 1
    assert balance(api, dana) == 100_00
    assert api.pending(noa)["pending"] == []


def test_transfer_is_still_pending_after_29_days(api, tokens, clock):
    dana, noa = tokens["Dana"], tokens["Noa"]
    api.top_up(dana, "100")
    api.send(dana, NOA[0], "20")
    clock.advance(days=29)
    assert api.run_expiry()["expired"] == 0
    assert len(api.pending(noa)["pending"]) == 1


def test_cannot_send_more_than_the_balance(api, tokens):
    api.top_up(tokens["Dana"], "10")
    assert api.send(tokens["Dana"], YOSSI[0], "20")["error"] == "insufficient_funds"


def test_cannot_send_to_yourself(api, tokens):
    api.top_up(tokens["Dana"], "100")
    assert api.send(tokens["Dana"], DANA[0], "20")["error"] == "not_allowed"


def test_cannot_accept_someone_elses_transfer(api, tokens):
    dana, yossi, noa = tokens["Dana"], tokens["Yossi"], tokens["Noa"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    transfer_id = api.pending(yossi)["pending"][0]["id"]
    assert api.accept(noa, transfer_id)["error"] == "not_found"

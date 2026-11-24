from conftest import YOSSI
from peerpay.api import PeerPayAPI


def test_statement_counts_received_transfers(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    dana, yossi = tokens["Dana"], tokens["Yossi"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    api.accept(yossi, api.pending(yossi)["pending"][0]["id"])
    statement = api.statement(yossi)

    assert statement["ok"]
    assert statement["received_count"] == 1


def test_statement_masks_phone_numbers(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    dana = tokens["Dana"]
    api.top_up(dana, "100")
    api.send(dana, YOSSI[0], "30")
    (line,) = api.statement(dana)["lines"]

    assert "Yossi (05*-***-4567)" in line

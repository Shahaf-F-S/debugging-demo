from peerpay.api import PeerPayAPI


def test_send_rejects_an_invalid_phone_number(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    api.top_up(tokens["Dana"], "100")
    response = api.send(tokens["Dana"], "12345", "10")

    assert response["error"] == "invalid"
    assert "invalid phone number" in response["message"]


def test_send_rejects_a_zero_amount(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    api.top_up(tokens["Dana"], "100")
    response = api.send(tokens["Dana"], "0521234567", "0")

    assert response["error"] == "invalid"
    assert "amount must be positive" in response["message"]


def test_one_request_reports_all_of_its_problems(api: PeerPayAPI, tokens: dict[str, str]) -> None:
    response = api.send(tokens["Dana"], "12345", "0", note="x" * 200)

    assert response["error"] == "invalid"
    assert response["message"] == (
        "invalid phone number; amount must be positive; note is longer than 140 characters"
    )

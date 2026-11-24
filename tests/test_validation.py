def test_send_rejects_an_invalid_phone_number(api, tokens):
    api.top_up(tokens["Dana"], "100")
    response = api.send(tokens["Dana"], "12345", "10")

    assert response["error"] == "invalid"
    assert "invalid phone number" in response["message"]


def test_send_rejects_a_zero_amount(api, tokens):
    api.top_up(tokens["Dana"], "100")
    response = api.send(tokens["Dana"], "0521234567", "0")

    assert response["error"] == "invalid"
    assert "amount must be positive" in response["message"]

from conftest import YOSSI


def test_a_notification_is_pushed_when_money_is_sent(api, tokens):
    api.top_up(tokens["Dana"], "100")
    api.send(tokens["Dana"], YOSSI[0], "30")

    assert len(api.notifier.outbox) == 1

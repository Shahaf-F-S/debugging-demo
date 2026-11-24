import pytest

from peerpay.errors import ValidationError
from peerpay.money import format_amount, parse_amount


def test_parse_whole_shekels():
    assert parse_amount("50") == 5000


def test_parse_half_shekels():
    assert parse_amount("12.5") == 1250


def test_parse_rejects_text():
    with pytest.raises(ValidationError):
        parse_amount("fifty")


def test_format_amount():
    assert format_amount(1999) == "₪19.99"
    assert format_amount(123456) == "₪1,234.56"

from decimal import Decimal

import pytest

from peerpay.errors import ValidationError
from peerpay.money import ZERO, Money


def test_parse_whole_shekels() -> None:
    assert Money.parse("50") == Money(5000)


def test_parse_half_shekels() -> None:
    assert Money.parse("12.5") == Money(1250)


def test_parse_is_exact() -> None:
    assert Money.parse("19.99") == Money(1999)
    assert Money.parse("0.29") == Money(29)


def test_parse_rejects_text_and_extra_decimals() -> None:
    for text in ("fifty", "19.999", "nan"):
        with pytest.raises(ValidationError):
            Money.parse(text)


def test_money_refuses_floats() -> None:
    with pytest.raises(TypeError):
        Money(19.99)        # type: ignore[arg-type]  # mypy catches it too; this checks runtime


def test_money_does_not_mix_with_plain_numbers() -> None:
    with pytest.raises(TypeError):
        Money(100) + 5      # type: ignore[operator]  # mypy catches it too; this checks runtime


def test_arithmetic_and_comparison() -> None:
    assert Money(1000) - Money(250) == Money(750)
    assert Money(100) < Money(200)
    assert sum([Money(100), Money(250)], ZERO) == Money(350)


def test_conversion_to_shekels() -> None:
    assert Money(5000).to_decimal() == Decimal("50")
    assert Money.from_decimal(Decimal("50.00")) == Money(5000)


def test_format() -> None:
    assert str(Money(1999)) == "₪19.99"
    assert str(Money(123456)) == "₪1,234.56"

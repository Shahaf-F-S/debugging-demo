"""Money helpers. Inside PeerPay, money is an int number of agorot (DESIGN.md §1)."""
from decimal import Decimal, InvalidOperation

from .errors import ValidationError


def parse_amount(text) -> int:
    """'19.99' → 1999 agorot. At most two decimal places."""
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        raise ValidationError([f"not an amount: {text!r}"]) from None
    if not value.is_finite() or value.as_tuple().exponent < -2:
        raise ValidationError([f"not an amount: {text!r}"])
    return int(value * 100)


def format_amount(agorot: int) -> str:
    """1999 → '₪19.99'"""
    sign = "-" if agorot < 0 else ""
    return f"{sign}₪{abs(agorot) // 100:,}.{abs(agorot) % 100:02d}"

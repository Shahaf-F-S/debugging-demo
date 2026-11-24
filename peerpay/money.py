"""Money helpers. Inside PeerPay, money is an int number of agorot (DESIGN.md §1)."""
from .errors import ValidationError


def parse_amount(text) -> int:
    """'19.99' → 1999 agorot."""
    try:
        return int(float(text) * 100)
    except ValueError:
        raise ValidationError([f"not an amount: {text!r}"]) from None


def format_amount(agorot: int) -> str:
    """1999 → '₪19.99'"""
    sign = "-" if agorot < 0 else ""
    return f"{sign}₪{abs(agorot) // 100:,}.{abs(agorot) % 100:02d}"

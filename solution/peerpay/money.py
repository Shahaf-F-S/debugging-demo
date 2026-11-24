"""Money as a value object (DESIGN.md §1): an exact int number of agorot, in one currency."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import total_ordering

from .errors import ValidationError


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    agorot: int
    currency: str = "ILS"

    def __post_init__(self):
        if type(self.agorot) is not int:            # rejects float and bool, not only str
            raise TypeError(f"Money needs an int number of agorot, got {type(self.agorot).__name__}")

    @classmethod
    def parse(cls, text) -> "Money":
        """The only way text becomes money: '19.99' → Money(1999). At most two decimal places."""
        try:
            value = Decimal(str(text).strip())
        except InvalidOperation:
            raise ValidationError([f"not an amount: {text!r}"]) from None
        if not value.is_finite() or value.as_tuple().exponent < -2:
            raise ValidationError([f"not an amount: {text!r}"])
        return cls(int(value * 100))

    @classmethod
    def from_decimal(cls, shekels: Decimal) -> "Money":
        return cls.parse(str(shekels))

    def to_decimal(self) -> Decimal:
        """Money(1999) → Decimal('19.99') shekels."""
        return Decimal(self.agorot) / 100

    def is_positive(self) -> bool:
        return self.agorot > 0

    def __add__(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self.agorot + other.agorot, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self.agorot - other.agorot, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.agorot, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._check_same_currency(other)
        return self.agorot < other.agorot

    def __str__(self) -> str:
        sign = "-" if self.agorot < 0 else ""
        whole, agorot = divmod(abs(self.agorot), 100)
        return f"{sign}₪{whole:,}.{agorot:02d}"

    def _check_same_currency(self, other):
        if not isinstance(other, Money):
            raise TypeError(f"cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise TypeError(f"cannot combine {self.currency} with {other.currency}")


ZERO = Money(0)

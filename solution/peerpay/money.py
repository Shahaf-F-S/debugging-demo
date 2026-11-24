"""Money as a value object (DESIGN.md §1).

A ``Money`` is an exact, immutable int number of agorot in one currency. It refuses floats, is
created from text in exactly one way (``Money.parse``), and only combines with Money of the same
currency. That makes the float family (bug S2) and the unit family (bug S5) hard to write.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from functools import total_ordering
from typing import Self

from .errors import ValidationError


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount of money: ``Money(1999)`` is ₪19.99."""

    agorot: int
    currency: str = "ILS"

    def __post_init__(self) -> None:
        # type() and not isinstance(): bool is a subclass of int, and True is not an amount
        if type(self.agorot) is not int:
            raise TypeError(
                f"Money needs an int number of agorot, not {type(self.agorot).__name__}"
            )

    @classmethod
    def parse(cls, text: str) -> Self:
        """The only way text becomes money: ``Money.parse("19.99") == Money(1999)``.

        Raises ValidationError for anything that isn't a number with at most two decimal places.
        """

        try:
            value = Decimal(text.strip())

        except InvalidOperation:
            raise ValidationError([f"not an amount: {text!r}"]) from None

        exponent = value.as_tuple().exponent

        if not value.is_finite() or not isinstance(exponent, int) or exponent < -2:
            raise ValidationError([f"not an amount: {text!r}"])

        return cls(int(value * 100))

    @classmethod
    def from_decimal(cls, shekels: Decimal) -> Self:
        """``Money.from_decimal(Decimal("50.00")) == Money(5000)``."""

        return cls.parse(str(shekels))

    def to_decimal(self) -> Decimal:
        """``Money(1999).to_decimal() == Decimal("19.99")``, in shekels."""

        return Decimal(self.agorot) / 100

    def is_positive(self) -> bool:
        return self.agorot > 0

    def __add__(self, other: Self) -> Self:
        self._check_same_currency(other)

        return replace(self, agorot=self.agorot + other.agorot)

    def __sub__(self, other: Self) -> Self:
        self._check_same_currency(other)

        return replace(self, agorot=self.agorot - other.agorot)

    def __neg__(self) -> Self:
        return replace(self, agorot=-self.agorot)

    def __lt__(self, other: Self) -> bool:
        self._check_same_currency(other)

        return self.agorot < other.agorot

    def __str__(self) -> str:
        sign = "-" if self.agorot < 0 else ""
        whole, agorot = divmod(abs(self.agorot), 100)

        return f"{sign}₪{whole:,}.{agorot:02d}"

    def _check_same_currency(self, other: object) -> None:
        # The type hints already say Money; this also stops callers that run no type checker.
        if not isinstance(other, Money):
            raise TypeError(f"cannot combine Money with {type(other).__name__}")

        if other.currency != self.currency:
            raise TypeError(f"cannot combine {self.currency} with {other.currency}")


ZERO = Money(0)

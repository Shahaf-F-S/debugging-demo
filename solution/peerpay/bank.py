"""The adapter between PeerPay and the bank (DESIGN.md §1).

PeerPay speaks Money; the bank speaks Decimal shekels. This module is the only code that knows
both, so no unit gets lost between them (bug C2).
"""

from decimal import Decimal
from typing import Protocol

from .bank_gateway import BankError, Receipt
from .errors import TopUpFailed
from .money import Money
from .values import BankAccount


class BankGateway(Protocol):
    """What PeerPay needs from a bank: ``bank_gateway.MockBank`` in this project."""

    def validate_account(self, account_number: str) -> bool: ...

    def pull(self, account_number: str, amount: Decimal) -> Receipt: ...


class BankAdapter:
    def __init__(self, gateway: BankGateway) -> None:
        self._gateway = gateway

    def validate_account(self, account_number: str) -> bool:
        return self._gateway.validate_account(account_number)

    def pull(self, account: BankAccount, amount: Money) -> Money:
        """Pulls ``amount`` from the user's bank account; returns what the bank says it pulled."""

        try:
            receipt = self._gateway.pull(str(account), amount.to_decimal())

        except BankError as e:
            raise TopUpFailed(str(e)) from e

        return Money.from_decimal(receipt.amount)

"""Adapter for the bank gateway: the only code that knows the bank speaks Decimal shekels (DESIGN.md §1)."""
from .bank_gateway import BankError
from .errors import TopUpFailed
from .money import Money


class BankAdapter:
    def __init__(self, gateway):
        self._gateway = gateway

    def validate_account(self, account_number: str) -> bool:
        return self._gateway.validate_account(account_number)

    def pull(self, account_number: str, amount: Money) -> Money:
        """Pulls ``amount`` from the user's bank account; returns what the bank says it pulled."""
        try:
            receipt = self._gateway.pull(account_number, amount.to_decimal())
        except BankError as e:
            raise TopUpFailed(str(e)) from e
        return Money.from_decimal(receipt.amount)

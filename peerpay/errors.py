"""Everything that can go wrong in PeerPay; the API turns these into error responses (§5)."""


class WalletError(Exception):
    code = "error"


class ValidationError(WalletError):
    code = "invalid"

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class LoginFailed(WalletError):
    code = "login_failed"

    def __init__(self):
        super().__init__("wrong phone number or password")


class NotLoggedIn(WalletError):
    code = "not_logged_in"

    def __init__(self):
        super().__init__("please log in")


class UnknownRecipient(WalletError):
    code = "unknown_recipient"

    def __init__(self, phone):
        super().__init__(f"no PeerPay user has the phone number {phone}")


class InsufficientFunds(WalletError):
    code = "insufficient_funds"

    def __init__(self):
        super().__init__("not enough money in your wallet")


class NotAllowed(WalletError):
    code = "not_allowed"


class TransferNotFound(WalletError):
    code = "not_found"

    def __init__(self, transfer_id):
        super().__init__(f"you have no pending transfer #{transfer_id}")


class TransferExpired(WalletError):
    code = "expired"

    def __init__(self, transfer_id):
        super().__init__(f"transfer #{transfer_id} has expired")


class TopUpFailed(WalletError):
    code = "top_up_failed"

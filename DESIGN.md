# PeerPay: design

PeerPay is the backend of an app for sending money to friends. Users register with a phone number, a bank
account and a password. They top up their wallet from their bank account and send money to any other user by
phone number. The money is **held** until the recipient accepts it; a transfer that is not accepted within 30
days **expires**, and the sender gets the money back.

This document is the source of truth: when the code and this document disagree, the code is wrong.

## Modules

| Module | Responsibility |
|---|---|
| `peerpay/api.py` | One method per request. Turns text input into values, and results or errors into dicts. |
| `peerpay/auth.py` | Registration, login, password hashing. |
| `peerpay/service.py` | The use cases: top up, send, pending list, accept, expire. |
| `peerpay/repository.py` | All SQL. |
| `peerpay/validation.py` | Input checks and phone-number helpers. |
| `peerpay/money.py` | Parsing and formatting amounts. |
| `peerpay/models.py` | The data: users, accounts, transfers. |
| `peerpay/notifier.py` | Push notifications (kept in memory). |
| `peerpay/errors.py` | Every error the service can raise. |

**Given** (part of the environment, not of the exercise, and not to be changed):

| File | What it is |
|---|---|
| `peerpay/bank_gateway.py` | A mock of the bank. `pull(account, amount)` takes a `Decimal` number of **shekels** and records every pull in the `bank_log` table. |
| `peerpay/clock.py` | `SystemClock`, and the `FakeClock` used in tests (`clock.advance(days=31)`). |
| `check.py` | Checks the invariants of a database and prints every violation. |
| `demo.py` | Creates the testing DB with test users, and runs a scripted day against it. |

The database is a **testing database** (`testing.db`), not production data.

## Rules

- **§1 Money.** Inside PeerPay, money is an `int` number of **agorot** (ILS only). Text is parsed exactly once,
  at the API, and may have at most 2 decimal places; amounts are formatted as ₪ only in responses. The bank
  speaks `Decimal` shekels; converting to and from it happens in exactly one place.
- **§2 Users.** A user is identified by a phone number, stored as `05XXXXXXXX` and unique. The bank account is
  checked with the bank's `validate_account()`. Passwords are hashed with PBKDF2-HMAC-SHA256, with a
  **per-user random salt stored together with the hash**, and compared in constant time.
- **§3 Send.** First validate everything: the amount is positive and not more than the balance, the recipient
  exists and is not the sender, and the note has at most 140 characters. Then, **atomically**, debit the
  sender and create a PENDING transfer. Held money is in no one's balance until the transfer is settled.
- **§4 Accept and expire.** The recipient may accept a PENDING transfer **until 30 days after it was created**
  (`EXPIRY = timedelta(days=30)`, defined once). Accepting credits the recipient. The nightly job expires
  older pending transfers and refunds their senders. Each of these is atomic, and a settled transfer never
  changes again.
- **§5 Errors.** The service reports a failure only by raising a subclass of `WalletError`; it never prints and
  never returns a flag. The API turns every error into `{"ok": False, "error": <code>, "message": <text>}`.
- **§6 Independence.** Requests are independent: nothing from one request or one user affects another.
- **§7 Display.** Showing data never changes stored data. The pending list shows the sender's phone number
  masked (`05*-***-4321`).
- **§8 Notifications.** A sent, accepted or expired transfer notifies the user it concerns. A logged-in user's
  notification list shows exactly the notifications sent to them; without a valid login it is an error.
- **§9 Types.** Every function and method has complete, modern type hints, and `mypy --strict` reports no
  errors. A value of the wrong type is a bug the type checker finds, not the user.

## Worked example

| Step | Dana | Yossi | Noa | Pending | Bank log |
|---|---|---|---|---|---|
| Dana tops up ₪100 | ₪100.00 | ₪0.00 | ₪0.00 | — | 100.00 |
| Dana sends Yossi ₪30 | ₪70.00 | ₪0.00 | ₪0.00 | #1 ₪30 | |
| Yossi accepts (day 12) | ₪70.00 | ₪30.00 | ₪0.00 | — | |
| Dana sends Noa ₪20 | ₪50.00 | ₪30.00 | ₪0.00 | #2 ₪20 | |
| Day 30: the nightly job | ₪70.00 | ₪30.00 | ₪0.00 | — | |

Check: 7000 + 3000 + 0 (wallets) + 0 (pending) = 10000 = 100.00 × 100 (what the bank pulled).

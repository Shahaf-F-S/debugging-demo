# Debugging & Refactoring Lab: "PeerPay" (teacher's guide)

**This is the answer key.** It is in the same public repository as the lab, so students can open it.

A single 90-minute lesson, with a 45-minute variant. Students get the backend of a small app for sending money
between friends: code that *mostly works*, a design document (`DESIGN.md`) that says what it should do, and 8
tickets (`TICKETS.md`). Every bug comes from a Python programming-method mistake or a design decision. In the
second half, students apply one of five pattern cards: currency, validation, transactions, DB usage, and type
hints.

- **Technology:** Python 3.12+ and SQLite only. The "API" is a class of plain methods that return dicts
  (`peerpay.api.PeerPayAPI`), so there is no web framework, GUI, networking or threads.
- **Scope:** register (phone, mock-validated bank account, real password), log in, top up through the given
  bank, balance, send by phone, pending list, accept, and the 30-day expiry. A minimal notifier hosts bug C3.
- **No type hints in the lab.** The exercise functions are unannotated; only the dataclass fields are typed,
  because dataclasses need it. The given modules (the bank, the clock, `check.py`) are typed like a library.
- **Size:**

  | | Lab | Solution |
  |---|---|---|
  | Exercise code | ~680 lines in 9 modules (~480 non-blank) | ~1,100 lines (~790 non-blank) |
  | Given helpers | ~270 lines | same |
  | Tests | 21 weak tests | 38 tests (10 regression tests) |
- **Code style** (all code, not a lesson topic):
  - **Blank lines** around blocks; before `return`, `raise` and `yield`; and between `if`/`elif`/`else` and
    `try`/`except`/`finally`.
  - **Wrapping:** lines of at most 100 characters. A wrapped call, definition or literal is indented one level,
    and its closing bracket lines up with the line that opened it.
  - **Arguments:** keyword arguments for a call's extra parameters, and one parameter per line in long definitions.

Everything below was run on Python 3.15.2 on this machine.

---

## 0. The repository, and what was verified

| Where | What it is |
|---|---|
| repository root | **The lab**: the buggy code, `DESIGN.md`, `TICKETS.md`, the weak tests, the given tools. |
| `docs/debugging-lab.md` | This guide. |
| `solution/` | The **reference solution**: all bugs fixed and the five cards applied, full type hints (`mypy --strict` passes), docstrings, and every test including `tests/test_regressions.py`. Run `python -m pytest` and `python -m mypy` inside it. |
| tag `naive` | The slim lab before any bug was planted (correct, untyped), with its regression tests. |
| history after `naive` | One commit per bug (`bug(C1): …` … `bug(H1): …`, each message explains its bug), then the removal of the regression tests, then the solution and these documents. Earlier history holds the previous, bigger version of the lab. |

**Verified**

- **Solution:** all 38 tests pass, and `mypy --strict` reports no issues in its 23 files.
- **Lab:** all 10 regression tests fail, covering the 9 bugs, while the 21 weak tests pass.
- **Independence:** each bug's minimal fix (section 2), applied alone to the lab, turns exactly that bug's
  tests green. Each test ran in its own process, because C1 leaks state across tests.
- **The type checker:** in the lab, `python -m mypy peerpay` reports nothing. After annotating a handful of
  signatures it reports C3, C2 and S1 (details in each entry).
- **Bisect:** `git bisect start --first-parent HEAD naive` with an S3 test finds `bug(S3)`.

**To run the regression tests against the lab** (from the repository root, in PowerShell):

```powershell
Copy-Item solution\tests\test_regressions.py tests\
python -m pytest tests\test_regressions.py
Remove-Item tests\test_regressions.py
```

The C1 test runs last on purpose: once C1 has polluted the shared list, every later send in that process fails.

---

## 1. The lab

```text
peerpay/
├── api.py            PeerPayAPI: register, login, balance, top_up, send, pending, accept,
│                     notifications, run_expiry → {"ok": ...}
├── auth.py           register, login, password hashing
├── service.py        WalletService: top_up, send, pending, accept, expire_pending
├── repository.py     the schema, UserDirectory (caches users), Repository (accounts, transfers)
├── validation.py     validate_send, validate_registration, normalize_phone, mask_phone
├── money.py          parse_amount, format_amount
├── models.py         User, Account, Transfer (mutable dataclasses), status strings
├── notifier.py       Notifier: push, messages_for
├── errors.py         WalletError and its subclasses
├── bank_gateway.py   GIVEN: MockBank.validate_account(), MockBank.pull(account, amount: Decimal shekels)
└── clock.py          GIVEN: SystemClock, FakeClock(start=now).advance(days=…)
check.py              GIVEN: [1] wallets + pending == bank log × 100; [2] phone numbers well-formed
demo.py               GIVEN: the test users, fresh_db(), a scripted day (--reuse keeps the DB)
```

**In the briefing** (all intended):
- **`python demo.py`** runs cleanly and the balances look right.
- **`python check.py`** already reports `[1] wallets 8000 + pending 2000 != 1000000.00 pulled from the bank`.
  That's C2, a teaser: note it and move on.
- **`python -m mypy peerpay`** says "no issues". Ask why: it skips every function without type hints.
- **`python demo.py --reuse`** fails every login. That's H1; keep it for the debrief.

**Why the weak tests are green:**

| Test weakness | Bug it hides |
|---|---|
| The invalid-input tests are in `test_validation.py`, which runs last | C1 |
| The top-up test checks the wallet, not the bank log | C2 |
| The notification test reads `api.notifier.outbox`, never the endpoint | C3 |
| Notes in tests are short | C4 |
| No test logs in a second time | C5 |
| No test sends to a well-formed but unregistered number | S1 |
| Amounts are whole shekels | S2 |
| Accept is tried on day 1 only | S3 |
| Everything runs in one process | H1 |

---

## 2. The bugs

There are **5 core** bugs (everyone), **3 stretch** bugs, and **1 hidden** bug with no ticket.

### Core

#### C1 · Every transfer fails after one typo (★) · `validation.py` · §6
```python
def validate_send(amount, recipient_phone, errors=[]):     # ONE list, shared by every call
```
- **Decision behind it:** a mutable default argument, which shares state between all requests.
- **Discover:**
  - In the REPL, two calls return the same list (`is` → `True`).
  - Running `pytest tests/test_validation.py tests/test_transfers.py` (invalid tests first) turns
    `test_transfers` red: a suite that only passes in one order is hiding shared state.
- **Fix:** `def validate_send(amount, recipient_phone):` with `errors = []` inside.
- **Card:** P2.

#### C2 · ₪5,000 pulled from the bank for a ₪50 top-up (★★) · `service.py` · §1, §9
```python
self.bank.pull(user.bank_account, amount)       # agorot; pull() takes a Decimal number of shekels
```
- **Decision behind it:** a bare `int` with no unit crosses a boundary. The mock bank silently accepts it.
- **Discover:**
  - `check.py` invariant `[1]`; then read `MockBank.pull`'s signature and docstring next to the call.
  - **Type hints:** annotate `WalletService.__init__(self, conn, bank: MockBank, clock, notifier) -> None`
    and `top_up(self, user_id: int, amount: int) -> None`, and mypy reports
    `Argument 2 to "pull" of "MockBank" has incompatible type "int"; expected "Decimal"`.
- **Fix:** `self.bank.pull(user.bank_account, Decimal(amount) / 100)`.
- **Card:** P1, and P5.

#### C3 · My notifications screen is always empty (★★) · `api.py` · §8, §9
```python
def notifications(self, token):
    return {"ok": True, "messages": self.notifier.messages_for(token)}    # a token where a user id belongs
```
`messages_for` compares the token with int user ids, and `"x3Fq…" == 2` is simply `False`. Nothing raises,
and a made-up token isn't rejected either.
- **Decision behind it:** no type hints, so nothing can see that a `str` went where an `int` belongs. Every
  other endpoint calls `self._user_id(token)`.
- **Discover:**
  - **Debugger:** a breakpoint in `messages_for` shows `user_id = 'x3Fq…'`.
  - **Type hints:** annotate `Notifier.__init__(self) -> None`, `messages_for(self, user_id: int) ->
    list[str]`, `PeerPayAPI.__init__(...) -> None` and `notifications(self, token: str)`, and mypy reports
    `Argument 1 to "messages_for" of "Notifier" has incompatible type "str"; expected "int"`.
- **Fix:** `user_id = self._user_id(token)` (in a `try`/`except WalletError`, like the other endpoints), then
  `messages_for(user_id)`.
- **Card:** P5.

#### C4 · A long note ate my ₪100 (★★) · `repository.py`, `service.py`, `validation.py` · §3
```python
# repository.py: every write ends with
self.conn.commit()

# service.py, send(): no transaction
sender.balance -= amount
self.repo.save_account(sender)                                           # committed
transfer = self.repo.insert_transfer(...)    # CHECK (length(note) <= 140) → IntegrityError
```
- **Decision behind it:** the repository commits on its own, so the service can't make a use case atomic.
  The note limit exists only as a DB `CHECK`, which runs after the money has moved.
- **Clues:** `MAX_NOTE` is defined but never used. The `IntegrityError` isn't a `WalletError`, so it escapes
  the API as a crash.
- **Discover:** `check.py` invariant `[1]`. Inspect the data at rest. Grep for `commit()`.
  - **Family:** `accept()` and the expiry job also commit in several separate steps.
- **Fix (makes the ticket pass):** check `len(note) > MAX_NOTE` in `validate_send`, and pass the note to it.
- **The real fix:** one transaction per use case (P3).
- **Card:** P3 and P2.

#### C5 · Dana can't log in since this morning (★★★, the centerpiece) · `service.py` · §7, §2
```python
# service.py, pending(): the sender object is the one in the UserDirectory cache
sender = self.users.get(transfer.sender_id)
sender.phone = mask_phone(sender.phone)          # "for display": mutates the shared object

# auth.py, login()
user = wallet.users.by_phone(normalize_phone(phone))   # the real phone finds the row; the cache returns the masked object
user.last_login = wallet.clock()
wallet.users.save(user)                                # UPDATE users SET phone = ?, … → writes the masked phone
```
When Yossi opens his pending list, Dana's cached object is masked. Her next login still works, but it saves
the masked phone, so every login after that fails.
- **Decision behind it:**
  - Formatting that mutates instead of returning a new value.
  - A cache of mutable objects.
  - "Save the whole object" instead of "update what changed".
- **Discover:**
  - `check.py` invariant `[2]`.
  - "Who changes `user.phone`?": *freeze it and let it crash*. A temporary `@dataclass(frozen=True)` on
    `User` makes `FrozenInstanceError` point at `pending()`.
- **Fix:** delete the assignment, and use `mask_phone(sender.phone)` in the tuple.
- **Card:** P4 and P2.

### Stretch

#### S1 · "Sent ✓", but nothing was sent (★★) · `service.py`, `api.py` · §5
```python
if recipient is None:
    print("no such user:", phone)

    return                         # None …

if sender.balance < amount:
    return False                   # … or False …

return True                        # … or True; and the API checks only `result is False`
```
- **Decision behind it:** four failure conventions in one function.
- **Discover:** step through the unknown-number case. **Type hints:** `send(...) -> Transfer` makes mypy flag all
  three returns.
- **Fix:** `raise UnknownRecipient(phone)`, `raise InsufficientFunds()`, `return transfer`.
- **Card:** P3 (the error boundary) and P5.

#### S2 · I sent ₪19.99, Yossi received ₪19.98 (★) · `money.py` · §1
```python
return int(float(text) * 100)      # float("19.99") * 100 == 1998.9999999999998 → 1998
```
- **Fix:** `int(Decimal(str(text).strip()) * 100)`, catching `InvalidOperation`.
- **Card:** P1.

#### S3 · "Expires tomorrow", but it already expired (★★, *bisect*) · `api.py` · §4
```python
"expires_at": (t.created_at + timedelta(days=31)).isoformat()    # a month
```
`accept()` refuses at `EXPIRY`, which is 30 days.
- **Decision behind it:** a rule duplicated in the API, with a second meaning of "a month".
- **Discover:** spec diff, and grep for `timedelta(`. Or bisect, with the test in a new, untracked file:
  ```powershell
  git bisect start --first-parent HEAD naive
  git bisect run python -m pytest -q tests/test_ticket_s3.py
  ```
- **Fix:** `(t.created_at + EXPIRY)`, with `from .service import EXPIRY, WalletService`.
- **Card:** P3 (`Transfer.expires_at` in the model).

### Hidden (no ticket)

#### H1 · After a restart, no existing user can log in (★★) · `auth.py` · §2
```python
SALT = os.urandom(16)              # a new salt in every process, and never stored with the hash
```
- **How it's found:** pairs who hunt C1's family ("what else is evaluated only once?") find it. Otherwise,
  reveal it in the debrief: `python demo.py`, then `python demo.py --reuse`.
- **Fix:** a per-user salt, stored as `pbkdf2_sha256$<iterations>$<salt>$<digest>`, checked with
  `hmac.compare_digest`.
- **Discussion point:** existing hashes can't be repaired, so users must reset their passwords.

---

## 3. The pattern cards (the refactoring round)

Each pair takes one card. The reference answer for every card is in `solution/`.

| Card | In `solution/` | Removes |
|---|---|---|
| **P1 Currency** | `money.Money`: immutable int agorot that refuses floats and `bool`, is created from text only by `Money.parse`, and combines only with the same currency. `bank.BankAdapter` is the only code that converts to the bank's shekels. | C2, S2 |
| **P2 Validation** | `values.py`: `PhoneNumber`, `Note`, `BankAccount` and `Password` can only exist when valid, and `PhoneNumber.masked()` returns a new string. `validation.parse_send` / `parse_registration` collect one request's problems in a fresh list and return a typed result before anything changes. | C1, (C4), (C5) |
| **P3 Transactions** | `repository.UnitOfWork`: `BEGIN IMMEDIATE` … `COMMIT` or `ROLLBACK`, and the repositories never commit. `api.endpoint` is the one error boundary. `Transfer.expires_at` and `settled()` keep the expiry and settle-once rules in the model. | C4, S1, S3 |
| **P4 DB usage** | The repositories return immutable objects in lists and keep no cache. Writes change only what changed: `touch_last_login`, and `UPDATE accounts SET balance = balance - ? WHERE … AND balance >= ?`, so the database itself checks and updates the balance atomically. | C5 |
| **P5 Type hints** | Every function, method, fixture and test is annotated with modern hints: PEP 695 `type` aliases and generics (`def endpoint[**P]`, `def collect[T]`), `Self`, `Protocol`, `ClassVar`, `StrEnum`, `X \| None`. Typed results (`PendingItem`, `SendRequest`) replace loose tuples and dicts. `mypy --strict` passes. | C3, and it exposes C2 and S1 |

**Running card P5 in class:**
1. Annotate the functions around a ticket. For C3: `messages_for`, `notifications`, and both `__init__`s.
2. Run `python -m mypy peerpay` and fix what it reports.
3. Widen the annotations step by step, toward `--strict`.

The point to make: mypy checks only annotated code, so an untyped program "passes" a type check.

---

## 4. The lesson (90 minutes)

| Time | Activity |
|---|---|
| 0:00–0:10 | **Briefing.** Read DESIGN.md (the 9 rules and the worked example). Run `demo.py`, `check.py` (note the `[1]` teaser) and `mypy` ("no issues": why?). Show a breakpoint and Evaluate Expression. |
| 0:10–0:50 | **Debugging, in pairs:** C1 → C5, then stretch. Each fix = a failing test + the minimal fix. |
| 0:50–1:15 | **Refactoring:** each pair applies one card, keeping all its tests green. |
| 1:15–1:30 | **Debrief:** the table below. Reveal H1 (`demo.py`, then `demo.py --reuse`). |

**45-minute variant:** C1, C3 and C4 in 25 minutes, card P5 in 15 minutes (annotate, run mypy, watch it find
C3 and S1), and a 5-minute debrief.

| Technique | Bugs |
|---|---|
| Spec diff (DESIGN rule vs. code) | C2, C4, S1, S3 |
| Debugger (breakpoints, Evaluate Expression) | C3, C5, S1, S2 |
| Type hints + `python -m mypy` | C3, C2, S1 |
| Invariant checking (`check.py`) | C2, C4, C5 |
| Identity (`is`) and *freeze it and let it crash* | C1, C5 |
| Test-order dependence | C1 |
| Controlling time (`FakeClock`) | S3 |
| `git bisect run` | S3 |
| Hunting the family | H1 (via C1), C4 (`accept`, the expiry job) |

---

## 5. Debrief table

| Bug | The design decision behind it | The general rule | Card |
|---|---|---|---|
| C1 | A mutable default argument | Defaults are evaluated once; share state only on purpose | P2 |
| C2 | A bare number with no unit crossing a boundary | Units live in types; convert in one adapter | P1, P5 |
| C3 | No type hints: a `str` token where an `int` id belongs | Annotate everything, and let a type checker compare | P5 |
| C4 | Repositories commit; act first, validate later | The use case owns the transaction; validate, then act | P3, P2 |
| C5 | Formatting that mutates, a cache of mutable objects, "save everything" | Command–query separation; immutable entities; targeted writes | P4, P2 |
| S1 | Four ways to signal failure | One error convention, one boundary | P3, P5 |
| S2 | `float` for money | Choose the representation by the required precision | P1 |
| S3 | A rule copied into the API | Each rule lives in exactly one place, in the model | P3 |
| H1 | A salt computed at import and never stored | Nothing runs at import time; store what you need later | — |

---

## 6. Maintaining the lab

- **To change a bug:** change it in the root code. Then copy `solution/tests/test_regressions.py` into
  `tests/`, and check that each test fails on its own and that each minimal fix turns only its own test green.
- **Keep the solution strict:** run `python -m pytest` and `python -m mypy` inside `solution/`.
- **Passwords in tests:** tests use 1,000 PBKDF2 iterations (a `monkeypatch` in `conftest.py`); the code
  default is 600,000.
- **The DB:** `testing.db` is always a testing DB, and `demo.py` re-creates it unless you pass `--reuse`.

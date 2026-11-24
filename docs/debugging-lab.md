# Debugging & Refactoring Lab: "PeerPay" (teacher's guide)

**This is the answer key.** It is in the same public repository as the lab, so students can open it.

A single-lesson lab (90 minutes, with a 45-minute variant). It is built on the backend of a small app for
sending money between friends. Students get code that *mostly works*, a design document (`DESIGN.md`) that
states what it should do, and a stack of tickets (`TICKETS.md`). Every bug comes from a **Python
programming-method mistake or a design decision**. In the second half, students apply **design patterns**
that remove whole families of bugs: validation, transaction execution, DB usage, and currency in software.

- **Technology:** Python + SQLite only. The "API" is a class of plain methods that return dicts
  (`peerpay.api.PeerPayAPI`), so there is no web framework, GUI, networking or threads.
- **Size:** about 740 lines of exercise code in 10 modules, counting docstrings and blank lines, plus about
  250 lines of given helpers and 225 lines of tests.

Everything below was run on Python 3.15.2 on this machine.

---

## 0. What is in this repository

Everything is on `main`, and it is public: the lab, the answer key and the solution.

| Where | What it is |
|---|---|
| repository root | **The lab the students work on**: the buggy code, `DESIGN.md`, `TICKETS.md`, the weak tests, and the given tools. |
| `docs/debugging-lab.md` | This guide (the answer key). |
| `solution/` | The **refactored reference**: patterns P1–P4 applied, all bugs fixed, with every test including `tests/test_regressions.py`. Self-contained: run `python -m pytest` inside `solution/`. |
| tag `naive` | A **correct** PeerPay in a plain style (no patterns), with full tests, including `tests/test_regressions.py`: one test per bug. |
| `main`'s history | `naive` → **one commit per bug** (`bug(C1): …` … `bug(H1): …`, each message explains the bug) → the regression tests removed → tickets and README → this guide → two merges. Run `git show <commit>` on any bug commit to see the bug, and `git revert <commit>` to turn it off. |
| merged-in histories | The `solution/` merge brings in the pattern commits (`refactor(P1)` … `refactor(P4)`); `git show` on each one is that card's solution diff. The second merge keeps the original five-commit student history ("PeerPay: first working version" … "docs: tickets for the debugging lab"), whose final code is the repository root. |

Find any of these commits with `git log --all --oneline`, or by message, e.g. `git show ":/refactor(P3)"`.

**What was verified**

- On `naive` and in `solution/`, every regression test passes, and so does the weak suite.
- On the root (the student code), every regression test fails, and the 25 weak tests pass.
- The bugs are **independent**. Applying any one bug's minimal fix (section 2) to the student code turns
  exactly that bug's regression tests green and changes nothing else. Each test was run in its own process,
  because C1 leaks state across tests.
- Every commit of the five-commit student history passes the weak suite.
- `git bisect run` with a C4 test finds C4 two ways:
  - Along `main` (`git bisect start --first-parent HEAD naive`), it finds `bug(C4): …`.
  - Along the student history, it finds "refactor: compute the expiry date in the API layer".

**To run the regression tests against the student code** (they live in `solution/tests/` and on `naive`):

```powershell
git checkout naive -- tests/test_regressions.py
python -m pytest tests/test_regressions.py
git rm -q -f tests/test_regressions.py
```

`test_c1` is deliberately last in that file. Once C1 has polluted the shared list, every later send in the
same process fails.

---

## 1. The system the students get

**Story.** Users register with a phone number, a bank account and a password. They top up their wallet from
the bank, then send money to any registered user by phone number. The money is held until the recipient
**accepts** it. If the transfer isn't accepted within 30 days, the nightly job **expires** it and the sender
is refunded. The recipient can also decline, and the sender can cancel the last pending transfer.

```text
DESIGN.md · TICKETS.md · README.md
peerpay/
├── api.py            PeerPayAPI: one method per request → {"ok": ...}
├── auth.py           register, login, password hashing
├── service.py        WalletService: top_up, send, pending, accept, decline, cancel_last,
│                     expire_pending, adjust, statement
├── repository.py     the schema, UserDirectory (caches users), Repository (accounts, ledger, transfers)
├── validation.py     validate_send, validate_registration, normalize_phone, mask_phone
├── money.py          parse_amount, format_amount
├── models.py         User, Account, Transfer (mutable dataclasses), status strings
├── events.py         EventBus, Notifier, wire_notifications
├── errors.py         WalletError and its subclasses
├── bank_gateway.py   GIVEN: MockBank.validate_account(), MockBank.pull(account, shekels)
└── clock.py          GIVEN: SystemClock, FakeClock(start=now).advance(days=…)
tools/support.py      the support team's credit tool
check.py              GIVEN: invariant checker
seed.py, demo.py      GIVEN: test users; a scripted day (demo.py --reuse keeps the DB)
tests/                conftest.py (fixtures api, tokens, clock, db_path, bank) + the weak tests
```

**Given parts** (not part of the exercise):
- **`MockBank`** writes every pull to a `bank_log` table in the same testing DB. `pull()` takes **shekels**
  (anything `Decimal()` accepts) and refuses pulls over ₪50,000.
- **`FakeClock`** starts at the real current time and moves only when you call `advance(...)`.
- **`check.py`** checks four invariants:
  1. Stored balance = sum of the ledger.
  2. Wallets + pending = deposits + adjustments.
  3. The bank log × 100 = the deposits.
  4. Every phone number looks like `05XXXXXXXX`.
- **Test users** live in `seed.py`: Dana `0547654321`, Yossi `0521234567`, Noa `0509876543` and Avi
  `0581112233`, each with a test password `<name>-test-pass`.

**What students see in the briefing** (intended):
- **`python demo.py`** runs without errors and the balances look right.
- **`python check.py`** already reports `[3] the bank pulled 1500000.00 agorot …`. That's S5, a teaser:
  tell students to note it and move on.
- Both pending transfers in the demo show the **same** `expires_at`. That's a quiet clue for S3.
- **`python demo.py --reuse`** fails every login. That's H1; keep it for the debrief.

### Why the weak tests are green

| Test weakness | Bug it hides |
|---|---|
| The invalid-input tests live in `test_validation.py`, which runs last (alphabetically) | C1 |
| The statement test checks only `received_count` | C2 |
| No test sends to a well-formed but unregistered number | C3 |
| Accept is tested only on day 1; `expires_at` is never compared with accept | C4 |
| Notes in tests are short | C5 |
| No test logs in a counterparty after a statement | C6 |
| The notification test checks only that *a* push happened | S1 |
| Amounts in tests are whole or half shekels | S2 |
| The clock is never advanced *before* a send; cancel_last is tested with one pending transfer | S3 |
| No test covers `tools/support.py` | S4 |
| The top-up test checks the wallet, not the bank log | S5 |
| Tests run in a single process | H1 |

---

## 2. The bugs

There are **6 core bugs** that every pair works through, **5 stretch bugs**, and **1 hidden bug** with no
ticket. Each entry gives the exact buggy code, the minimal fix (verified independent), and the pattern card
that removes the whole family.

### Core

#### C1 · Every transfer fails after one typo (★) · `validation.py` · §7
```python
def validate_send(amount, recipient_phone, errors=[]) -> list[str]:   # ONE list, shared by every call
    if amount <= 0:
        errors.append("amount must be positive")
    if not PHONE_RE.fullmatch(recipient_phone):
        errors.append("invalid phone number")
    return errors
```
- **Decision behind it:** a mutable default argument, which creates state shared by every request.
- **Discover:**
  - In the REPL, `validate_send(-1, "x")` and then `validate_send(100, "0521234567")` returns the old
    errors, and the two results are the same object (`is` → `True`). Ruff B006 flags the default.
  - The testing lesson: run `pytest tests/test_validation.py tests/test_transfers.py` (invalid tests first)
    and `test_transfers` turns red. A suite that only passes in one order is hiding shared state.
- **Minimal fix:** `def validate_send(amount, recipient_phone)`, with `errors = []` inside.
- **Pattern:** P2.

#### C2 · "Total received: ₪0.00" (★) · `repository.py`, `service.py`
```python
# repository.py
def transfers_to(self, user_id):
    """Accepted transfers that the user received. Streams the rows instead of loading them all."""
    rows = self.conn.execute("SELECT * FROM transfers WHERE recipient_id = ? AND status = 'ACCEPTED' ...")
    for row in rows:
        yield _transfer(row)
# service.py, statement()
"received_count": sum(1 for _ in received),
"received_total": sum(t.amount for t in received),       # the generator is already exhausted → 0
```
- **Decision behind it:** an unclear data-access contract. The function looks like it returns a collection,
  but it returns a one-time stream.
- **Discover:** Put a breakpoint in `statement` and look at `type(received)`. In the REPL:
  `g = (x for x in [1, 2, 3]); sum(1 for _ in g), sum(g)` → `(3, 0)`.
- **Minimal fix:** `return [_transfer(row) for row in rows]`.
- **Pattern:** P4.

#### C3 · "Sent ✓", but nothing was sent (★★) · `service.py`, `api.py` · §6
```python
# service.py, send()
errors = validate_send(amount, phone)
if errors:
    raise ValidationError(errors)            # convention 1: an exception
recipient = self.users.by_phone(phone)
if recipient is None:
    print("no such user:", phone)            # convention 2: print, to the server console …
    return                                   # … and convention 3: None
...
if sender.balance < amount:
    return False                             # convention 4: False
...
return True
# api.py
if result is False:
    return {"ok": False, "error": "insufficient_funds", ...}
return {"ok": True, "message": "Sent ✓"}     # None lands here
```
- **Decision behind it:** there is no single error convention.
- **Clue:** `InsufficientFunds` and `UnknownRecipient` are still imported in `service.py`, but never raised.
- **Discover:** Step through the unknown-number case and watch `send` return `None`. Then list every
  `return` and what each one means, and compare the list with §6.
- **Minimal fix:**
  - `raise UnknownRecipient(phone)` instead of the print and return.
  - `raise InsufficientFunds()` instead of `return False`.
  - `return transfer` instead of `return True`.
  - The API's `is False` check then never fires.
- **Pattern:** P3 (the `@endpoint` error boundary).

#### C4 · "Expires tomorrow", but it already expired (★★, *bisect*) · `api.py` · §5
```python
"expires_at": (t.created_at + timedelta(days=31)).isoformat(),     # a month
```
`service.accept()` refuses once `clock() - created_at >= EXPIRY`, where `EXPIRY` is 30 days.
- **Decision behind it:** a business rule duplicated in the presentation layer, with a second definition of "a month".
- **Discover:**
  - Spec diff on §5, then grep for `timedelta(` to find two definitions.
  - **Bisect:** write the regression test in a **new, untracked** file (tracked files would change under
    bisect), then run:
    ```powershell
    git bisect start HEAD <first commit>
    git bisect run python -m pytest -q tests/test_ticket_c4.py
    ```
    It finds "refactor: compute the expiry date in the API layer". A good test: create a transfer, advance
    the clock to `expires_at − 1 minute`, and accept. It must succeed.
- **Minimal fix:** `(t.created_at + EXPIRY)`, with `from .service import EXPIRY, WalletService`.
- **Pattern:** P3 (`Transfer.expires_at` and `is_expired()` in the model).

#### C5 · A long note ate my ₪100 (★★) · `repository.py`, `service.py`, `validation.py` · §4
```python
# repository.py: every write method ends with
self.conn.commit()
# service.py, send(): no transaction
sender.balance -= amount
self.repo.save_account(sender)                                        # committed
transfer = self.repo.insert_transfer(sender_id, recipient.id, amount, note)   # CHECK (length(note) <= 140) → IntegrityError
self.repo.add_ledger(sender_id, -amount, "transfer_out", self.clock(), transfer.id)
```
- **Decision behind it:** repository methods commit on their own, so the service can't make a use case
  atomic. The note limit exists only as a DB `CHECK`, which runs after the money has moved.
- **Clues:** `MAX_NOTE` is still defined in `validation.py` but never used. The `sqlite3.IntegrityError`
  isn't a `WalletError`, so it escapes the API as a crash.
- **Discover:** Reproduce the ticket, then run `check.py`: `[1] stored balance … != ledger total …` and
  `[2] …`. Look at the data at rest: the balance went down, but there is no ledger row and no transfer.
  Grep for `commit()`.
  - **Family:** `accept()` and `_refund()` also write in several separately committed steps.
- **Minimal fix (makes the ticket pass):** validate the note up front. Add `note` to `validate_send`, check
  `len(note) > MAX_NOTE`, and pass `note` from `send()`.
- **The real fix:** one transaction per use case (P3).
- **Pattern:** P3 + P2.

#### C6 · Yossi's phone number turned into `05*-***-4567` (★★★, the centerpiece) · `service.py` · §10, §2
```python
# service.py, statement()
other = self.users.get(transfer.other_party(user_id))    # the SAME object the UserDirectory cache holds
other.phone = mask_phone(other.phone)                    # "privacy": mutates the shared object
# auth.py, login()
user = wallet.users.by_phone(normalize_phone(phone))     # finds the row by the real phone, but returns the CACHED object
user.last_login = wallet.clock()
wallet.users.save(user)                                  # UPDATE users SET phone = ?, … → writes the masked phone
```
When Dana views her statement, it masks Yossi's cached object. His next login still works, but it saves the
masked phone, so every login after that fails.
- **Decision behind it:**
  - Formatting that mutates instead of returning a new value (no command–query separation).
  - Shared mutable entities in a cache.
  - "Save the whole object" instead of "update what changed".
- **Discover:**
  - `check.py` reports `[4] user 2: stored phone number '05*-***-4567' …`.
  - "Who writes `users.phone`?": only `save()`.
  - "Who changes `user.phone` in memory?": *freeze it and let it crash*. Temporarily make `User` a
    `@dataclass(frozen=True)`, and `FrozenInstanceError: cannot assign to field 'phone'` points at
    `statement()`.
- **Minimal fix:** delete the assignment, and format `({mask_phone(other.phone)})`.
- **Pattern:** P4 (immutable users, no cache, `touch_last_login`) + P2 (`PhoneNumber.masked()`).

### Stretch

#### S1 · Every notification says "expired" (★) · `events.py` · §11
```python
for kind in TEMPLATES:
    bus.subscribe(kind, lambda transfer: notifier.push(kind, transfer))   # every handler sees the LAST kind
```
Every event uses the "expired" template, and because "expired" notifies the sender, the recipient gets
nothing.
- **Decision behind it:** closures capture variables, not values.
- **Discover:** Print inside a handler, or `[f() for f in [lambda: k for k in "abc"]]` → `['c', 'c', 'c']`.
  Ruff B023 flags it.
- **Fix:** `lambda transfer, kind=kind: …`, or `functools.partial(notifier.push, kind)`.

#### S2 · I sent ₪19.99, Yossi received ₪19.98 (★) · `money.py` · §1
```python
def parse_amount(text) -> int:
    try:
        return int(float(text) * 100)        # float("19.99") * 100 == 1998.9999999999998 → 1998
```
- **Decision behind it:** passing an exact quantity through an approximate type.
- **Discover:** Evaluate `float("19.99") * 100` in the debugger (`repr` shows what `print` formatting
  hides). Then test a table of amounts: `0.29` → 28 too.
- **Fix:** `int(Decimal(str(text).strip()) * 100)`, catching `InvalidOperation`.
- **Pattern:** P1.

#### S3 · Today's transfers "expired" tonight; "cancel last" cancels the wrong one (★★) · `repository.py`, `service.py` · §9, §12
```python
# repository.py
def insert_transfer(self, sender_id, recipient_id, agorot, note, created_at=datetime.now()) -> Transfer:
...
"... WHERE sender_id = ? AND status = 'PENDING' ORDER BY created_at DESC LIMIT 1"
# service.py: send() no longer passes self.clock()
transfer = self.repo.insert_transfer(sender_id, recipient.id, amount, note)
```
The default is evaluated once, at import. On a long-running server every new transfer looks weeks old, so
the nightly job expires it. And all transfers share one timestamp, so `ORDER BY created_at` hits a tie and
SQLite returns the *oldest* row (verified; with an index on `(sender_id, created_at)` it returned the newest).
- **Decision behind it:** defaults are evaluated at definition time; the code bypasses the injected clock; and
  it relies on an order the query doesn't guarantee.
- **Discover:** In a test, `clock.advance(days=35)`, then send, then `api.run_expiry()` → `expired: 1`.
  Inspect the table: every `created_at` is identical.
  - **Family:** "what else is computed once at import?" leads to H1.
- **Fix:** make `created_at` a required parameter, pass `self.clock()`, and use `ORDER BY id DESC`.
- **Pattern:** P5.

#### S4 · A support credit disappeared (★★★) · `service.py`, `tools/support.py` · §3, §8
```python
# service.py
self._accounts = {}                         # user id -> Account, loaded once
def _account(self, user_id):
    if user_id not in self._accounts:
        self._accounts[user_id] = self.repo.account(user_id)
    return self._accounts[user_id]
# tools/support.py: "quick credit: one UPDATE, no need to start the whole app for it"
conn.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = (SELECT id FROM users WHERE phone = ?)", ...)
```
- **Decision behind it:** duplicated state (the balance column, the ledger and the cached `Account`),
  together with a layer bypass.
- **Discover:** Reproduce in one test: send, `support.credit(db_path, …)`, send again. Then run `check.py`:
  `[1]` and `[2]` fire. Ask "who writes `balance`?": grep finds three writers in two layers.
- **Fix:** `_account()` returns `self.repo.account(user_id)` (no cache), and the tool goes through
  `api.wallet.adjust(...)`, which writes a ledger entry.
- **Pattern:** P4 (no balance column at all).

#### S5 · ₪5,000 pulled from the bank for a ₪50 top-up (★★) · `service.py` · §1
```python
self.bank.pull(user.bank_account, amount)       # amount is agorot; pull() expects shekels
```
- **Decision behind it:** primitive obsession. An `int` has no unit.
- **Discover:** `check.py` invariant `[3]`. Read `MockBank.pull`'s docstring next to the call, and ask "what
  unit is this number in?"
  - **Clue:** a top-up of ₪600 or more fails with "amount out of range: 60000.00".
- **Fix:** `self.bank.pull(user.bank_account, Decimal(amount) / 100)`.
- **Pattern:** P1 (`BankAdapter` + `Money`).

### Hidden (no ticket)

#### H1 · After a restart, no existing user can log in (★★) · `auth.py` · §2
```python
SALT = os.urandom(16)                       # a new salt in every process; never stored with the hash
def hash_password(password):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), SALT, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${digest.hex()}"
def verify_password(password, stored):
    ...
    return digest.hex() == digest_hex          # also not constant-time
```
Tests, `demo.py` and the README's shell example all register and log in within one process, so it stays
hidden. Pairs who hunt S3's family find it. **Reveal it in the debrief** with `python demo.py` followed by
`python demo.py --reuse`.
- **Fix:** a per-user `salt = os.urandom(16)` inside `hash_password`, stored as
  `pbkdf2_sha256$<iterations>$<salt>$<hash>`, and checked with `hmac.compare_digest`.
- **Data repair:** existing hashes can't be repaired; users must reset their passwords. That's a good
  discussion point.

---

## 3. The patterns (the refactoring round)

Each card is one `refactor(P…)` commit, merged into `main` as `solution/`. That commit is the reference answer, and `git show` on it
is the card's solution diff. All the tests, including the regression tests, pass after every commit.

| Card | Commit | What changes | Removes |
|---|---|---|---|
| **P1 Currency** | `refactor(P1)` | `Money` (immutable int agorot that refuses floats, `Money.parse`, same-currency arithmetic) and `BankAdapter`, the only code that converts to the bank's shekels | S2, S5 |
| **P2 Validation** | `refactor(P2)` | Value objects (`PhoneNumber`, `Note`, `BankAccount`, `Password`) that can only exist when valid; `validation.parse_all` collects one request's errors in a fresh list before anything changes | C1, (C5), (C6) |
| **P3 Transaction execution** | `refactor(P3)` | `UnitOfWork` (`BEGIN IMMEDIATE` … `COMMIT` or `ROLLBACK`; repositories never commit); the `TopUp` / `SendTransfer` commands; `Transfer` as a state machine (`moved_to`, `ALLOWED`) that owns the expiry rule (`expires_at`, `is_expired`); one `@endpoint` error boundary | C3, C4, C5 |
| **P4 DB usage** | `refactor(P4)` | The ledger as the only source of truth (no balance column: a balance is `SUM(ledger)`); `UserRepo`, `LedgerRepo`, `TransferRepo` return immutable objects in lists and keep no cache; `touch_last_login` updates one column | C2, C6, S4 |
| **P5 Time** | already in `naive` | The clock is injected and nothing runs at import time; `Clock` is a type in the service | S3, H1 |

The essential snippets (from `solution/`):

```python
# P1: money.py
@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    agorot: int
    currency: str = "ILS"
    def __post_init__(self):
        if type(self.agorot) is not int:            # rejects float and bool
            raise TypeError(...)
    @classmethod
    def parse(cls, text) -> "Money": ...            # Decimal, at most 2 places: "19.99" → Money(1999)

# P1: bank.py
class BankAdapter:
    def pull(self, account: BankAccount, amount: Money) -> Money:
        receipt = self._gateway.pull(str(account), amount.to_decimal())
        return Money.from_decimal(receipt.amount)

# P2: values.py and validation.py
@dataclass(frozen=True, slots=True)
class PhoneNumber:
    digits: str
    def __post_init__(self): ...                    # invalid → ValidationError: no invalid PhoneNumber exists
    def masked(self) -> str: ...                    # a new string; the number never changes

def parse_all(**parsers) -> dict:
    values, errors = {}, []                         # fresh for every request
    ...

# P3: repository.py, models.py, api.py
class UnitOfWork:
    def __enter__(self):
        self.conn = sqlite3.connect(self._db_path, timeout=5, isolation_level=None)
        self.conn.execute("BEGIN IMMEDIATE")
        ...
    def __exit__(self, exc_type, exc, tb):
        self.conn.execute("COMMIT" if exc_type is None else "ROLLBACK")

EXPIRY = timedelta(days=30)                         # the ONLY definition of "a month"
@dataclass(frozen=True)
class Transfer:
    @property
    def expires_at(self): return self.created_at + EXPIRY
    def moved_to(self, status, at): ...             # raises InvalidTransition unless ALLOWED

def endpoint(method):                               # the single error boundary
    ...  except WalletError → {"ok": False, ...}; except Exception → log + "internal_error"

# P4: repository.py
class LedgerRepo:
    def balance(self, user_id) -> Money:            # derived; nothing to drift
        "SELECT COALESCE(SUM(agorot), 0) FROM ledger WHERE user_id = ?"
```

Also in the reference: slow work (the bank, password hashing) runs **outside** transactions, and events are
published only after the commit.

---

## 4. The lesson (90 minutes)

| Time | Activity |
|---|---|
| 0:00–0:10 | **Briefing.** Read DESIGN.md (the rules and the worked example). Run `python demo.py` and `python check.py` (note the `[3]` teaser), and show a breakpoint and Evaluate Expression. Put the procedure from TICKETS.md on the board. |
| 0:10–0:55 | **Debugging round, in pairs.** Core tickets C1 → C6, then stretch for fast pairs. Each fix = a failing test + the minimal fix. No refactoring yet. |
| 0:55–1:20 | **Refactoring round.** Each pair takes one pattern card (P1–P4) and applies it, keeping all their tests green. |
| 1:20–1:30 | **Debrief.** Fill in the table below. Run `python demo.py` and then `python demo.py --reuse` to reveal H1 if nobody found it. |

**45-minute variant:** C1, C3, C5 and C6 in 25 minutes, the P3 card in 15 minutes, and a 5-minute debrief.

### Techniques this lab practices

| Technique | Bugs |
|---|---|
| Spec diff: the DESIGN rule next to the code path | C3, C4, C5, S4, S5 |
| Debugger: breakpoints, Evaluate Expression, the call stack | C2, C3, S2 |
| Identity checks (`is`, `id()`) | C1, C6 |
| *Freeze it and let it crash* (a temporary `frozen=True`) | C6 |
| Invariant checking (`check.py`) | C5, C6, S4, S5 |
| "Who writes X?" (find usages / grep) | C4, C6, S4 |
| Test-order dependence | C1 |
| Controlling time (`FakeClock.advance`) | C4, S3 |
| `repr()` instead of formatted output | S2 |
| Inspecting data at rest (sqlite3 CLI / DB Browser) | C5, C6, S3 |
| Static analysis (`ruff check --select B`) | C1, S1 |
| `git bisect run` | C4 |
| Hunting the family | H1 (via S3), C5 (`accept`, `_refund`) |

---

## 5. Debrief table (fill it in with the class)

| Bug | The design decision behind it | The general rule | Pattern |
|---|---|---|---|
| C1 | A mutable default argument | Defaults are evaluated once; no state shared by accident | P2 |
| C2 | A generator where a list was expected | Make the data-access contract explicit | P4 |
| C3 | Four ways to signal failure | One error convention, one boundary | P3 |
| C4 | A rule copied into the API, with a second meaning of "a month" | Each rule lives in exactly one place, in the model | P3 |
| C5 | Repositories commit; act first, validate later | Whoever owns the use case owns the transaction; validate, then act | P3, P2 |
| C6 | Formatting that mutates, a shared cache, "save everything" | Command–query separation; immutable entities; targeted writes | P4, P2 |
| S1 | A closure over a loop variable | Bind values explicitly | — |
| S2 | `float` for money | Choose the representation by the required precision | P1 |
| S3 | A default evaluated at import; bypassing the clock; an unguaranteed order | Time is a dependency; identities, not timestamps | P5 |
| S4 | Duplicated state, plus a layer bypass | A single source of truth; respect the layers | P4 |
| S5 | A bare number with no unit crossing a boundary | Units live in types; convert in one adapter | P1 |
| H1 | A salt computed at import and never stored | Nothing runs at import time; store what you need to verify later | P5 |

---

## 6. Maintaining the lab

- **To change a bug:** change it in the root code (or `git revert` its `bug(…)` commit and plant it again),
  then check that each regression test fails on its own, and that each minimal fix turns only its own test
  green.
- **Passwords in tests:** tests use 1,000 PBKDF2 iterations (a `monkeypatch` in `conftest.py`). The code
  default is 600,000.
- **The DB:** `testing.db` is always a testing DB, and `demo.py` re-creates it unless you pass `--reuse`.

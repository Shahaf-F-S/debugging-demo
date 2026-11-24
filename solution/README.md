# PeerPay: the reference solution

The lab's code after every bug was fixed and the six pattern cards were applied: money as a value object
and a bank adapter (P1), value objects and per-request validation (P2), a unit of work, commands, a status
state machine and one error boundary (P3), the ledger as the only source of truth (P4), an injected clock
(P5), and full modern type hints checked by `mypy --strict` (P6). Read [DESIGN.md](DESIGN.md) for the rules.

## Setup

Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run (from this folder)

```powershell
python -m pytest           # all tests, including tests/test_regressions.py (one test per lab bug)
python -m mypy             # strict type checking, configured in pyproject.toml
python demo.py             # a scripted day against testing.db (re-created every time)
python check.py            # checks the invariants of testing.db
```

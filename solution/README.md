# PeerPay: the reference solution

The lab's code after every bug was fixed and the five pattern cards were applied: money as a value object
and a bank adapter (P1), value objects and per-request validation (P2), a unit of work and one error
boundary (P3), repositories that return immutable objects and update balances in SQL (P4), and full
modern type hints checked by `mypy --strict` (P5). Read [DESIGN.md](DESIGN.md) for the rules.

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

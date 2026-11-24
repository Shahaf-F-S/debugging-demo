# PeerPay

The backend of an app for sending money to friends. In this lab you debug and refactor it.

1. Read [DESIGN.md](DESIGN.md). It is the source of truth: where the code disagrees with it, the code is wrong.
2. Work through [TICKETS.md](TICKETS.md).

## Setup

Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
python -m pytest           # the tests (all green, which doesn't mean much)
python demo.py             # a scripted day against testing.db (re-created every time)
python check.py            # checks the invariants of testing.db
python -m mypy peerpay     # the type checker (it only checks functions that have type hints)
```

`python demo.py --reuse` runs the day again on the existing `testing.db`, without re-creating it.

The API is `peerpay.api.PeerPayAPI`. To try something by hand, in a Python shell:

```python
import demo
from peerpay.api import PeerPayAPI
demo.fresh_db()                       # re-creates testing.db with the test users
api = PeerPayAPI(demo.DB_PATH)
dana = api.login("0547654321", "dana-test-pass")["token"]
api.top_up(dana, "100")
api.balance(dana)
```

The test users and their test passwords are in `demo.py`. In tests, use the fixtures from
`tests/conftest.py`: `api`, `tokens` (Dana, Yossi and Noa, registered and logged in), `clock` (a
`FakeClock`), and `db_path`.

## What else is in this repository

Spoilers, for after the lab (or for teachers):

- [docs/debugging-lab.md](docs/debugging-lab.md): the teacher's guide, with every bug, its fix and the lesson plan.
- [solution/](solution/): the refactored reference solution, fully typed and self-contained: `cd solution`,
  then `python -m pytest` and `python -m mypy` (strict).
- The git history: the tag `naive` is a correct version, and each later `bug(…)` commit plants one bug.

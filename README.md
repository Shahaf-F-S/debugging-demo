# PeerPay

The backend of an app for sending money to friends. In this lab you debug and refactor it.

1. Read [DESIGN.md](DESIGN.md). It is the source of truth: where the code disagrees with it, the code is wrong.
2. Work through [TICKETS.md](TICKETS.md).

## Setup

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
```

`python demo.py --reuse` runs the day again on the existing `testing.db`, without re-creating it.

The API is `peerpay.api.PeerPayAPI`. To try something by hand, in a Python shell:

```python
import seed
from peerpay.api import PeerPayAPI
seed.fresh_db()                       # re-creates testing.db with the test users
api = PeerPayAPI(seed.DB_PATH)
dana = api.login("0547654321", "dana-test-pass")["token"]
api.top_up(dana, "100")
api.balance(dana)
```

The test users and their test passwords are in `seed.py`. In tests, use the fixtures from
`tests/conftest.py`: `api`, `tokens` (Dana, Yossi and Noa, registered and logged in), `clock` (a
`FakeClock`), and `db_path`.

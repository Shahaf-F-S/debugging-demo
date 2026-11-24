# PeerPay

The backend of an app for sending money to friends. Read [DESIGN.md](DESIGN.md) first.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
python -m pytest           # the tests
python demo.py             # a scripted day against testing.db (re-created every time)
python check.py            # checks the invariants of testing.db
```

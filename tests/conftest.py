import pytest

from peerpay import auth
from peerpay.api import PeerPayAPI
from peerpay.bank_gateway import MockBank
from peerpay.clock import FakeClock

# phone, name, bank account, test password
DANA = ("0547654321", "Dana", "12-345-678905", "dana-test-pass")
YOSSI = ("0521234567", "Yossi", "20-614-123452", "yossi-test-pass")
NOA = ("0509876543", "Noa", "31-102-555017", "noa-test-pass")


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    """The real PBKDF2 settings are slow on purpose; tests use fewer iterations."""

    monkeypatch.setattr(auth, "ITERATIONS", 1_000)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "testing.db"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def bank(db_path):
    return MockBank(db_path)


@pytest.fixture
def api(db_path, bank, clock):
    app = PeerPayAPI(db_path, bank=bank, clock=clock)

    yield app

    app.close()


@pytest.fixture
def tokens(api):
    """Registers Dana, Yossi and Noa, and logs them in. Returns {name: token}."""

    result = {}

    for phone, name, bank_account, password in (DANA, YOSSI, NOA):
        assert api.register(phone, name, bank_account, password)["ok"]
        result[name] = api.login(phone, password)["token"]

    return result

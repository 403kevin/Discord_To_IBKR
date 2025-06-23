import time
import pytest
from freezegun import freeze_time
from trailing_stop_manager import TrailingStopManager

class DummyIB:
    def __init__(self):
        self.sell_calls = []
        self.prices = []
    def get_live_price(self, contract):
        # pop next price for each check
        return self.prices.pop(0) if self.prices else None
    def submit_sell_market_order(self, order):
        self.sell_calls.append(order)

class DummyContract:
    symbol = "AAPL"
    lastTradeDateOrContractMonth = "20250620"
    strike = 150
    right = "C"

@pytest.fixture
def manager(monkeypatch):
    ib = DummyIB()
    # intercept telegram
    sent = []
    monkeypatch.setattr("notification.send_telegram_message", lambda msg: sent.append(msg))
    mgr = TrailingStopManager(ib_interface=ib, portfolio_state={})
    return ib, mgr, sent

def test_trailing_exit_after_pullback(manager):
    ib, mgr, sent = manager
    # simulate a position entry
    contract = DummyContract()
    mgr.add_position("AAPL", contract, entry_price=100.0, qty=1)
    # simulate first breakeven trigger at 5% gain
    ib.prices = [105.1, 105.1, 104.0]  # first check hits BE, next updates high, then falls below high * 0.75
    mgr.check_trailing_stops()
    # after first call, breakeven_hit should be True
    assert mgr.active_trails["AAPL"]["breakeven_hit"]
    # two more checks cause exit
    mgr.check_trailing_stops()
    mgr.check_trailing_stops()
    # should have sold once
    assert len(ib.sell_calls) == 1
    # telegram sent
    assert any("Exited Trade: AAPL" in msg for msg in sent)

@freeze_time("2025-06-20 09:30:00")
def test_timeout_exit(manager):
    ib, mgr, sent = manager
    contract = DummyContract()
    mgr.add_position("AAPL", contract, entry_price=100.0, qty=2)
    # simulate no price change
    ib.prices = [100, 100, 100]
    # simulate passing TIMEOUT_EXIT_MINUTES via time travel
    with freeze_time("2025-06-20 09:32:00"):
        mgr.check_trailing_stops()
    # should have sold once
    assert len(ib.sell_calls) == 1
    assert "Time-Based Exit" in sent[0]

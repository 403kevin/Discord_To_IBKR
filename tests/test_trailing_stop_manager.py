import pytest
from freezegun import freeze_time
from trailing_stop_manager import TrailingStopManager

class DummyIB:
    def __init__(self):
        self.sell_calls = []
        self.prices = []

    def get_live_price(self, contract):
        # Return the next price in the list (or None if empty)
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
    sent = []
    # Patch Telegram notifier to capture messages instead of sending
    monkeypatch.setattr("notification.send_telegram_message", lambda msg: sent.append(msg))
    mgr = TrailingStopManager(ib_interface=ib, portfolio_state={})
    return ib, mgr, sent

def test_trailing_exit_after_pullback(manager):
    ib, mgr, sent = manager
    contract = DummyContract()
    mgr.add_position("AAPL", contract, entry_price=100.0, qty=1)
    # Simulate prices: hit BE, update high, then drop below high*(1-25%)
    ib.prices = [105.1, 105.1, 104.0]
    mgr.check_trailing_stops()  # breakeven flag
    assert mgr.active_trails["AAPL"]["breakeven_hit"]
    mgr.check_trailing_stops()
    mgr.check_trailing_stops()
    assert len(ib.sell_calls) == 1
    assert any("Exited Trade: AAPL" in msg for msg in sent)

@freeze_time("2025-06-20 09:30:00")
def test_timeout_exit(manager):
    ib, mgr, sent = manager
    contract = DummyContract()
    mgr.add_position("AAPL", contract, entry_price=100.0, qty=2)
    ib.prices = [100, 100, 100]
    # Advance clock past TIMEOUT_EXIT_MINUTES (1 minute by default)
    with freeze_time("2025-06-20 09:32:00"):
        mgr.check_trailing_stops()
    assert len(ib.sell_calls) == 1
    assert "Time-Based Exit" in sent[0]

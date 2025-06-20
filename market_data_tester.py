# market_data_tester_v3.py

import time
import re
from datetime import datetime
from ib_insync import IB, Option

def parse_signal(signal: str):
    """
    Given a signal like "BTO SPX 06/06 6000C",
    extract: action, underlying, expiry (MM/DD), strike, right.
    """
    pattern = r'^\s*(?P<action>\w+)\s+(?P<underlying>\w+)\s+(?P<expiry>\d{2}/\d{2})\s+(?P<strike>\d+(?:\.\d+)?)(?P<right>[CPcp])\s*$'
    m = re.match(pattern, signal)
    if not m:
        raise ValueError(f"Signal does not match expected format: '{signal}'")
    gd = m.groupdict()
    return {
        "action": gd["action"].upper(),
        "underlying": gd["underlying"].upper(),
        "expiry": gd["expiry"],        # "MM/DD"
        "strike": float(gd["strike"]),
        "right": gd["right"].upper()   # "C" or "P"
    }

def build_option_template(parsed: dict, year: int = None, trading_class: str = None, exchange: str = "SMART"):
    """
    Build an Option contract object with (symbol, expiryYYYYMMDD, strike, right, exchange, currency).
    Optionally pass a tradingClass; if None, it will be omitted.
    """
    now = datetime.utcnow()
    yy = year if year is not None else now.year
    mm, dd = parsed["expiry"].split('/')
    yyyymmdd = f"{yy:04d}{int(mm):02d}{int(dd):02d}"

    kwargs = {
        "symbol": parsed["underlying"],
        "lastTradeDateOrContractMonth": yyyymmdd,
        "strike": parsed["strike"],
        "right": parsed["right"],
        "exchange": exchange,
        "currency": "USD"
    }
    if trading_class:
        kwargs["tradingClass"] = trading_class

    return Option(**kwargs)

def qualify_variations(ib: IB, parsed: dict):
    """
    Try a few different Option templates until one qualifies:
      1) SMART, no tradingClass
      2) SMART, tradingClass=underlying
      3) CBOE, no tradingClass
      4) CBOE, tradingClass=underlying

    Return the first contract that passes qualifyContracts(), or (None, None, None).
    """
    underlying = parsed["underlying"]
    to_try = [
        ("SMART",    None),
        ("SMART",    underlying),
        ("CBOE",     None),
        ("CBOE",     underlying),
    ]

    for exch, tclass in to_try:
        contract = build_option_template(parsed, trading_class=tclass, exchange=exch)
        details = ib.qualifyContracts(contract)
        if details:
            return details[0], exch, tclass

    return None, None, None

def format_price(x):
    """
    Safely format a float or None.
    Return a string like "3.50" or "--" if x is None or nan.
    """
    try:
        if x is None:
            return "--"
        # Some streams give nan instead of None
        if isinstance(x, float) and (x != x):
            return "--"
        return f"{x:.2f}"
    except:
        return "--"

def test_market_data_for_signal(signal: str, run_seconds: int = 15, client_id: int = 1):
    """
    1) Parses the signal
    2) Connects to IB on localhost:7497
    3) Tries a few contract‐qualification variants
    4) Subscribes to real-time quotes and prints bid/ask/mid or last
    """
    print(f">>> Testing market data for signal: '{signal}'")
    parsed = parse_signal(signal)
    print("Parsed signal:", parsed)

    ib = IB()
    try:
        print("→ Connecting to IB on localhost:7497 ...")
        ib.connect('127.0.0.1', 7497, clientId=client_id)
    except Exception as e:
        print("❌ Could not connect to IB Gateway/TWS:", e)
        return

    print("→ Attempting to qualify contract with multiple exchange/tradingClass combos …")
    contract, found_exch, found_tclass = qualify_variations(ib, parsed)
    if not contract:
        print("❌ All contract-qualification attempts failed.")
        print("  - Tried SMART & CBOE, with/without tradingClass.")
        print("  - Make sure SPX 06/06/2025 6000C exists and you have OPRA subscription.")
        ib.disconnect()
        return

    tc_info = f"exchange='{found_exch}'"
    if found_tclass:
        tc_info += f", tradingClass='{found_tclass}'"
    print(f"✅ Contract qualified on {tc_info}: {contract.localSymbol}  (conId={contract.conId})\n")

    print(">> Note: SPX options only trade during CBOE hours: 8:30 am – 3:00 pm ET (6:30 am – 1:00 pm MT).")
    print("   If run outside those times, bid/ask will be empty and we’ll fall back to last price if available.\n")

    print(f"→ Subscribing to live market data for {contract.localSymbol} …")
    ticker = ib.reqMktData(contract, "", False, False)

    print("\n--- Live Quotes (bid / ask / mid or last) ---")
    start_time = time.time()
    while time.time() - start_time < run_seconds:
        bid = ticker.bid
        ask = ticker.ask
        last = ticker.last
        mid = None
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2

        tstamp = (
            ticker.time.strftime("%H:%M:%S")
            if ticker.time
            else "--"
        )

        bid_str = format_price(bid)
        ask_str = format_price(ask)
        mid_str = format_price(mid)
        last_str = format_price(last)

        # If bid/ask are not available, show last
        if mid_str == "--" and last_str != "--":
            price_display = f"Last={last_str}"
        else:
            price_display = f"Bid={bid_str}  Ask={ask_str}  Mid={mid_str}"

        print(f"{datetime.now().strftime('%H:%M:%S')}   {price_display}   TickTs={tstamp}")
        time.sleep(1)

    print("\n→ Canceling subscription and disconnecting …")
    ib.cancelMktData(ticker)
    ib.disconnect()
    print("✅ Disconnected from IB. Test complete.")

if __name__ == "__main__":
    test_market_data_for_signal("BTO SPX 06/06 6000C")

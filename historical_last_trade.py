# historical_last_trade.py

import logging
from datetime import datetime, timedelta
from ib_interface import IBInterface  # your existing class

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def main():
    ib_if = IBInterface()
    try:
        # Build the SPX 06/09/2025 6000C contract
        class ParsedSignal:
            pass

        parsed = ParsedSignal()
        parsed.underlying_symbol = "SPX"
        parsed.expiry = datetime(2025, 6, 9).date()
        parsed.strike_price = 6000.0
        parsed.call_or_put = "C"

        contract = ib_if.create_contract(parsed)

        # --- Pull the last 1‐minute bar from today’s session ---
        # EndDateTime: use current time (or market close time)
        # DurationStr: “1 D” means 1 calendar day, but if you only want the final bar,
        #   you can set DurationStr="300 S" (5 minutes) or "2 D" and then pick the last bar.
        # BarSize: use “1 min” so you get that last‐traded price, even after hours.
        # WhatToShow: “TRADES” for the actual traded price.
        # UseRTH: 1 means Regular Trading Hours only (so you don’t pull extended‐hours bars).
        #
        # The call returns a list of BarData; we’ll take the final bar.
        bars = ib_if.ib.reqHistoricalData(
            contract,
            endDateTime="",         # empty string = “now”
            durationStr="1 D",      # pull today’s bars
            barSizeSetting="1 min", # 1‐minute bars
            whatToShow="TRADES",    # last traded price
            useRTH=1,               # only regular trading hours (no extended)
            formatDate=1            # return datetime objects
        )

        if not bars:
            print("No historical bars returned. Maybe no trades today?")
        else:
            last_bar = bars[-1]
            last_price = last_bar.close
            last_time = last_bar.date
            print(
                f"Most recent trade bar for {contract.localSymbol}: "
                f"{last_price} at {last_time}"
            )

        ib_if.ib.reqHistoricalData  # NB: no explicit cancel needed for reqHistoricalData

    finally:
        ib_if.disconnect()


if __name__ == "__main__":
    main()

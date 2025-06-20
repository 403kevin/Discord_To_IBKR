# snapshot_test.py

import logging
from datetime import date
from ib_interface import IBInterface

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

def main():
    ib_if = IBInterface()
    try:
        # Build the SPX 06/06/2025 6000C contract
        class ParsedSignal:
            pass

        parsed = ParsedSignal()
        parsed.underlying_symbol = "SPX"
        parsed.expiry = date(2025, 6, 6)
        parsed.strike_price = 6000.0
        parsed.call_or_put = "C"

        # Create and qualify the contract
        contract = ib_if.create_contract(parsed)

        # Perform a one‐shot “snapshot only” request (timeout is short because we only want the last‐print)
        price, _ = ib_if.get_realtime_price(
            contract,
            timeout=0.5,
            use_snapshot=True
        )

        print(f"After‐hours last‐trade price for {contract.localSymbol} = {price}")

    finally:
        ib_if.disconnect()

if __name__ == "__main__":
    main()

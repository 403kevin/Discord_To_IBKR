# ib_interface.py

import logging
import ib_insync
from ib_insync import Option, Stock, Order


class IBInterface:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, clientId: int = 1, account_number: str = ""):
        """
        Initialize the IB connection.
        """
        self.ib = ib_insync.IB()
        self.account_number = account_number
        self.ib.connect(host, port, clientId)
        logging.info(f"[IB] Connected to {host}:{port} as clientId={clientId}")

    def create_contract(self, parsed_symbol) -> ib_insync.Contract:
        """
        Build and qualify a Stock or Option contract from parsed_symbol.
        - If parsed_symbol is a plain string (e.g., "AAPL"), we treat it as a Stock.
        - Otherwise, parsed_symbol should have attributes:
            • underlying_symbol (str, e.g., "SPX")
            • expiry (datetime.date)
            • strike_price (float)
            • call_or_put ("C" or "P")
        """
        # Case 1: parsed_symbol is a simple stock ticker string
        if not hasattr(parsed_symbol, "underlying_symbol"):
            contract = Stock(parsed_symbol, "SMART", "USD")
            self.ib.qualifyContracts(contract)
            logging.info(f"[CONTRACT] Qualified Stock: {contract.localSymbol}")
            return contract

        # Case 2: parsed_symbol is an OptionSymbol-like object
        expiry_str = parsed_symbol.expiry.strftime("%Y%m%d")
        contract = Option(
            parsed_symbol.underlying_symbol,
            expiry_str,
            parsed_symbol.strike_price,
            parsed_symbol.call_or_put,
            "SMART",
            currency="USD"
        )

        # Special handling for SPX vs. SPXW
        if parsed_symbol.underlying_symbol.upper() == "SPX":
            contract = Option(
                parsed_symbol.underlying_symbol,
                expiry_str,
                parsed_symbol.strike_price,
                parsed_symbol.call_or_put,
                "SMART",
                currency="USD",
                tradingClass="SPXW"
            )

        self.ib.qualifyContracts(contract)
        logging.info(f"[CONTRACT] Qualified Option: {contract.localSymbol}")
        return contract

    def get_realtime_price(
        self,
        contract: ib_insync.Contract,
        timeout: float = 3.0,
        use_snapshot: bool = False
    ) -> tuple[float, ib_insync.Contract]:
        """
        Fetch a single real-time price for a qualified IB Contract.
        If use_snapshot=True, requests a one-shot snapshot.
        Otherwise, subscribes to streaming ticks for up to `timeout` seconds.

        Returns:
            (price: float, contract: ib_insync.Contract)
            • price = last / marketPrice() / midpoint; -1.0 if no valid data.
        """
        try:
            # Ensure contract is qualified
            if not getattr(contract, "conId", None):
                self.ib.qualifyContracts(contract)

            if use_snapshot:
                ticker = self.ib.reqMktData(contract, "", False, True)
                # Brief pause to allow IB to fill the snapshot
                self.ib.sleep(0.5)

                price = ticker.last if (ticker.last not in [None, 0.0]) else None
                try:
                    self.ib.cancelMktData(contract)
                except Exception:
                    pass
            else:
                ticker = self.ib.reqMktData(contract, "", False, False)
                self.ib.sleep(timeout)
                self.ib.cancelMktData(contract)

                if ticker.last and (ticker.last not in [0.0]):
                    price = ticker.last
                else:
                    price = ticker.marketPrice()

            # Fallback to bid/ask midpoint if still invalid
            if price in [None, 0.0]:
                if hasattr(ticker, "bid") and hasattr(ticker, "ask") and ticker.bid and ticker.ask:
                    price = (ticker.bid + ticker.ask) / 2
                else:
                    price = None

            if price:
                logging.info(f"[PRICE FETCH] {contract.localSymbol}: {price}")
                return price, contract
            else:
                logging.warning(f"[PRICE FETCH FAIL] No valid price for {contract.localSymbol}")
                return -1.0, contract

        except Exception as exc:
            logging.error(f"[PRICE EXC] failed for {getattr(contract, 'localSymbol', contract)}: {exc}")
            return -1.0, contract

    def place_native_trail_stop(self, order: dict) -> ib_insync.Trade:
        """
        Place a native IB trailing-stop order.
        Expects `order` to contain:
          • parsed_symbol (OptionSymbol or stock ticker)
          • qty (int)
          • trail_percent (float, in percentage points, e.g., 1.5 for 1.5%)
        """
        # Build & qualify the contract
        contract = self.create_contract(order["parsed_symbol"])

        # Convert percentage into decimal for IB API (IB expects a raw percent)
        trailing_percent = order.get("trail_percent", 1.5) / 100.0

        ib_order = Order(
            orderType="TRAIL",
            totalQuantity=order["qty"],
            trailingPercent=trailing_percent,
            action="SELL",
            tif="GTC",
            account=self.account_number if self.account_number else None,
        )

        trade = self.ib.placeOrder(contract, ib_order)
        logging.info(
            f"[TRAIL STOP] Placed TRAIL order on {contract.localSymbol} "
            f"qty={order['qty']} trail%={trailing_percent*100}"
        )
        return trade

    def unsub_market_data(self, contract: ib_insync.Contract):
        """
        Cancel any ongoing market data subscription for the given contract.
        """
        try:
            self.ib.cancelMktData(contract)
            logging.info(f"[UNSUBSCRIBE] Cancelled market data for {contract.localSymbol}")
        except Exception as exc:
            logging.warning(f"[UNSUBSCRIBE FAIL] Could not cancel data for {contract}: {exc}")

    def disconnect(self):
        """
        Disconnect the IB session cleanly.
        """
        try:
            self.ib.disconnect()
            logging.info("[IB] Disconnected from Interactive Brokers")
        except Exception as exc:
            logging.error(f"[IB DISCONNECT ERROR] {exc}")

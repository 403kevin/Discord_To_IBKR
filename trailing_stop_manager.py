import time
import logging
from datetime import datetime
from config import (
    TRAILING_STOP_ENABLED,
    USE_ADVANCED_TRAILING,
    FALLBACK_IB_TRAIL_ENABLED,
    BREAKEVEN_TRIGGER_PERCENT,
    MAX_LOSS_STOP_PERCENT,
    TIMEOUT_EXIT_MINUTES
)
from trade_logger import log_trade
from notification import send_telegram_message


class TrailingStopManager:
    def __init__(self, ib_interface, portfolio_state):
        self.ib = ib_interface
        self.portfolio_state = portfolio_state
        self.active_trails = {}

    def add_position(self, symbol: str, contract, entry_price: float, qty: int):
        if not TRAILING_STOP_ENABLED:
            return

        if FALLBACK_IB_TRAIL_ENABLED:
            # Fallback to native IB TRAIL order if enabled
            logging.info(
                f"[FALLBACK TRAIL] Placing IB native trailing stop for {contract.localSymbol} at "
                f"{100 * self.ib.TRAILING_STOP_PERCENT}%"
            )
            self.ib.submit_trailing_stop_order({
                'underlying': contract.symbol,
                'exp_month': int(contract.lastTradeDateOrContractMonth[4:6]),
                'exp_day': int(contract.lastTradeDateOrContractMonth[6:]),
                'strike': contract.strike,
                'p_or_c': contract.right.lower(),
                'qty': qty,
                'trail_percent': self.ib.TRAILING_STOP_PERCENT
            })
            return

        # Initialize adaptive trailing state
        self.active_trails[symbol] = {
            'contract': contract,
            'entry_price': entry_price,
            'qty': qty,
            'highest': entry_price,
            'breakeven_hit': False,
            'start_time': time.time()
        }

    def check_trailing_stops(self):
        if not self.active_trails:
            return

        now = time.time()
        to_remove = []

        for symbol, trail in list(self.active_trails.items()):
            contract = trail['contract']
            current_price = self.ib.get_live_price(contract)
            if current_price is None:
                logging.warning(f"[TRAIL WARNING] {symbol} - No valid price for trailing stop")
                continue

            elapsed_minutes = (now - trail['start_time']) / 60
            logging.info(
                f"[TRAIL CHECK] {symbol} | price: {current_price:.2f}, "
                f"elapsed: {elapsed_minutes:.2f} min"
            )

            # Adaptive trailing logic
            if USE_ADVANCED_TRAILING:
                # Breakeven trigger
                if not trail['breakeven_hit']:
                    target = trail['entry_price'] * (1 + BREAKEVEN_TRIGGER_PERCENT / 100)
                    if current_price >= target:
                        trail['breakeven_hit'] = True
                        logging.info(f"[BREAKEVEN HIT] {symbol} crossed {BREAKEVEN_TRIGGER_PERCENT}%")

                # Once breakeven_hit, update highest and check pullback
                if trail['breakeven_hit']:
                    if current_price > trail['highest']:
                        trail['highest'] = current_price
                        logging.debug(f"[TRAIL UPDATE] {symbol} new high: {current_price:.2f}")
                    else:
                        threshold = trail['highest'] * (1 - MAX_LOSS_STOP_PERCENT / 100)
                        if current_price < threshold:
                            # Trigger trailing exit
                            logging.info(
                                f"[TRAIL EXIT] {symbol} dropped {MAX_LOSS_STOP_PERCENT}% from high. Exiting..."
                            )
                            self.ib.submit_sell_market_order({
                                'qty': trail['qty'],
                                'underlying': contract.symbol,
                                'exp_month': int(contract.lastTradeDateOrContractMonth[4:6]),
                                'exp_day': int(contract.lastTradeDateOrContractMonth[6:]),
                                'strike': contract.strike,
                                'p_or_c': contract.right.lower()
                            })
                            # Log and notify
                            log_trade(symbol, trail['qty'], current_price, "SELL", "trailing_stop")
                            msg = (
                                f"🔴 *Exited Trade: {symbol}*
"                                f"> Reason: Trailing Stop ({MAX_LOSS_STOP_PERCENT}% pullback)\n"
                                f"> Price: ${current_price:.2f}  Qty: {trail['qty']}\n"
                                f"> Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            send_telegram_message(msg)
                            self.ib.stop_stream(contract)
                            to_remove.append(symbol)
                            continue

            # Time-based exit
            if elapsed_minutes > TIMEOUT_EXIT_MINUTES:
                logging.info(
                    f"[TIMEOUT EXIT] {symbol} held longer than {TIMEOUT_EXIT_MINUTES} min. Exiting..."
                )
                self.ib.submit_sell_market_order({
                    'qty': trail['qty'],
                    'underlying': contract.symbol,
                    'exp_month': int(contract.lastTradeDateOrContractMonth[4:6]),
                    'exp_day': int(contract.lastTradeDateOrContractMonth[6:]),
                    'strike': contract.strike,
                    'p_or_c': contract.right.lower()
                })
                # Log and notify
                log_trade(symbol, trail['qty'], current_price, "SELL", "timeout")
                msg = (
                    f"🔴 *Exited Trade: {symbol}*
"                    f"> Reason: Time-Based Exit ({TIMEOUT_EXIT_MINUTES} min)\n"
                    f"> Price: ${current_price:.2f}  Qty: {trail['qty']}\n"
                    f"> Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_telegram_message(msg)
                self.ib.stop_stream(contract)
                to_remove.append(symbol)

        # Cleanup completed trails
        for symbol in to_remove:
            self.active_trails.pop(symbol, None)

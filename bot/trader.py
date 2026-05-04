"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                   Live / Demo Trader Module                  ║
╚══════════════════════════════════════════════════════════════╝
⚠  DEMO mode is the default and safe starting point.
   Set LIVE_TRADING_ENABLED = True in config.py AND confirm
   the prompt inside this module to enable real-money trading.
"""
from __future__ import annotations

import time
from datetime import datetime, date
from typing import Optional, Callable

from config import (
    DEFAULT_SYMBOL, TIMEFRAME, BARS_TO_FETCH,
    LOOP_SLEEP_SECONDS, MAX_OPEN_TRADES, LIVE_TRADING_ENABLED,
    is_live_mode,
)
from data import DataFetcher
from indicators import IndicatorEngine
from strategy import SignalGenerator, TradeSetup
from risk import RiskManager
from logger import (
    log_info, log_warning, log_error, log_banner,
    log_trade_open, log_trade_close, log_risk_block, log_separator,
)

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False

# MT5 order type constants (fall back to plain ints if mt5 not imported)
_ORDER_BUY  = 0
_ORDER_SELL = 1
if _MT5_AVAILABLE:
    _ORDER_BUY  = mt5.ORDER_TYPE_BUY
    _ORDER_SELL = mt5.ORDER_TYPE_SELL


class LiveTrader:
    """
    Main trading loop.

    Usage:
        trader = LiveTrader(fetcher, demo_mode=True)
        trader.start()        # blocks — run in a thread from the UI
        trader.stop()         # signals graceful shutdown
    """

    def __init__(
        self,
        fetcher:   DataFetcher,
        demo_mode: bool = True,
        symbol:    str  = DEFAULT_SYMBOL,
        timeframe: str  = TIMEFRAME,
        on_status: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.fetcher    = fetcher
        self.symbol     = symbol
        self.timeframe  = timeframe
        self.demo_mode  = demo_mode
        self.on_status  = on_status   # UI callback for status updates

        self._indicators = IndicatorEngine()
        self._strategy   = SignalGenerator()
        self._risk       = RiskManager()
        self._running    = False
        self._day_start_balance: float = 0.0
        self._current_day: date = datetime.utcnow().date()

        if not demo_mode and not LIVE_TRADING_ENABLED:
            raise RuntimeError(
                "LIVE trading requested but LIVE_TRADING_ENABLED is False in config.py. "
                "Set it to True only after thorough demo testing."
            )

        mode = "⚠  DEMO" if demo_mode else "🔴 LIVE"
        log_banner()
        log_info(f"Trader initialised | Mode: {mode} | Symbol: {symbol} | TF: {timeframe}")

    # ─── Control ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Blocking trading loop.  Call in a background thread from the UI."""
        self._running = True
        account = self.fetcher.get_account_info()
        if account:
            self._day_start_balance = account["balance"]
            self._risk.reset_daily(self._day_start_balance)
            log_info(f"Account balance: {self._day_start_balance:.2f} {account['currency']}")

        log_separator()
        log_info(f"Trading loop started.  Interval: {LOOP_SLEEP_SECONDS}s")

        while self._running:
            try:
                self._cycle()
            except Exception as exc:
                log_error(f"Cycle error: {exc}")

            if self._running:
                time.sleep(LOOP_SLEEP_SECONDS)

        log_info("Trading loop stopped.")

    def stop(self) -> None:
        self._running = False
        log_info("Stop signal sent — waiting for current cycle to finish.")

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Main cycle ───────────────────────────────────────────────────────────

    def _cycle(self) -> None:
        now = datetime.utcnow()
        log_separator("─", 50)
        log_info(f"Cycle at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # Roll daily risk counter at midnight
        today = now.date()
        if today != self._current_day:
            account = self.fetcher.get_account_info()
            bal = account["balance"] if account else self._day_start_balance
            self._day_start_balance = bal
            self._risk.reset_daily(bal)
            self._current_day = today

        account = self.fetcher.get_account_info()
        if not account:
            log_warning("Could not retrieve account info — skipping cycle.")
            return

        balance = account["balance"]

        # Halted?
        if self._risk.is_halted:
            log_risk_block("Daily loss limit active — no new trades today.")
            self._emit_status(account, [])
            return

        # Fetch + decorate data
        df = self.fetcher.get_ohlcv(self.symbol, self.timeframe, BARS_TO_FETCH)
        df = self._indicators.calculate(df)
        df = self._strategy.generate_signals(df)

        # Current open positions
        open_positions = self.fetcher.get_open_positions(self.symbol)
        open_count     = len(open_positions)

        # Check for a new entry signal (only if not at max capacity)
        can_trade, block_reason = self._risk.can_open_trade(balance, open_count)
        if can_trade:
            setup = self._strategy.evaluate_latest(df, self.symbol)
            if setup:
                self._execute_trade(setup, balance)
        else:
            log_info(f"Entry blocked: {block_reason}")

        # Emit UI status
        open_positions = self.fetcher.get_open_positions(self.symbol)
        self._emit_status(account, open_positions)

    # ─── Order execution ──────────────────────────────────────────────────────

    def _execute_trade(self, setup: TradeSetup, balance: float) -> Optional[int]:
        """
        Send a market order via MT5.
        In DEMO mode this hits the broker's demo server (real MT5 API, paper money).
        """
        if not _MT5_AVAILABLE:
            log_warning("MT5 unavailable — cannot place order.")
            return None

        sym_info = self.fetcher.get_symbol_info(setup.symbol)
        if not sym_info:
            log_error(f"Cannot get symbol info for {setup.symbol}")
            return None

        lot_size = self._risk.calculate_lot_size(
            balance       = balance,
            sl_distance   = setup.sl_distance,
            tick_size     = sym_info["trade_tick_size"],
            tick_value    = sym_info["trade_tick_value"],
            contract_size = sym_info["trade_contract_size"],
        )

        tick     = self.fetcher.get_tick(setup.symbol)
        if not tick:
            log_error("Cannot get current tick — order aborted.")
            return None

        order_type = _ORDER_BUY if setup.signal == "BUY" else _ORDER_SELL
        price      = tick["ask"] if setup.signal == "BUY" else tick["bid"]
        digits     = sym_info["digits"]

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       setup.symbol,
            "volume":       lot_size,
            "type":         order_type,
            "price":        round(price, digits),
            "sl":           round(setup.sl, digits),
            "tp":           round(setup.tp, digits),
            "deviation":    20,
            "magic":        202400,   # AST Capital bot magic number
            "comment":      "AST_BOT",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error() if result is None else result.comment
            log_error(f"Order send failed: {err}")
            return None

        log_trade_open(
            symbol      = setup.symbol,
            direction   = setup.signal,
            entry_price = result.price,
            sl          = request["sl"],
            tp          = request["tp"],
            lot_size    = lot_size,
            reason      = setup.reason,
            ticket      = result.order,
        )
        return result.order

    def close_position(self, ticket: int) -> bool:
        """Manually close a specific open position."""
        if not _MT5_AVAILABLE:
            return False

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            log_error(f"Position {ticket} not found.")
            return False

        pos  = positions[0]
        tick = self.fetcher.get_tick(pos.symbol)
        if not tick:
            return False

        close_type  = _ORDER_SELL if pos.type == 0 else _ORDER_BUY
        close_price = tick["bid"]  if pos.type == 0 else tick["ask"]

        sym_info = self.fetcher.get_symbol_info(pos.symbol)
        digits   = sym_info["digits"] if sym_info else 5

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     ticket,
            "price":        round(close_price, digits),
            "deviation":    20,
            "magic":        202400,
            "comment":      "AST_BOT_CLOSE",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log_error(f"Close failed ticket={ticket}: {getattr(result, 'comment', '')}")
            return False

        log_trade_close(
            symbol      = pos.symbol,
            direction   = "BUY" if pos.type == 0 else "SELL",
            entry_price = pos.price_open,
            exit_price  = result.price,
            pnl         = pos.profit,
            exit_reason = "MANUAL_CLOSE",
            ticket      = ticket,
        )
        self._risk.record_pnl(pos.profit, self.fetcher.get_account_info()["balance"])
        return True

    def close_all(self) -> None:
        """Close every open position for this symbol."""
        for pos in self.fetcher.get_open_positions(self.symbol):
            self.close_position(pos["ticket"])

    # ─── Status callback ──────────────────────────────────────────────────────

    def _emit_status(self, account: dict, positions: list[dict]) -> None:
        if not self.on_status:
            return
        self.on_status({
            "mode":          "DEMO" if self.demo_mode else "LIVE",
            "balance":       account.get("balance", 0),
            "equity":        account.get("equity",  0),
            "daily_pnl":     round(self._risk.daily_pnl, 2),
            "daily_loss_pct":round(self._risk.daily_loss_pct(account.get("balance", 1)) * 100, 2),
            "open_positions":positions,
            "is_halted":     self._risk.is_halted,
            "timestamp":     datetime.utcnow().isoformat(),
        })

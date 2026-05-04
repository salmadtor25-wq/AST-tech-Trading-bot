"""
AST Capital — Auto-Trading Engine
Runs as an asyncio background task inside the FastAPI server.
Evaluates signals every BOT_LOOP_SECONDS; enforces all risk rules.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable

from app.config import (
    BOT_LOOP_SECONDS, LIVE_TRADING_ENABLED,
    SL_ATR_MULT, TP_ATR_MULT,
)
from app import indicators, strategy
from app.risk import RiskManager
from app.market import get_market_status

log = logging.getLogger("ast.trader")


class AutoTrader:
    """
    Attach to a live MT5Client and call start() to run.
    Call stop() for a graceful shutdown.
    """

    def __init__(
        self,
        client,                          # MT5Client instance
        symbol:    str     = "EURUSD",
        timeframe: str     = "H1",
        demo_mode: bool    = True,
        on_event:  Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.client    = client
        self.symbol    = symbol
        self.timeframe = timeframe
        self.demo_mode = demo_mode
        self.on_event  = on_event        # UI callback

        self._rm:      RiskManager  = RiskManager()
        self._running: bool         = False
        self._task:    Optional[asyncio.Task] = None

        # Log state
        self.log_entries: list[dict] = []
        self.last_signal: dict = {}
        self.last_eval_time: Optional[str] = None

        if not demo_mode and not LIVE_TRADING_ENABLED:
            raise RuntimeError(
                "LIVE trading blocked — set LIVE_TRADING_ENABLED=True in config.py "
                "only after thorough demo validation."
            )

    # ── Control ───────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task    = asyncio.create_task(self._loop())
        self._emit("bot_started", f"Bot started | {self.symbol} {self.timeframe} | "
                                  f"Mode: {'DEMO' if self.demo_mode else 'LIVE'}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._emit("bot_stopped", "Bot stopped")

    @property
    def running(self) -> bool:
        return self._running

    @property
    def risk_status(self) -> dict:
        acc = self.client.account_info()
        bal = acc["balance"] if acc else 10_000
        return self._rm.status(bal)

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._emit("error", f"Cycle error: {exc}")
                log.exception("Trader cycle error")
            await asyncio.sleep(BOT_LOOP_SECONDS)

    async def _cycle(self) -> None:
        now = datetime.utcnow()
        self.last_eval_time = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Market open?
        mkt = get_market_status(self.symbol)
        if not mkt["open"]:
            self._emit("market_closed", f"Market closed: {mkt['reason']}")
            return

        # 2. Account info + daily reset
        acc = self.client.account_info()
        if acc is None:
            self._emit("error", "Cannot retrieve account info")
            return
        balance = acc["balance"]
        self._rm.daily_reset(balance)

        if self._rm.is_halted:
            self._emit("risk_halt", "Daily loss limit active — no new trades")
            return

        # 3. Fetch & decorate data
        df = await asyncio.get_event_loop().run_in_executor(
            None, self.client.get_ohlcv, self.symbol, self.timeframe, 500
        )
        df = indicators.calculate(df)

        # 4. Check exits on open positions (trend-reversal exit)
        positions = self.client.get_positions(self.symbol)
        for pos in positions:
            should_exit, exit_reason = strategy.check_exit(pos, df)
            if should_exit:
                ok, msg = self.client.close_position(pos["ticket"])
                if ok:
                    self._emit("trade_closed",
                               f"CLOSED #{pos['ticket']} ({pos['type']}) — {exit_reason}")
                    self._rm.record_trade(pos["profit"], balance)

        # 5. Evaluate entry signal
        sig = strategy.evaluate(df)
        self.last_signal = sig

        if sig["signal"] == "NONE":
            self._emit("signal", f"No entry: {sig['reason']}")
            return

        # 6. Risk gate
        open_count = len(self.client.get_positions(self.symbol))
        can, block_reason = self._rm.can_trade(balance, open_count)
        if not can:
            self._emit("risk_block", block_reason)
            return

        # 7. Position sizing
        sl_dist = abs(sig["entry"] - sig["sl"]) if sig["sl"] else sig["atr"] * SL_ATR_MULT
        sym_info = self.client.symbol_info(self.symbol)
        if sym_info:
            lot = self._rm.lot_size(balance, sl_dist,
                                    sym_info["tick_size"], sym_info["tick_value"])
        else:
            lot = self._rm.lot_size_simple(balance, sl_dist)

        # 8. Place order
        ok, msg, ticket = self.client.place_order(
            symbol    = self.symbol,
            direction = sig["signal"],
            lot       = lot,
            sl        = sig["sl"],
            tp        = sig["tp"],
            comment   = f"AST_{self.symbol}",
        )

        if ok:
            self._emit("trade_opened",
                       f"OPENED {sig['signal']} #{ticket} | lot={lot} | "
                       f"SL={sig['sl']} TP={sig['tp']} | {sig['reason']}")
        else:
            self._emit("error", f"Order failed: {msg}")

    # ── Event emitter ─────────────────────────────────────────────────────────

    def _emit(self, event_type: str, message: str) -> None:
        entry = {
            "type":    event_type,
            "message": message,
            "time":    datetime.utcnow().strftime("%H:%M:%S"),
        }
        self.log_entries.append(entry)
        if len(self.log_entries) > 200:
            self.log_entries = self.log_entries[-200:]
        log.info("[%s] %s", event_type, message)
        if self.on_event:
            self.on_event(entry)

"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                   Risk Management Module                     ║
╚══════════════════════════════════════════════════════════════╝
Enforces:
  • 1% risk per trade (position sizing via ATR stop)
  • Max 3 simultaneous open trades
  • Daily loss limit of 5% — halts trading if breached

All monetary values are in the account's base currency.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

from config import (
    RISK_PER_TRADE, MAX_OPEN_TRADES, DAILY_LOSS_LIMIT,
    MIN_LOT_SIZE, MAX_LOT_SIZE, LOT_STEP,
)
from logger import log_info, log_warning, log_risk_block


class RiskManager:
    """
    Stateful risk manager.  Call reset_daily() at the start of each trading day.
    """

    def __init__(self) -> None:
        self._daily_loss: float     = 0.0   # cumulative realized P&L today
        self._trading_day: date     = datetime.utcnow().date()
        self._halt_triggered: bool  = False

    # ─── Daily state ──────────────────────────────────────────────────────────

    def reset_daily(self, current_balance: float) -> None:
        """Must be called once at session start and at each calendar day roll."""
        today = datetime.utcnow().date()
        if today != self._trading_day or self._halt_triggered:
            self._daily_loss      = 0.0
            self._trading_day     = today
            self._halt_triggered  = False
            log_info(f"Daily risk counter reset.  Balance: {current_balance:.2f}")

    def record_pnl(self, pnl: float, balance: float) -> None:
        """Call after every closed trade."""
        self._daily_loss += pnl
        if pnl < 0:
            self._check_daily_halt(balance)

    # ─── Gate checks (return False = blocked) ─────────────────────────────────

    def can_open_trade(
        self,
        balance: float,
        open_trade_count: int,
    ) -> tuple[bool, str]:
        """
        Master pre-trade check.
        Returns (allowed: bool, reason: str).
        """
        if self._halt_triggered:
            msg = "Daily loss limit already triggered — trading halted for today."
            log_risk_block(msg)
            return False, msg

        if open_trade_count >= MAX_OPEN_TRADES:
            msg = f"Max open trades ({MAX_OPEN_TRADES}) reached."
            log_risk_block(msg)
            return False, msg

        ok, msg = self._check_daily_loss_pre(balance)
        if not ok:
            log_risk_block(msg)
            return False, msg

        return True, "OK"

    def _check_daily_loss_pre(self, balance: float) -> tuple[bool, str]:
        if balance <= 0:
            return False, "Balance is zero or negative."
        loss_pct = -self._daily_loss / balance   # positive number = loss
        if loss_pct >= DAILY_LOSS_LIMIT:
            self._halt_triggered = True
            msg = (
                f"Daily loss limit {DAILY_LOSS_LIMIT*100:.1f}% breached "
                f"(current loss: {loss_pct*100:.2f}%).  Trading halted."
            )
            log_risk_block(msg)
            return False, msg
        return True, "OK"

    def _check_daily_halt(self, balance: float) -> None:
        self._check_daily_loss_pre(balance)

    # ─── Position sizing ──────────────────────────────────────────────────────

    def calculate_lot_size(
        self,
        balance:        float,
        sl_distance:    float,           # in price units (not pips)
        tick_size:      float = 0.00001, # symbol point size
        tick_value:     float = 1.0,     # value of one tick per 1 lot
        contract_size:  float = 100_000, # standard forex lot
    ) -> float:
        """
        Derive the lot size that risks exactly RISK_PER_TRADE of balance.

        Risk $    = balance × RISK_PER_TRADE
        SL ticks  = sl_distance / tick_size
        Risk/lot  = SL ticks × tick_value
        lots      = Risk $ / Risk/lot
        """
        if balance <= 0 or sl_distance <= 0:
            log_warning("Invalid balance or SL distance — returning min lot.")
            return MIN_LOT_SIZE

        risk_amount = balance * RISK_PER_TRADE
        sl_ticks    = sl_distance / tick_size
        risk_per_lot = sl_ticks * tick_value

        if risk_per_lot <= 0:
            log_warning("risk_per_lot is zero — returning min lot.")
            return MIN_LOT_SIZE

        raw_lots = risk_amount / risk_per_lot

        # Snap to the broker's lot step grid
        lots = math.floor(raw_lots / LOT_STEP) * LOT_STEP
        lots = max(MIN_LOT_SIZE, min(lots, MAX_LOT_SIZE))

        log_info(
            f"Position size | balance={balance:.2f}  risk={risk_amount:.2f}  "
            f"sl_dist={sl_distance:.5f}  lots={lots:.2f}"
        )
        return round(lots, 2)

    def calculate_lot_size_simple(
        self,
        balance:     float,
        sl_distance: float,
        pip_value:   float = 10.0,  # $ per pip per standard lot (EURUSD default)
        pip_size:    float = 0.0001,
    ) -> float:
        """
        Simplified sizing used in backtesting (no MT5 tick data available).
        pip_value=10 is correct for USD-denominated EURUSD accounts.
        """
        if balance <= 0 or sl_distance <= 0:
            return MIN_LOT_SIZE

        risk_amount  = balance * RISK_PER_TRADE
        sl_pips      = sl_distance / pip_size
        risk_per_lot = sl_pips * pip_value

        raw_lots = risk_amount / risk_per_lot if risk_per_lot > 0 else MIN_LOT_SIZE
        lots     = math.floor(raw_lots / LOT_STEP) * LOT_STEP
        return max(MIN_LOT_SIZE, min(round(lots, 2), MAX_LOT_SIZE))

    # ─── Accessors ────────────────────────────────────────────────────────────

    @property
    def daily_pnl(self) -> float:
        return self._daily_loss

    @property
    def is_halted(self) -> bool:
        return self._halt_triggered

    def daily_loss_pct(self, balance: float) -> float:
        """Daily loss as a fraction of current balance (positive = loss)."""
        if balance <= 0:
            return 0.0
        return max(0.0, -self._daily_loss / balance)

    def status_dict(self, balance: float) -> dict:
        return {
            "daily_pnl":         round(self._daily_loss, 2),
            "daily_loss_pct":    round(self.daily_loss_pct(balance) * 100, 2),
            "halt_triggered":    self._halt_triggered,
            "daily_loss_limit":  f"{DAILY_LOSS_LIMIT*100:.1f}%",
            "max_open_trades":   MAX_OPEN_TRADES,
            "risk_per_trade":    f"{RISK_PER_TRADE*100:.1f}%",
        }

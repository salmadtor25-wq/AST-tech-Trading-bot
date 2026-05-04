"""
AST Capital — Risk Manager
1% per trade · max 3 open trades · 5% daily loss halt
"""
from __future__ import annotations
import math
from datetime import datetime, date
from app.config import (
    RISK_PER_TRADE, MAX_OPEN_TRADES, DAILY_LOSS_LIMIT,
    MIN_LOT, MAX_LOT, LOT_STEP,
)


class RiskManager:
    def __init__(self) -> None:
        self._daily_pnl:  float = 0.0
        self._day:        date  = datetime.utcnow().date()
        self._halted:     bool  = False
        self._trades_today: int = 0

    # ── Daily reset ───────────────────────────────────────────────────────────

    def daily_reset(self, balance: float) -> None:
        today = datetime.utcnow().date()
        if today != self._day or self._halted:
            self._daily_pnl    = 0.0
            self._day          = today
            self._halted       = False
            self._trades_today = 0

    # ── Gate check ────────────────────────────────────────────────────────────

    def can_trade(self, balance: float, open_count: int) -> tuple[bool, str]:
        if self._halted:
            return False, "Daily loss limit triggered — halted until midnight UTC"
        if open_count >= MAX_OPEN_TRADES:
            return False, f"Max open trades ({MAX_OPEN_TRADES}) reached"
        loss_pct = self._loss_pct(balance)
        if loss_pct >= DAILY_LOSS_LIMIT:
            self._halted = True
            return False, f"Daily loss {loss_pct*100:.2f}% ≥ {DAILY_LOSS_LIMIT*100:.0f}% — halted"
        return True, "OK"

    # ── P&L recording ─────────────────────────────────────────────────────────

    def record_trade(self, pnl: float, balance: float) -> None:
        self._daily_pnl    += pnl
        self._trades_today += 1
        if self._loss_pct(balance) >= DAILY_LOSS_LIMIT:
            self._halted = True

    # ── Position sizing ───────────────────────────────────────────────────────

    def lot_size(
        self,
        balance:     float,
        sl_distance: float,
        tick_size:   float = 0.00001,
        tick_value:  float = 1.0,
    ) -> float:
        """
        Risk exactly RISK_PER_TRADE of balance.
        lot = risk_amount / (sl_ticks × tick_value_per_lot)
        """
        if balance <= 0 or sl_distance <= 0:
            return MIN_LOT
        risk   = balance * RISK_PER_TRADE
        ticks  = sl_distance / tick_size if tick_size > 0 else sl_distance / 0.00001
        r_lot  = ticks * tick_value
        if r_lot <= 0:
            return MIN_LOT
        raw    = risk / r_lot
        lots   = math.floor(raw / LOT_STEP) * LOT_STEP
        return max(MIN_LOT, min(round(lots, 2), MAX_LOT))

    def lot_size_simple(self, balance: float, sl_distance: float,
                        pip_value: float = 10.0, pip_size: float = 0.0001) -> float:
        """Fallback sizing used in backtest / when symbol info unavailable."""
        if balance <= 0 or sl_distance <= 0:
            return MIN_LOT
        risk    = balance * RISK_PER_TRADE
        sl_pips = sl_distance / pip_size
        r_lot   = sl_pips * pip_value
        if r_lot <= 0:
            return MIN_LOT
        raw  = risk / r_lot
        lots = math.floor(raw / LOT_STEP) * LOT_STEP
        return max(MIN_LOT, min(round(lots, 2), MAX_LOT))

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def daily_pnl(self)     -> float: return round(self._daily_pnl, 2)
    @property
    def is_halted(self)     -> bool:  return self._halted
    @property
    def trades_today(self)  -> int:   return self._trades_today

    def _loss_pct(self, balance: float) -> float:
        if balance <= 0:
            return 0.0
        return max(0.0, -self._daily_pnl / balance)

    def status(self, balance: float) -> dict:
        loss_pct = self._loss_pct(balance)
        return {
            "daily_pnl":        self.daily_pnl,
            "daily_loss_pct":   round(loss_pct * 100, 2),
            "daily_loss_limit": DAILY_LOSS_LIMIT * 100,
            "is_halted":        self._halted,
            "trades_today":     self._trades_today,
            "max_open_trades":  MAX_OPEN_TRADES,
            "risk_per_trade":   RISK_PER_TRADE * 100,
        }

"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                     Strategy Module                          ║
╚══════════════════════════════════════════════════════════════╝
Strategy:  EMA Trend-Filter + EMA Crossover + RSI confirmation

BUY  when: price > EMA200  AND  EMA50 crosses ABOVE EMA200
           AND  RSI between 50-70

SELL when: price < EMA200  AND  EMA50 crosses BELOW EMA200
           AND  RSI between 30-50

Exit:  SL = 1.5 × ATR  |  TP = 2.0 × ATR
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from config import (
    RSI_BUY_LOW, RSI_BUY_HIGH,
    RSI_SELL_LOW, RSI_SELL_HIGH,
    SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER,
)
from indicators import C_EMA50, C_EMA200, C_RSI, C_ATR, C_CROSS_UP, C_CROSS_DOWN
from logger import log_signal, log_debug


SignalType = Literal["BUY", "SELL", "NONE"]

SIGNAL_COL = "signal"          # added to the DataFrame


@dataclass
class TradeSetup:
    """All information needed to execute one trade."""
    signal:     SignalType
    symbol:     str
    entry_price: float
    sl:         float
    tp:         float
    atr:        float
    rsi:        float
    ema50:      float
    ema200:     float
    reason:     str
    bar_time:   Optional[object] = None

    @property
    def sl_distance(self) -> float:
        return abs(self.entry_price - self.sl)

    @property
    def tp_distance(self) -> float:
        return abs(self.tp - self.entry_price)

    @property
    def risk_reward(self) -> float:
        if self.sl_distance == 0:
            return 0.0
        return self.tp_distance / self.sl_distance


# ─── Signal Logic ─────────────────────────────────────────────────────────────

class SignalGenerator:
    """
    Generates vectorised signal column for backtesting AND
    evaluates the live signal for the latest bar.
    """

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add a 'signal' column ('BUY' / 'SELL' / 'NONE') to the DataFrame.
        Safe against look-ahead: conditions on columns[i] only.
        """
        df = df.copy()

        buy_cond = (
            (df["close"] > df[C_EMA200]) &     # price above trend filter
            df[C_CROSS_UP] &                   # fresh golden cross
            (df[C_RSI] >= RSI_BUY_LOW) &
            (df[C_RSI] <= RSI_BUY_HIGH)
        )

        sell_cond = (
            (df["close"] < df[C_EMA200]) &     # price below trend filter
            df[C_CROSS_DOWN] &                 # fresh death cross
            (df[C_RSI] >= RSI_SELL_LOW) &
            (df[C_RSI] <= RSI_SELL_HIGH)
        )

        df[SIGNAL_COL] = "NONE"
        df.loc[buy_cond,  SIGNAL_COL] = "BUY"
        df.loc[sell_cond, SIGNAL_COL] = "SELL"

        buys  = int(buy_cond.sum())
        sells = int(sell_cond.sum())
        log_debug(f"Signal scan complete — {buys} BUY, {sells} SELL signals found.")
        return df

    # ─── Live (single-bar) evaluation ────────────────────────────────────────

    def evaluate_latest(self, df: pd.DataFrame, symbol: str) -> Optional[TradeSetup]:
        """
        Check the most recent complete candle for an entry signal.
        Returns a TradeSetup if a signal is present, else None.
        """
        if len(df) < 2:
            return None

        row = df.iloc[-1]

        # Guard: skip if any indicator is NaN
        for col in [C_EMA50, C_EMA200, C_RSI, C_ATR]:
            if pd.isna(row[col]):
                return None

        close  = float(row["close"])
        ema50  = float(row[C_EMA50])
        ema200 = float(row[C_EMA200])
        rsi    = float(row[C_RSI])
        atr    = float(row[C_ATR])

        signal, reason = self._check_conditions(close, ema50, ema200, rsi, row)

        if signal == "NONE":
            return None

        sl, tp = self._compute_sl_tp(signal, close, atr)

        setup = TradeSetup(
            signal=signal,
            symbol=symbol,
            entry_price=close,
            sl=sl,
            tp=tp,
            atr=atr,
            rsi=rsi,
            ema50=ema50,
            ema200=ema200,
            reason=reason,
            bar_time=row.get("time"),
        )
        log_signal(symbol, signal, reason)
        return setup

    # ─── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _check_conditions(
        close: float, ema50: float, ema200: float, rsi: float, row: pd.Series
    ) -> tuple[SignalType, str]:
        cross_up   = bool(row[C_CROSS_UP])
        cross_down = bool(row[C_CROSS_DOWN])

        if (
            close > ema200 and
            cross_up and
            RSI_BUY_LOW <= rsi <= RSI_BUY_HIGH
        ):
            reason = (
                f"Price({close:.5f}) > EMA200({ema200:.5f}) | "
                f"EMA50({ema50:.5f}) crossed ABOVE EMA200 | "
                f"RSI={rsi:.1f} in [{RSI_BUY_LOW},{RSI_BUY_HIGH}]"
            )
            return "BUY", reason

        if (
            close < ema200 and
            cross_down and
            RSI_SELL_LOW <= rsi <= RSI_SELL_HIGH
        ):
            reason = (
                f"Price({close:.5f}) < EMA200({ema200:.5f}) | "
                f"EMA50({ema50:.5f}) crossed BELOW EMA200 | "
                f"RSI={rsi:.1f} in [{RSI_SELL_LOW},{RSI_SELL_HIGH}]"
            )
            return "SELL", reason

        return "NONE", ""

    @staticmethod
    def _compute_sl_tp(
        signal: SignalType, price: float, atr: float
    ) -> tuple[float, float]:
        sl_dist = atr * SL_ATR_MULTIPLIER
        tp_dist = atr * TP_ATR_MULTIPLIER
        if signal == "BUY":
            return price - sl_dist, price + tp_dist
        else:  # SELL
            return price + sl_dist, price - tp_dist

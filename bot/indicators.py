"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                    Indicators Module                         ║
╚══════════════════════════════════════════════════════════════╝
Calculates EMA-50, EMA-200, RSI-14, ATR-14 and derived signals.
Uses pandas + numpy directly (no external ta dependency required).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    EMA_FAST_PERIOD, EMA_SLOW_PERIOD,
    RSI_PERIOD, ATR_PERIOD,
)
from logger import log_debug, log_warning


# ─── Column names exposed to the rest of the system ──────────────────────────
C_EMA50       = "ema50"
C_EMA200      = "ema200"
C_RSI         = "rsi"
C_ATR         = "atr"
C_CROSS_UP    = "ema_cross_up"    # True on the candle where EMA50 crosses above EMA200
C_CROSS_DOWN  = "ema_cross_down"  # True on the candle where EMA50 crosses below EMA200


# ─── Low-level helpers ────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average — uses Wilder/pandas ewm convention."""
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI.  Returns values 0-100; NaN for the first `period` rows.
    """
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    # Wilder smoothing (equivalent to EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range using Wilder smoothing.
    TR = max(H-L, |H-prev_C|, |L-prev_C|)
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ─── Public API ───────────────────────────────────────────────────────────────

class IndicatorEngine:
    """
    Adds all required indicators to an OHLCV DataFrame in-place.
    All new columns are listed in the C_* constants above.
    """

    def __init__(
        self,
        ema_fast: int = EMA_FAST_PERIOD,
        ema_slow: int = EMA_SLOW_PERIOD,
        rsi_period: int = RSI_PERIOD,
        atr_period: int = ATR_PERIOD,
    ) -> None:
        self.ema_fast   = ema_fast
        self.ema_slow   = ema_slow
        self.rsi_period = rsi_period
        self.atr_period = atr_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Accept a copy-friendly DataFrame with columns [open, high, low, close].
        Returns the same DataFrame augmented with indicator columns.
        """
        df = df.copy()
        self._validate(df)

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        df[C_EMA50]  = _ema(close, self.ema_fast)
        df[C_EMA200] = _ema(close, self.ema_slow)
        df[C_RSI]    = _rsi(close, self.rsi_period)
        df[C_ATR]    = _atr(high, low, close, self.atr_period)

        # Crossover flags — True only on the EXACT candle the cross occurs
        prev_fast  = df[C_EMA50].shift(1)
        prev_slow  = df[C_EMA200].shift(1)
        df[C_CROSS_UP]   = (prev_fast <= prev_slow) & (df[C_EMA50] > df[C_EMA200])
        df[C_CROSS_DOWN] = (prev_fast >= prev_slow) & (df[C_EMA50] < df[C_EMA200])

        rows_before_valid = max(self.ema_slow, self.rsi_period, self.atr_period)
        valid_count = len(df) - rows_before_valid
        log_debug(
            f"Indicators calculated.  "
            f"Valid rows: {valid_count}/{len(df)}.  "
            f"Latest EMA50={df[C_EMA50].iloc[-1]:.5f}  "
            f"EMA200={df[C_EMA200].iloc[-1]:.5f}  "
            f"RSI={df[C_RSI].iloc[-1]:.1f}  "
            f"ATR={df[C_ATR].iloc[-1]:.5f}"
        )
        return df

    @staticmethod
    def _validate(df: pd.DataFrame) -> None:
        required = {"open", "high", "low", "close"}
        missing  = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing columns: {missing}")
        if len(df) < EMA_SLOW_PERIOD + 10:
            log_warning(
                f"Only {len(df)} bars available — need at least "
                f"{EMA_SLOW_PERIOD + 10} for reliable signals."
            )

    # ─── Convenience: snapshot of the latest bar ──────────────────────────────

    @staticmethod
    def latest_snapshot(df: pd.DataFrame) -> dict:
        """Return key indicator values for the most recent (complete) candle."""
        row = df.iloc[-1]
        return {
            "time":       row.get("time"),
            "close":      row["close"],
            "ema50":      row[C_EMA50],
            "ema200":     row[C_EMA200],
            "rsi":        row[C_RSI],
            "atr":        row[C_ATR],
            "cross_up":   bool(row[C_CROSS_UP]),
            "cross_down": bool(row[C_CROSS_DOWN]),
        }

"""
AST Capital — Enhanced Technical Indicators
EMA50, EMA200, RSI14, ATR14 + slope, ATR-MA, recent-high/low for candle confirmation.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from app.config import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    ATR_MA_PERIOD, EMA_SLOPE_BARS, CANDLE_LOOKBACK,
)


# ── Primitives ────────────────────────────────────────────────────────────────

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, min_periods=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta    = s.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/n, min_periods=n, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_c = close.shift(1)
    tr     = pd.concat([(high-low), (high-prev_c).abs(), (low-prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, min_periods=n, adjust=False).mean()


# ── Main calculation function ─────────────────────────────────────────────────

def calculate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accept an OHLCV DataFrame, return it augmented with all indicator columns.
    No side-effects — always returns a copy.
    """
    if df.empty or len(df) < EMA_SLOW + 10:
        return df.copy()

    df = df.copy()
    c, h, l, o = df["close"], df["high"], df["low"], df["open"]

    # Core indicators
    df["ema50"]  = _ema(c, EMA_FAST)
    df["ema200"] = _ema(c, EMA_SLOW)
    df["rsi"]    = _rsi(c, RSI_PERIOD)
    df["atr"]    = _atr(h, l, c, ATR_PERIOD)
    df["atr_ma"] = df["atr"].rolling(ATR_MA_PERIOD).mean()

    # EMA-200 slope: pct change over SLOPE_BARS (absolute value)
    # Reflects how "trending" the slow EMA is
    df["ema200_slope"] = df["ema200"].pct_change(EMA_SLOPE_BARS).abs()

    # Recent-high / recent-low: best high and low of the preceding LOOKBACK bars
    # shift(1) prevents using the current bar (no look-ahead)
    df["recent_high"] = h.shift(1).rolling(CANDLE_LOOKBACK).max()
    df["recent_low"]  = l.shift(1).rolling(CANDLE_LOOKBACK).min()

    # Candle body direction
    df["bullish"] = (c > o).astype(int)
    df["bearish"] = (c < o).astype(int)

    # EMA crossover markers (for chart annotations)
    p50, p200 = df["ema50"].shift(1), df["ema200"].shift(1)
    df["cross_up"]   = ((p50 <= p200) & (df["ema50"] > df["ema200"])).astype(int)
    df["cross_down"] = ((p50 >= p200) & (df["ema50"] < df["ema200"])).astype(int)

    return df


def to_chart_payload(df: pd.DataFrame) -> dict:
    """
    Convert a decorated DataFrame to the JSON payload consumed by the frontend chart.
    Timestamps are converted to Unix seconds (TradingView format).
    """
    def _ts(t) -> int:
        try:
            return int(pd.Timestamp(t).timestamp())
        except Exception:
            return 0

    valid = df.dropna(subset=["ema50", "ema200", "rsi", "atr"])

    candles = [
        {"time": _ts(r.time), "open": r.open, "high": r.high, "low": r.low, "close": r.close}
        for r in valid.itertuples()
    ]
    ema50  = [{"time": _ts(r.time), "value": round(r.ema50,  5)} for r in valid.itertuples()]
    ema200 = [{"time": _ts(r.time), "value": round(r.ema200, 5)} for r in valid.itertuples()]
    rsi    = [{"time": _ts(r.time), "value": round(r.rsi,    2)} for r in valid.itertuples()]
    atr    = [{"time": _ts(r.time), "value": round(r.atr,    5)} for r in valid.itertuples()]

    # Signal markers for cross events
    markers = []
    for r in valid.itertuples():
        if getattr(r, "cross_up", 0):
            markers.append({"time": _ts(r.time), "position": "belowBar",
                            "color": "#52A868", "shape": "arrowUp", "text": "EMA Cross ↑"})
        if getattr(r, "cross_down", 0):
            markers.append({"time": _ts(r.time), "position": "aboveBar",
                            "color": "#A85252", "shape": "arrowDown", "text": "EMA Cross ↓"})

    return {"candles": candles, "ema50": ema50, "ema200": ema200,
            "rsi": rsi, "atr": atr, "markers": markers}

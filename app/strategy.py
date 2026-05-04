"""
AST Capital — Enhanced Signal Engine
All 8 strategy conditions evaluated and returned with full transparency.

Condition summary
─────────────────────────────────────────────────────────────────
1. Trend filter    price > EMA200 AND EMA50 > EMA200  (BUY)
                   price < EMA200 AND EMA50 < EMA200  (SELL)
2. RSI momentum    BUY:  50 ≤ RSI ≤ 70  |  SELL: 30 ≤ RSI ≤ 50
3. RSI extremes    Avoid RSI > 80 or RSI < 20
4. Candle confirm  BUY:  bullish + close > recent 10-bar high
                   SELL: bearish + close < recent 10-bar low
5. Volatility      ATR ≥ ATR-MA × 0.70  (market is active)
6. No-trade: flat  |EMA200 slope| < 0.08 % over 20 bars → skip
7. No-trade: dead  RSI in [45, 55] → skip
8. Trend reversal  Exit open BUY if trend flips bearish (and vice-versa)
─────────────────────────────────────────────────────────────────
Entry only when conditions 1-5 are ALL met AND 6-7 are NOT triggered.
"""
from __future__ import annotations
import math
from typing import Literal, Optional
import pandas as pd
import numpy as np

from app.config import (
    RSI_BUY_MIN, RSI_BUY_MAX,
    RSI_SELL_MIN, RSI_SELL_MAX,
    RSI_OVERBOUGHT, RSI_OVERSOLD,
    RSI_DEAD_LOW, RSI_DEAD_HIGH,
    ATR_VOL_RATIO, EMA_SLOPE_THRESHOLD,
    SL_ATR_MULT, TP_ATR_MULT,
)

Signal = Literal["BUY", "SELL", "NONE"]


def evaluate(df: pd.DataFrame) -> dict:
    """
    Evaluate the strategy on the last complete candle of `df`.

    Returns
    -------
    {
        "signal":     "BUY" | "SELL" | "NONE",
        "reason":     str,
        "sl":         float | None,
        "tp":         float | None,
        "entry":      float | None,
        "atr":        float | None,
        "conditions": {
            # True = condition is MET (positive for a trade)
            "trend_buy":     bool,
            "trend_sell":    bool,
            "rsi_buy":       bool,
            "rsi_sell":      bool,
            "rsi_safe":      bool,   # RSI not in extreme zone
            "candle_buy":    bool,
            "candle_sell":   bool,
            "volatility":    bool,
            "trending":      bool,   # EMA slope active (not flat)
            "rsi_active":    bool,   # RSI outside dead zone
        },
        "values": {                  # raw indicator snapshot
            "close": float, "ema50": float, "ema200": float,
            "rsi": float, "atr": float, "atr_ma": float,
            "recent_high": float, "recent_low": float,
            "ema200_slope_pct": float,
        }
    }
    """
    MIN_ROWS = 210
    if len(df) < MIN_ROWS:
        return _empty("Insufficient data — need 210+ bars")

    row = df.iloc[-1]
    required = ["close","open","ema50","ema200","rsi","atr","atr_ma",
                "ema200_slope","recent_high","recent_low","bullish","bearish"]
    if any(pd.isna(row.get(c, float("nan"))) for c in required):
        return _empty("Indicators still warming up")

    # Raw values
    close        = float(row["close"])
    open_        = float(row["open"])
    ema50        = float(row["ema50"])
    ema200       = float(row["ema200"])
    rsi          = float(row["rsi"])
    atr          = float(row["atr"])
    atr_ma       = float(row["atr_ma"])
    slope        = float(row["ema200_slope"])   # already abs()
    recent_high  = float(row["recent_high"])
    recent_low   = float(row["recent_low"])
    is_bullish   = bool(row["bullish"])
    is_bearish   = bool(row["bearish"])

    # ── Individual conditions ─────────────────────────────────────────────────
    trend_buy    = (close > ema200) and (ema50 > ema200)
    trend_sell   = (close < ema200) and (ema50 < ema200)
    rsi_buy      = RSI_BUY_MIN  <= rsi <= RSI_BUY_MAX
    rsi_sell     = RSI_SELL_MIN <= rsi <= RSI_SELL_MAX
    rsi_safe     = not (rsi > RSI_OVERBOUGHT or rsi < RSI_OVERSOLD)
    candle_buy   = is_bullish and (close > recent_high)
    candle_sell  = is_bearish and (close < recent_low)
    volatility   = (atr >= atr_ma * ATR_VOL_RATIO) if atr_ma > 0 else False
    trending     = slope >= EMA_SLOPE_THRESHOLD
    rsi_active   = not (RSI_DEAD_LOW <= rsi <= RSI_DEAD_HIGH)

    cond = {
        "trend_buy":   trend_buy,   "trend_sell":  trend_sell,
        "rsi_buy":     rsi_buy,     "rsi_sell":    rsi_sell,
        "rsi_safe":    rsi_safe,    "candle_buy":  candle_buy,
        "candle_sell": candle_sell, "volatility":  volatility,
        "trending":    trending,    "rsi_active":  rsi_active,
    }

    vals = {
        "close": round(close, 5),   "ema50":  round(ema50,  5),
        "ema200": round(ema200, 5), "rsi":    round(rsi,    2),
        "atr":   round(atr,    5),  "atr_ma": round(atr_ma, 5),
        "recent_high": round(recent_high, 5),
        "recent_low":  round(recent_low,  5),
        "ema200_slope_pct": round(slope * 100, 4),
    }

    # ── No-trade gates ───────────────────────────────────────────────────────
    if not trending:
        return _result("NONE", f"Sideways market — EMA200 slope {slope*100:.4f}% < threshold",
                       None, None, close, atr, cond, vals)
    if not rsi_active:
        return _result("NONE", f"RSI dead zone ({rsi:.1f}) — no momentum",
                       None, None, close, atr, cond, vals)
    if not volatility:
        return _result("NONE", f"Low volatility — ATR({atr:.5f}) < 70% of ATR-MA({atr_ma:.5f})",
                       None, None, close, atr, cond, vals)
    if not rsi_safe:
        return _result("NONE", f"RSI extreme ({rsi:.1f}) — overbought/oversold",
                       None, None, close, atr, cond, vals)

    # ── Entry signals (ALL buy/sell conditions must align) ───────────────────
    if trend_buy and rsi_buy and candle_buy:
        sl = close - atr * SL_ATR_MULT
        tp = close + atr * TP_ATR_MULT
        reason = (
            f"BUY — Trend↑ EMA50({ema50:.5f})>EMA200({ema200:.5f}) | "
            f"RSI={rsi:.1f} [{RSI_BUY_MIN}-{RSI_BUY_MAX}] | "
            f"Bullish candle breaks {CANDLE_LOOKBACK}-bar high({recent_high:.5f})"
        )
        return _result("BUY", reason, sl, tp, close, atr, cond, vals)

    if trend_sell and rsi_sell and candle_sell:
        sl = close + atr * SL_ATR_MULT
        tp = close - atr * TP_ATR_MULT
        reason = (
            f"SELL — Trend↓ EMA50({ema50:.5f})<EMA200({ema200:.5f}) | "
            f"RSI={rsi:.1f} [{RSI_SELL_MIN}-{RSI_SELL_MAX}] | "
            f"Bearish candle breaks {CANDLE_LOOKBACK}-bar low({recent_low:.5f})"
        )
        return _result("SELL", reason, sl, tp, close, atr, cond, vals)

    # Partial alignment — explain which condition is missing
    if trend_buy:
        missing = []
        if not rsi_buy:    missing.append(f"RSI={rsi:.1f} not in [{RSI_BUY_MIN}-{RSI_BUY_MAX}]")
        if not candle_buy: missing.append(f"Close({close:.5f}) didn't break high({recent_high:.5f})")
        reason = "BUY conditions partial — missing: " + "; ".join(missing)
    elif trend_sell:
        missing = []
        if not rsi_sell:    missing.append(f"RSI={rsi:.1f} not in [{RSI_SELL_MIN}-{RSI_SELL_MAX}]")
        if not candle_sell: missing.append(f"Close({close:.5f}) didn't break low({recent_low:.5f})")
        reason = "SELL conditions partial — missing: " + "; ".join(missing)
    else:
        reason = f"No trend alignment — Price({close:.5f}) vs EMA200({ema200:.5f}), EMA50({ema50:.5f})"

    return _result("NONE", reason, None, None, close, atr, cond, vals)


def check_exit(position: dict, df: pd.DataFrame) -> tuple[bool, str]:
    """
    Return (should_exit, reason) for an open position based on trend reversal.
    Called each bar for every open position.
    """
    if len(df) < 2 or df["ema50"].isna().iloc[-1] or df["ema200"].isna().iloc[-1]:
        return False, ""

    row   = df.iloc[-1]
    close = float(row["close"])
    ema50 = float(row["ema50"])
    ema200= float(row["ema200"])
    rsi   = float(row["rsi"]) if not pd.isna(row["rsi"]) else 50.0

    direction = position.get("type", "")
    if direction == "BUY":
        if close < ema200 and ema50 < ema200:
            return True, "Trend reversal — price & EMA50 crossed below EMA200"
        if rsi > RSI_OVERBOUGHT:
            return True, f"RSI overbought ({rsi:.1f}) — exit BUY"
    elif direction == "SELL":
        if close > ema200 and ema50 > ema200:
            return True, "Trend reversal — price & EMA50 crossed above EMA200"
        if rsi < RSI_OVERSOLD:
            return True, f"RSI oversold ({rsi:.1f}) — exit SELL"

    return False, ""


# ── Private helpers ───────────────────────────────────────────────────────────

def _empty(reason: str) -> dict:
    return {"signal": "NONE", "reason": reason, "sl": None, "tp": None,
            "entry": None, "atr": None, "conditions": {}, "values": {}}


def _result(signal, reason, sl, tp, entry, atr, cond, vals) -> dict:
    return {
        "signal": signal, "reason": reason,
        "sl":     round(sl,    5) if sl    is not None else None,
        "tp":     round(tp,    5) if tp    is not None else None,
        "entry":  round(entry, 5) if entry is not None else None,
        "atr":    round(atr,   5) if atr   is not None else None,
        "conditions": cond, "values": vals,
    }

"""
AST Capital — MetaTrader 5 Client
Wraps the MT5 Python API with graceful fallbacks for offline/Linux use.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.config import BARS_TO_FETCH, DATA_DIR

try:
    import MetaTrader5 as mt5
    _MT5 = True
except ImportError:
    _MT5 = False


class MT5Client:
    """
    Thread-safe (per-instance) wrapper around MetaTrader5.
    All public methods return plain Python dicts/lists — no MT5 types leak out.
    """

    def __init__(self) -> None:
        self._connected = False
        self._login_info: dict = {}

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, login: int, password: str, server: str) -> tuple[bool, str]:
        if not _MT5:
            return False, "MetaTrader5 package not installed (Windows required for live data)."

        if not mt5.initialize():
            return False, f"MT5 initialize() failed: {mt5.last_error()}"

        if not mt5.login(login=int(login), password=password, server=server):
            mt5.shutdown()
            return False, f"MT5 login failed: {mt5.last_error()}"

        info = mt5.account_info()
        self._connected = True
        self._login_info = {
            "login":    info.login,
            "name":     info.name,
            "server":   info.server,
            "currency": info.currency,
            "leverage": info.leverage,
            "balance":  info.balance,
            "equity":   info.equity,
        }
        return True, f"Connected — {info.name} @ {info.server}"

    def disconnect(self) -> None:
        if _MT5 and self._connected:
            mt5.shutdown()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Account ───────────────────────────────────────────────────────────────

    def account_info(self) -> Optional[dict]:
        if not (self._connected and _MT5):
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "login":        info.login,
            "name":         info.name,
            "server":       info.server,
            "currency":     info.currency,
            "leverage":     info.leverage,
            "balance":      round(info.balance,  2),
            "equity":       round(info.equity,   2),
            "margin":       round(info.margin,   2),
            "free_margin":  round(info.margin_free, 2),
            "margin_level": round(info.margin_level, 2) if info.margin_level else 0,
            "profit":       round(info.profit,   2),
        }

    # ── Market data ───────────────────────────────────────────────────────────

    _TF_MAP = {
        "M1":  1,  "M5":  5,  "M15": 15, "M30": 30,
        "H1":  60, "H4":  240, "D1": 1440,
    }

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "H1",
        bars: int = BARS_TO_FETCH,
    ) -> pd.DataFrame:
        if self._connected and _MT5:
            df = self._from_mt5(symbol, timeframe, bars)
            if df is not None and not df.empty:
                self._cache(df, symbol, timeframe)
                return df
        return self._from_cache_or_synthetic(symbol, timeframe, bars)

    def _from_mt5(self, symbol: str, tf: str, bars: int) -> Optional[pd.DataFrame]:
        tf_const = getattr(mt5, f"TIMEFRAME_{tf}", None)
        if tf_const is None:
            return None
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time","open","high","low","close","volume"]].sort_values("time").reset_index(drop=True)

    def _cache(self, df: pd.DataFrame, symbol: str, tf: str) -> None:
        df.to_csv(DATA_DIR / f"{symbol}_{tf}.csv", index=False)

    def _from_cache_or_synthetic(self, symbol: str, tf: str, bars: int) -> pd.DataFrame:
        path = DATA_DIR / f"{symbol}_{tf}.csv"
        if path.exists():
            df = pd.read_csv(path, parse_dates=["time"])
            return df.tail(bars).reset_index(drop=True)
        return self._synthetic(bars, tf)

    @staticmethod
    def _synthetic(bars: int, tf: str) -> pd.DataFrame:
        mins = {"M5":5,"M15":15,"H1":60,"H4":240,"D1":1440}.get(tf, 60)
        np.random.seed(42)
        times  = pd.date_range(end=datetime.utcnow(), periods=bars, freq=f"{mins}min", tz="UTC")
        closes = 1.10 + np.cumsum(np.random.normal(0, 0.0005, bars))
        opens  = np.roll(closes, 1);  opens[0] = closes[0]
        highs  = np.maximum(opens, closes) + np.abs(np.random.normal(0, 0.0003, bars))
        lows   = np.minimum(opens, closes) - np.abs(np.random.normal(0, 0.0003, bars))
        return pd.DataFrame({"time": times, "open": opens, "high": highs,
                             "low": lows, "close": closes, "volume": np.random.randint(500,5000,bars).astype(float)})

    def get_tick(self, symbol: str) -> Optional[dict]:
        if not (self._connected and _MT5):
            return None
        t = mt5.symbol_info_tick(symbol)
        if t is None:
            return None
        return {"bid": t.bid, "ask": t.ask, "time": int(t.time),
                "spread": round((t.ask - t.bid) * 1e5, 1)}

    def symbol_info(self, symbol: str) -> Optional[dict]:
        if not (self._connected and _MT5):
            return None
        i = mt5.symbol_info(symbol)
        if i is None:
            return None
        return {"tick_size": i.trade_tick_size, "tick_value": i.trade_tick_value,
                "contract_size": i.trade_contract_size, "vol_min": i.volume_min,
                "vol_max": i.volume_max, "vol_step": i.volume_step, "digits": i.digits,
                "point": i.point}

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self, symbol: Optional[str] = None) -> list[dict]:
        if not (self._connected and _MT5):
            return []
        pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if pos is None:
            return []
        return [{
            "ticket":     p.ticket,
            "symbol":     p.symbol,
            "type":       "BUY" if p.type == 0 else "SELL",
            "volume":     p.volume,
            "price_open": p.price_open,
            "price_cur":  p.price_current,
            "sl":         p.sl,
            "tp":         p.tp,
            "profit":     round(p.profit, 2),
            "swap":       round(p.swap,   2),
            "time":       datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M"),
            "comment":    p.comment,
        } for p in pos]

    # ── History ───────────────────────────────────────────────────────────────

    def get_history(self, days: int = 30) -> list[dict]:
        if not (self._connected and _MT5):
            return []
        from datetime import timedelta
        t_from = datetime.utcnow() - timedelta(days=days)
        deals  = mt5.history_deals_get(t_from, datetime.utcnow())
        if deals is None:
            return []
        return [{
            "ticket":  d.ticket,
            "symbol":  d.symbol,
            "type":    "BUY" if d.type == 0 else "SELL" if d.type == 1 else "OTHER",
            "volume":  d.volume,
            "price":   d.price,
            "profit":  round(d.profit, 2),
            "commission": round(d.commission, 2),
            "swap":    round(d.swap, 2),
            "time":    datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M"),
            "comment": d.comment,
        } for d in deals if d.symbol != ""]

    # ── Order execution ───────────────────────────────────────────────────────

    def place_order(self, symbol: str, direction: str, lot: float,
                    sl: float, tp: float, comment: str = "AST_BOT") -> tuple[bool, str, int]:
        if not (self._connected and _MT5):
            return False, "Not connected", 0

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False, "Cannot get tick", 0

        si = mt5.symbol_info(symbol)
        digits = si.digits if si else 5

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price      = tick.ask if direction == "BUY" else tick.bid

        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot,
            "type":         order_type,
            "price":        round(price, digits),
            "sl":           round(sl, digits),
            "tp":           round(tp, digits),
            "deviation":    20,
            "magic":        202500,
            "comment":      comment,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            err = getattr(res, "comment", str(mt5.last_error()))
            return False, err, 0
        return True, "Order placed", res.order

    def close_position(self, ticket: int) -> tuple[bool, str]:
        if not (self._connected and _MT5):
            return False, "Not connected"
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False, "Position not found"
        pos  = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return False, "Cannot get tick"
        close_type  = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        close_price = tick.bid if pos.type == 0 else tick.ask
        si     = mt5.symbol_info(pos.symbol)
        digits = si.digits if si else 5
        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     ticket,
            "price":        round(close_price, digits),
            "deviation":    20,
            "magic":        202500,
            "comment":      "AST_CLOSE",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            return False, getattr(res, "comment", "Unknown error")
        return True, f"Closed ticket {ticket}"

    def close_all(self, symbol: Optional[str] = None) -> list[dict]:
        results = []
        for pos in self.get_positions(symbol):
            ok, msg = self.close_position(pos["ticket"])
            results.append({"ticket": pos["ticket"], "ok": ok, "msg": msg})
        return results

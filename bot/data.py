"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                      Data Module                             ║
╚══════════════════════════════════════════════════════════════╝
Fetches OHLCV data from MetaTrader 5.
Falls back to CSV cache when MT5 is unavailable (backtest-only mode).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from config import (
    BARS_TO_FETCH, DATA_DIR, TIMEFRAME_MAP, DEFAULT_SYMBOL
)
from logger import log_info, log_error, log_warning, log_debug

# MT5 is only available on Windows; graceful fallback for other platforms
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False
    log_warning("MetaTrader5 package not found — live data disabled. Using CSV fallback.")


# ─── Column name constants ────────────────────────────────────────────────────
COL_OPEN   = "open"
COL_HIGH   = "high"
COL_LOW    = "low"
COL_CLOSE  = "close"
COL_VOLUME = "volume"
COL_TIME   = "time"

REQUIRED_COLS = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]


class DataFetcher:
    """Thin wrapper around the MT5 API with CSV caching."""

    def __init__(self) -> None:
        self._connected = False

    # ─── Connection ───────────────────────────────────────────────────────────

    def connect(self, login: int, password: str, server: str) -> bool:
        """Initialise and log in to the MT5 terminal."""
        if not _MT5_AVAILABLE:
            log_error("MetaTrader5 package unavailable — cannot connect.")
            return False

        if not mt5.initialize():
            log_error(f"MT5 initialize() failed: {mt5.last_error()}")
            return False

        auth = mt5.login(login=int(login), password=password, server=server)
        if not auth:
            log_error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        info = mt5.account_info()
        log_info(f"Connected to MT5 | Account: {info.login} | "
                 f"Balance: {info.balance:.2f} {info.currency} | "
                 f"Server: {info.server}")
        self._connected = True
        return True

    def disconnect(self) -> None:
        if _MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            log_info("MT5 connection closed.")

    @property
    def connected(self) -> bool:
        return self._connected

    # ─── Historical data ──────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: str = "H1",
        bars: int = BARS_TO_FETCH,
    ) -> pd.DataFrame:
        """
        Return a DataFrame with columns [time, open, high, low, close, volume].
        Tries MT5 first; falls back to local CSV cache.
        """
        if self._connected and _MT5_AVAILABLE:
            df = self._fetch_from_mt5(symbol, timeframe, bars)
            if df is not None and not df.empty:
                self._save_cache(df, symbol, timeframe)
                return df

        # Fallback: use cached CSV
        return self._load_cache(symbol, timeframe, bars)

    def _fetch_from_mt5(
        self, symbol: str, timeframe: str, bars: int
    ) -> Optional[pd.DataFrame]:
        tf_code = self._resolve_timeframe(timeframe)
        if tf_code is None:
            log_error(f"Unknown timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, bars)
        if rates is None or len(rates) == 0:
            log_error(f"MT5 copy_rates_from_pos failed: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"tick_volume": "volume"})[
            ["time", "open", "high", "low", "close", "volume"]
        ]
        df = df.sort_values("time").reset_index(drop=True)
        log_debug(f"Fetched {len(df)} bars of {symbol} {timeframe} from MT5.")
        return df

    @staticmethod
    def _resolve_timeframe(timeframe: str):
        """Map string timeframe to MT5 constant."""
        if not _MT5_AVAILABLE:
            return None
        mapping = {
            "M1":  mt5.TIMEFRAME_M1,
            "M5":  mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1":  mt5.TIMEFRAME_H1,
            "H4":  mt5.TIMEFRAME_H4,
            "D1":  mt5.TIMEFRAME_D1,
        }
        return mapping.get(timeframe.upper())

    # ─── CSV cache ────────────────────────────────────────────────────────────

    def _cache_path(self, symbol: str, timeframe: str) -> Path:
        return DATA_DIR / f"{symbol}_{timeframe}.csv"

    def _save_cache(self, df: pd.DataFrame, symbol: str, timeframe: str) -> None:
        path = self._cache_path(symbol, timeframe)
        df.to_csv(path, index=False)
        log_debug(f"Cache saved: {path}")

    def _load_cache(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        path = self._cache_path(symbol, timeframe)
        if path.exists():
            df = pd.read_csv(path, parse_dates=["time"])
            df = df.tail(bars).reset_index(drop=True)
            log_info(f"Loaded {len(df)} rows from cache: {path.name}")
            return df

        log_warning(f"No cache found for {symbol} {timeframe} — generating synthetic data.")
        return self._generate_synthetic(symbol, timeframe, bars)

    @staticmethod
    def _generate_synthetic(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        """
        Produce random-walk OHLCV data for offline testing.
        NOT suitable for strategy validation — use real data.
        """
        np.random.seed(42)
        minutes_per_bar = TIMEFRAME_MAP.get(timeframe, 60)
        times  = pd.date_range(end=datetime.utcnow(), periods=bars,
                               freq=f"{minutes_per_bar}min", tz="UTC")
        closes = 1.10 + np.cumsum(np.random.normal(0, 0.0005, bars))
        opens  = np.roll(closes, 1)
        opens[0] = closes[0]
        highs  = np.maximum(opens, closes) + np.abs(np.random.normal(0, 0.0003, bars))
        lows   = np.minimum(opens, closes) - np.abs(np.random.normal(0, 0.0003, bars))
        volumes = np.random.randint(500, 5000, bars).astype(float)

        df = pd.DataFrame({
            "time": times, "open": opens, "high": highs,
            "low": lows, "close": closes, "volume": volumes,
        })
        log_warning("Using synthetic data — results are NOT meaningful for real trading.")
        return df

    # ─── Live price ───────────────────────────────────────────────────────────

    def get_tick(self, symbol: str) -> Optional[dict]:
        """Return {'bid': float, 'ask': float, 'time': datetime} or None."""
        if not (self._connected and _MT5_AVAILABLE):
            return None
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {
            "bid":  tick.bid,
            "ask":  tick.ask,
            "time": datetime.fromtimestamp(tick.time),
        }

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """Return symbol metadata needed for position sizing."""
        if not (self._connected and _MT5_AVAILABLE):
            return None
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "trade_tick_size":  info.trade_tick_size,
            "trade_tick_value": info.trade_tick_value,
            "trade_contract_size": info.trade_contract_size,
            "volume_min":       info.volume_min,
            "volume_max":       info.volume_max,
            "volume_step":      info.volume_step,
            "digits":           info.digits,
            "point":            info.point,
        }

    # ─── Account ──────────────────────────────────────────────────────────────

    def get_account_info(self) -> Optional[dict]:
        """Return key account metrics."""
        if not (self._connected and _MT5_AVAILABLE):
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "login":    info.login,
            "balance":  info.balance,
            "equity":   info.equity,
            "margin":   info.margin,
            "free_margin": info.margin_free,
            "currency": info.currency,
            "leverage": info.leverage,
            "server":   info.server,
        }

    def get_open_positions(self, symbol: Optional[str] = None) -> list[dict]:
        """Return list of open positions as dicts."""
        if not (self._connected and _MT5_AVAILABLE):
            return []
        positions = (
            mt5.positions_get(symbol=symbol)
            if symbol else mt5.positions_get()
        )
        if positions is None:
            return []
        return [
            {
                "ticket":       p.ticket,
                "symbol":       p.symbol,
                "type":         "BUY" if p.type == 0 else "SELL",
                "volume":       p.volume,
                "price_open":   p.price_open,
                "sl":           p.sl,
                "tp":           p.tp,
                "profit":       p.profit,
                "time":         datetime.fromtimestamp(p.time),
            }
            for p in positions
        ]

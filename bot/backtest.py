"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                    Backtest Engine                           ║
╚══════════════════════════════════════════════════════════════╝
Event-driven bar-by-bar backtest — no look-ahead bias.
Position sizing mirrors the live RiskManager.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import matplotlib
matplotlib.use("Agg")   # headless default; overridden to TkAgg in UI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from config import (
    SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER,
    RISK_PER_TRADE, MAX_OPEN_TRADES, DAILY_LOSS_LIMIT,
    MIN_LOT_SIZE, LOT_STEP, COLORS,
)
from indicators import C_EMA50, C_EMA200, C_RSI, C_ATR, SIGNAL_COL
from risk import RiskManager
from logger import log_info, log_warning, log_separator


# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    idx:          int
    direction:    Literal["BUY", "SELL"]
    entry_price:  float
    sl:           float
    tp:           float
    lot_size:     float
    entry_time:   object
    atr_at_entry: float

    exit_price:   Optional[float] = None
    exit_time:    Optional[object] = None
    pnl:          float = 0.0
    exit_reason:  str = ""
    closed:       bool = False

    @property
    def r_multiple(self) -> float:
        """How many R's were gained/lost (SL risk = 1R)."""
        sl_dist = abs(self.entry_price - self.sl)
        if sl_dist == 0:
            return 0.0
        dist = (
            (self.exit_price - self.entry_price)
            if self.direction == "BUY"
            else (self.entry_price - self.exit_price)
        )
        return dist / sl_dist if self.exit_price else 0.0


@dataclass
class BacktestResults:
    initial_balance:  float
    final_balance:    float
    trades:           list[BacktestTrade] = field(default_factory=list)
    equity_curve:     list[float] = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl > 0)

    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl <= 0)

    @property
    def win_rate(self) -> float:
        return self.winning_trades / self.total_trades if self.total_trades else 0.0

    @property
    def net_pnl(self) -> float:
        return self.final_balance - self.initial_balance

    @property
    def return_pct(self) -> float:
        return self.net_pnl / self.initial_balance * 100 if self.initial_balance else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for v in self.equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def profit_factor(self) -> float:
        gross_win  = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return gross_win / gross_loss if gross_loss > 0 else float("inf")

    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def expectancy(self) -> float:
        return (self.win_rate * self.avg_win) + ((1 - self.win_rate) * self.avg_loss)

    def summary(self) -> str:
        bar = "─" * 56
        lines = [
            "",
            "╔" + "═" * 56 + "╗",
            "║{:^56}║".format("  AST CAPITAL — BACKTEST RESULTS  "),
            "╠" + "═" * 56 + "╣",
            f"║  {'Initial Balance':<28} {self.initial_balance:>12.2f}  ║",
            f"║  {'Final Balance':<28} {self.final_balance:>12.2f}  ║",
            f"║  {'Net P&L':<28} {self.net_pnl:>+12.2f}  ║",
            f"║  {'Return':<28} {self.return_pct:>11.2f}%  ║",
            "╠" + "─" * 56 + "╣",
            f"║  {'Total Trades':<28} {self.total_trades:>12}  ║",
            f"║  {'Win Rate':<28} {self.win_rate*100:>11.1f}%  ║",
            f"║  {'Winning Trades':<28} {self.winning_trades:>12}  ║",
            f"║  {'Losing Trades':<28} {self.losing_trades:>12}  ║",
            "╠" + "─" * 56 + "╣",
            f"║  {'Average Win':<28} {self.avg_win:>+12.2f}  ║",
            f"║  {'Average Loss':<28} {self.avg_loss:>+12.2f}  ║",
            f"║  {'Expectancy / Trade':<28} {self.expectancy:>+12.2f}  ║",
            f"║  {'Profit Factor':<28} {self.profit_factor:>12.2f}  ║",
            "╠" + "─" * 56 + "╣",
            f"║  {'Max Drawdown':<28} {self.max_drawdown*100:>11.2f}%  ║",
            "╚" + "═" * 56 + "╝",
        ]
        return "\n".join(lines)


# ─── Engine ───────────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Bar-by-bar simulation.  On each bar:
      1. Check exits on open positions (SL / TP hit, checked against H/L).
      2. If no open position on this symbol, check for entry signal.
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        pip_value:       float = 10.0,    # $ per pip per standard lot (USD account, EURUSD)
        pip_size:        float = 0.0001,
    ) -> None:
        self.initial_balance = initial_balance
        self.pip_value       = pip_value
        self.pip_size        = pip_size
        self._rm             = RiskManager()

    def run(self, df: pd.DataFrame) -> BacktestResults:
        """
        Run the backtest on a fully-decorated DataFrame
        (must have SIGNAL_COL, ATR, EMA columns already computed).
        """
        balance     = self.initial_balance
        open_trades: list[BacktestTrade] = []
        closed:      list[BacktestTrade] = []
        equity_curve = [balance]

        self._rm.reset_daily(balance)

        for i in range(len(df)):
            row = df.iloc[i]

            # ── 1. Check exits for all open positions ──────────────────────
            still_open = []
            for trade in open_trades:
                closed_trade = self._check_exit(trade, row)
                if closed_trade:
                    balance += closed_trade.pnl
                    self._rm.record_pnl(closed_trade.pnl, balance)
                    closed.append(closed_trade)
                else:
                    still_open.append(trade)
            open_trades = still_open

            # ── 2. Check for entry signal ──────────────────────────────────
            signal = str(row.get(SIGNAL_COL, "NONE"))
            if signal in ("BUY", "SELL"):
                can_trade, _ = self._rm.can_open_trade(balance, len(open_trades))
                if can_trade:
                    atr = float(row[C_ATR])
                    if not math.isnan(atr) and atr > 0:
                        trade = self._open_trade(i, row, signal, balance, atr)
                        if trade:
                            open_trades.append(trade)

            equity_curve.append(balance)

        # Force-close any positions still open at end of data
        for trade in open_trades:
            last = df.iloc[-1]
            trade.exit_price  = float(last["close"])
            trade.exit_time   = last.get("time")
            trade.exit_reason = "END_OF_DATA"
            trade.pnl         = self._calc_pnl(trade, trade.exit_price)
            trade.closed      = True
            balance += trade.pnl
            closed.append(trade)

        results = BacktestResults(
            initial_balance=self.initial_balance,
            final_balance=balance,
            trades=closed,
            equity_curve=equity_curve,
        )
        log_info(results.summary())
        return results

    # ─── Trade lifecycle ──────────────────────────────────────────────────────

    def _open_trade(
        self,
        idx: int,
        row: pd.Series,
        signal: str,
        balance: float,
        atr: float,
    ) -> Optional[BacktestTrade]:
        price  = float(row["close"])
        sl_d   = atr * SL_ATR_MULTIPLIER
        tp_d   = atr * TP_ATR_MULTIPLIER

        if signal == "BUY":
            sl, tp = price - sl_d, price + tp_d
        else:
            sl, tp = price + sl_d, price - tp_d

        lot_size = self._rm.calculate_lot_size_simple(
            balance, sl_d, self.pip_value, self.pip_size
        )

        return BacktestTrade(
            idx=idx,
            direction=signal,
            entry_price=price,
            sl=sl,
            tp=tp,
            lot_size=lot_size,
            entry_time=row.get("time"),
            atr_at_entry=atr,
        )

    def _check_exit(
        self, trade: BacktestTrade, row: pd.Series
    ) -> Optional[BacktestTrade]:
        """Check if SL or TP was hit during this bar (uses High/Low)."""
        high  = float(row["high"])
        low   = float(row["low"])
        close = float(row["close"])
        time  = row.get("time")

        if trade.direction == "BUY":
            if low <= trade.sl:
                return self._close_trade(trade, trade.sl, time, "STOP_LOSS")
            if high >= trade.tp:
                return self._close_trade(trade, trade.tp, time, "TAKE_PROFIT")
        else:  # SELL
            if high >= trade.sl:
                return self._close_trade(trade, trade.sl, time, "STOP_LOSS")
            if low <= trade.tp:
                return self._close_trade(trade, trade.tp, time, "TAKE_PROFIT")
        return None

    def _close_trade(
        self,
        trade: BacktestTrade,
        exit_price: float,
        exit_time: object,
        reason: str,
    ) -> BacktestTrade:
        trade.exit_price  = exit_price
        trade.exit_time   = exit_time
        trade.exit_reason = reason
        trade.pnl         = self._calc_pnl(trade, exit_price)
        trade.closed      = True
        return trade

    def _calc_pnl(self, trade: BacktestTrade, exit_price: float) -> float:
        pips = (
            (exit_price - trade.entry_price) / self.pip_size
            if trade.direction == "BUY"
            else (trade.entry_price - exit_price) / self.pip_size
        )
        return pips * self.pip_value * trade.lot_size

    # ─── Visualisation ────────────────────────────────────────────────────────

    def plot(self, df: pd.DataFrame, results: BacktestResults, symbol: str = "") -> plt.Figure:
        """
        Returns a matplotlib Figure with:
          • Panel 1: Price + EMA50 + EMA200 + trade markers
          • Panel 2: RSI with overbought/oversold bands
          • Panel 3: Equity curve
        """
        gold   = COLORS["gold_primary"]
        gold_l = COLORS["gold_light"]
        bg     = COLORS["bg_dark"]
        card   = COLORS["bg_card"]
        green  = COLORS["green"]
        red    = COLORS["red"]
        gray   = COLORS["text_gray"]

        matplotlib.rcParams.update({
            "figure.facecolor":  bg,
            "axes.facecolor":    card,
            "axes.edgecolor":    COLORS["gold_dim"],
            "axes.labelcolor":   gold,
            "xtick.color":       gray,
            "ytick.color":       gray,
            "grid.color":        "#222222",
            "text.color":        COLORS["text_white"],
        })

        fig, axes = plt.subplots(
            3, 1, figsize=(16, 12),
            gridspec_kw={"height_ratios": [3, 1, 1.2]},
            sharex=False,
        )
        fig.suptitle(
            f"AST CAPITAL  ·  {symbol}  ·  Backtest Results",
            fontsize=14, color=gold_l, fontweight="bold", y=0.98,
        )

        times = df["time"] if "time" in df.columns else df.index

        # ── Panel 1: Price + EMAs + trades ────────────────────────────────
        ax1 = axes[0]
        ax1.plot(times, df["close"],    color=gray,   lw=0.8, label="Close")
        ax1.plot(times, df[C_EMA50],    color=gold,   lw=1.2, label="EMA 50")
        ax1.plot(times, df[C_EMA200],   color=gold_l, lw=1.6, label="EMA 200", linestyle="--")

        for t in results.trades:
            entry_idx = t.idx
            if entry_idx >= len(df):
                continue
            t_time = df.iloc[entry_idx]["time"] if "time" in df.columns else entry_idx
            marker = "^" if t.direction == "BUY" else "v"
            col    = green if t.direction == "BUY" else red
            ax1.scatter(t_time, t.entry_price, marker=marker,
                        color=col, s=60, zorder=5)
            if t.exit_time is not None:
                exit_col = green if t.pnl > 0 else red
                ax1.scatter(t.exit_time, t.exit_price, marker="x",
                            color=exit_col, s=50, zorder=5)

        ax1.set_ylabel("Price", color=gold)
        ax1.legend(loc="upper left", framealpha=0.3,
                   facecolor=card, edgecolor=COLORS["gold_dim"],
                   labelcolor=COLORS["text_white"], fontsize=8)
        ax1.grid(True, alpha=0.2)
        ax1.tick_params(axis='x', rotation=30, labelsize=7)

        # ── Panel 2: RSI ──────────────────────────────────────────────────
        ax2 = axes[1]
        ax2.plot(times, df[C_RSI], color=gold, lw=1.0, label="RSI 14")
        ax2.axhline(70,  color=red,   lw=0.8, linestyle="--", alpha=0.6)
        ax2.axhline(50,  color=gray,  lw=0.6, linestyle=":",  alpha=0.5)
        ax2.axhline(30,  color=green, lw=0.8, linestyle="--", alpha=0.6)
        ax2.fill_between(times, 50, df[C_RSI],
                         where=df[C_RSI] >= 50,
                         alpha=0.08, color=green)
        ax2.fill_between(times, df[C_RSI], 50,
                         where=df[C_RSI] < 50,
                         alpha=0.08, color=red)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI", color=gold)
        ax2.legend(loc="upper left", framealpha=0.3,
                   facecolor=card, edgecolor=COLORS["gold_dim"],
                   labelcolor=COLORS["text_white"], fontsize=8)
        ax2.grid(True, alpha=0.2)
        ax2.tick_params(axis='x', rotation=30, labelsize=7)

        # ── Panel 3: Equity curve ─────────────────────────────────────────
        ax3 = axes[2]
        eq   = results.equity_curve
        t_eq = list(range(len(eq)))
        ax3.plot(t_eq, eq, color=gold_l, lw=1.2, label="Equity")
        ax3.axhline(results.initial_balance, color=gray, lw=0.6, linestyle="--")
        ax3.fill_between(t_eq, results.initial_balance, eq,
                         where=[v >= results.initial_balance for v in eq],
                         alpha=0.15, color=green)
        ax3.fill_between(t_eq, results.initial_balance, eq,
                         where=[v < results.initial_balance for v in eq],
                         alpha=0.15, color=red)
        ax3.set_ylabel("Balance", color=gold)
        ax3.set_xlabel("Bar", color=gold)
        ax3.legend(loc="upper left", framealpha=0.3,
                   facecolor=card, edgecolor=COLORS["gold_dim"],
                   labelcolor=COLORS["text_white"], fontsize=8)
        ax3.grid(True, alpha=0.2)

        # Subtitle stats
        stats = (
            f"Trades: {results.total_trades}  |  "
            f"Win Rate: {results.win_rate*100:.1f}%  |  "
            f"Net P&L: {results.net_pnl:+.2f}  |  "
            f"Max DD: {results.max_drawdown*100:.2f}%  |  "
            f"PF: {results.profit_factor:.2f}"
        )
        fig.text(0.5, 0.005, stats, ha="center", va="bottom",
                 color=gold, fontsize=9)

        plt.tight_layout(rect=[0, 0.02, 1, 0.97])
        return fig

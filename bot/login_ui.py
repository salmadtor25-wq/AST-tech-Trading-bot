"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║              Login & Dashboard  (Tkinter GUI)                ║
╚══════════════════════════════════════════════════════════════╝
Dark-gold themed desktop application.

Screens:
  1. LoginScreen  — enter MT5 credentials
  2. DashScreen   — live status, backtest launcher, trade controls
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from datetime import datetime
from typing import Optional
import os
import sys

# ── Make sure bot/ is on the path when launched from root ─────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    COLORS, FONTS, load_credentials, save_credentials,
    set_live_mode, is_live_mode, LIVE_TRADING_ENABLED,
    DEFAULT_SYMBOL, SYMBOLS, TIMEFRAME,
)
from logger import log_info, log_error, log_warning

# ── Lazy imports (only needed when connected) ─────────────────────────────────
_fetcher_cls    = None
_indicator_cls  = None
_strategy_cls   = None
_backtest_cls   = None
_trader_cls     = None


def _lazy_imports():
    global _fetcher_cls, _indicator_cls, _strategy_cls, _backtest_cls, _trader_cls
    from data       import DataFetcher
    from indicators import IndicatorEngine
    from strategy   import SignalGenerator
    from backtest   import BacktestEngine
    from trader     import LiveTrader
    _fetcher_cls   = DataFetcher
    _indicator_cls = IndicatorEngine
    _strategy_cls  = SignalGenerator
    _backtest_cls  = BacktestEngine
    _trader_cls    = LiveTrader


# ─── Colour / font shorthands ─────────────────────────────────────────────────
BG      = COLORS["bg_dark"]
CARD    = COLORS["bg_card"]
INPUT   = COLORS["bg_input"]
GOLD    = COLORS["gold_primary"]
GOLD_L  = COLORS["gold_light"]
GOLD_D  = COLORS["gold_dim"]
BORDER  = COLORS["gold_border"]
WHITE   = COLORS["text_white"]
GRAY    = COLORS["text_gray"]
DIM     = COLORS["text_dim"]
GREEN   = COLORS["green"]
RED     = COLORS["red"]
ORANGE  = COLORS["orange"]


def _cfg(widget, **kw):
    """Apply config silently."""
    try:
        widget.config(**kw)
    except Exception:
        pass


# ─── Reusable styled widgets ──────────────────────────────────────────────────

class GoldButton(tk.Button):
    def __init__(self, parent, text: str, command=None, danger: bool = False, **kw):
        accent = RED if danger else GOLD
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=CARD,
            fg=accent,
            activebackground=INPUT,
            activeforeground=GOLD_L,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONTS["button"],
            padx=18,
            pady=8,
            highlightthickness=1,
            highlightbackground=accent,
            **kw,
        )
        self.bind("<Enter>", lambda e: self.config(bg=INPUT, fg=GOLD_L))
        self.bind("<Leave>", lambda e: self.config(bg=CARD, fg=accent))


class LabeledEntry(tk.Frame):
    """Dark-styled labelled input field."""

    def __init__(self, parent, label: str, show: str = "", width: int = 30, **kw):
        super().__init__(parent, bg=CARD, **kw)
        tk.Label(self, text=label, bg=CARD, fg=GOLD, font=FONTS["label"],
                 anchor="w").pack(anchor="w", pady=(6, 2))
        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            show=show,
            bg=INPUT,
            fg=WHITE,
            insertbackground=GOLD,
            relief="flat",
            bd=0,
            font=FONTS["value"],
            width=width,
            highlightthickness=1,
            highlightbackground=GOLD_D,
            highlightcolor=GOLD,
        )
        self.entry.pack(fill="x", ipady=6)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, val: str) -> None:
        self.var.set(val)


class StatusDot(tk.Label):
    """Coloured status indicator dot."""

    def __init__(self, parent, **kw):
        super().__init__(parent, text="●", font=("Courier New", 14, "bold"),
                         bg=CARD, **kw)
        self.set_offline()

    def set_online(self):  self.config(fg=GREEN)
    def set_offline(self): self.config(fg=GRAY)
    def set_live(self):    self.config(fg=RED)
    def set_demo(self):    self.config(fg=GOLD_L)


class Divider(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=GOLD_D, height=1, **kw)
        self.pack(fill="x", pady=10)


# ─── Screen 1: Login ──────────────────────────────────────────────────────────

class LoginScreen(tk.Frame):
    def __init__(self, app: "App"):
        super().__init__(app.root, bg=BG)
        self.app = app
        self._build()
        self._prefill()

    def _build(self):
        # ── Brand header ──────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG)
        header.pack(pady=(40, 10))

        tk.Label(header, text="◈  AST CAPITAL  ◈",
                 bg=BG, fg=GOLD_L, font=FONTS["brand"]).pack()
        tk.Label(header, text="Algorithmic Trading Systems",
                 bg=BG, fg=GOLD_D, font=FONTS["tagline"]).pack()
        tk.Frame(self, bg=GOLD_D, height=1).pack(fill="x", padx=60, pady=(8, 20))

        # ── Card ──────────────────────────────────────────────────────────
        card = tk.Frame(self, bg=CARD, bd=0,
                        highlightthickness=1, highlightbackground=GOLD_D)
        card.pack(padx=80, pady=0, fill="x")

        inner = tk.Frame(card, bg=CARD)
        inner.pack(padx=36, pady=30, fill="x")

        tk.Label(inner, text="MT5  ACCOUNT  CREDENTIALS",
                 bg=CARD, fg=GOLD, font=FONTS["subhead"]).pack(pady=(0, 16))

        self.f_login  = LabeledEntry(inner, "Account Login (Number)")
        self.f_login.pack(fill="x", pady=2)

        self.f_pass   = LabeledEntry(inner, "Password", show="●")
        self.f_pass.pack(fill="x", pady=2)

        self.f_server = LabeledEntry(inner, "Broker Server")
        self.f_server.pack(fill="x", pady=2)

        # Mode selector
        mode_frame = tk.Frame(inner, bg=CARD)
        mode_frame.pack(fill="x", pady=(14, 4))
        tk.Label(mode_frame, text="Trading Mode:", bg=CARD, fg=GOLD,
                 font=FONTS["label"]).pack(side="left", padx=(0, 12))

        self.mode_var = tk.StringVar(value="DEMO")
        for m, col in [("DEMO", GOLD_L), ("LIVE", RED)]:
            rb = tk.Radiobutton(
                mode_frame, text=m, variable=self.mode_var, value=m,
                bg=CARD, fg=col, selectcolor=INPUT, activebackground=CARD,
                activeforeground=col, font=FONTS["button"],
                command=self._on_mode_change,
            )
            rb.pack(side="left", padx=8)

        # Warning label
        self._warn_var = tk.StringVar(value="")
        tk.Label(inner, textvariable=self._warn_var, bg=CARD, fg=ORANGE,
                 font=FONTS["warning"], wraplength=360, justify="left").pack(pady=(2, 0))

        Divider(inner)

        btn_row = tk.Frame(inner, bg=CARD)
        btn_row.pack()
        GoldButton(btn_row, "CONNECT TO MT5", command=self._on_connect).pack(
            side="left", padx=6)
        GoldButton(btn_row, "OFFLINE / BACKTEST ONLY",
                   command=self._on_offline).pack(side="left", padx=6)

        # Status
        self._status_var = tk.StringVar(value="Enter credentials to connect.")
        tk.Label(card, textvariable=self._status_var,
                 bg=CARD, fg=GRAY, font=FONTS["mono"]).pack(pady=(0, 14))

        # Footer
        tk.Label(self, text="© 2024 AST Capital  —  For authorised users only.",
                 bg=BG, fg=DIM, font=FONTS["small"]).pack(pady=(20, 6))

    def _prefill(self):
        login, password, server = load_credentials()
        if login:
            self.f_login.set(str(login))
        if password:
            self.f_pass.set(password)
        if server:
            self.f_server.set(server)
        if is_live_mode():
            self.mode_var.set("LIVE")
            self._on_mode_change()

    def _on_mode_change(self):
        if self.mode_var.get() == "LIVE":
            self._warn_var.set(
                "⚠  LIVE mode uses REAL MONEY.  Losses are permanent.\n"
                "   Ensure LIVE_TRADING_ENABLED = True in config.py."
            )
        else:
            self._warn_var.set("")

    def _on_connect(self):
        login_str = self.f_login.get()
        password  = self.f_pass.get()
        server    = self.f_server.get()

        if not login_str or not password or not server:
            messagebox.showerror("Missing Credentials",
                                 "Please fill in all three fields.")
            return

        try:
            login = int(login_str)
        except ValueError:
            messagebox.showerror("Invalid Login", "Account login must be a number.")
            return

        live = self.mode_var.get() == "LIVE"
        if live and not LIVE_TRADING_ENABLED:
            messagebox.showerror(
                "Live Trading Disabled",
                "LIVE_TRADING_ENABLED is False in config.py.\n\n"
                "Open bot/config.py, set LIVE_TRADING_ENABLED = True, "
                "and restart the application."
            )
            return

        if live:
            confirmed = messagebox.askyesno(
                "⚠  LIVE TRADING WARNING",
                "You are about to connect in LIVE mode.\n\n"
                "Real money will be used.  Losses are not recoverable.\n\n"
                "Are you sure you want to continue?",
                icon="warning",
            )
            if not confirmed:
                return

        save_credentials(login, password, server)
        set_live_mode(live)

        self._status_var.set("Connecting…")
        self.app.root.update()

        _lazy_imports()
        fetcher = _fetcher_cls()
        ok = fetcher.connect(login, password, server)

        if not ok:
            self._status_var.set("Connection failed.  Check credentials / MT5 terminal.")
            messagebox.showerror("Connection Failed",
                                 "Could not connect to MT5.\n\n"
                                 "Make sure MetaTrader 5 is running on this machine "
                                 "and the terminal is logged in.")
            return

        self.app.launch_dashboard(fetcher, demo_mode=not live)

    def _on_offline(self):
        _lazy_imports()
        fetcher = _fetcher_cls()   # not connected — uses CSV cache / synthetic
        self.app.launch_dashboard(fetcher, demo_mode=True, offline=True)


# ─── Screen 2: Dashboard ──────────────────────────────────────────────────────

class DashScreen(tk.Frame):
    def __init__(self, app: "App", fetcher, demo_mode: bool, offline: bool = False):
        super().__init__(app.root, bg=BG)
        self.app        = app
        self.fetcher    = fetcher
        self.demo_mode  = demo_mode
        self.offline    = offline
        self._trader: Optional[object] = None
        self._trade_thread: Optional[threading.Thread] = None
        self._build()
        self._refresh_account()

    def _build(self):
        # ── Top bar ───────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=CARD, height=52,
                          highlightthickness=1, highlightbackground=GOLD_D)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="◈  AST CAPITAL", bg=CARD, fg=GOLD_L,
                 font=("Georgia", 16, "bold")).pack(side="left", padx=18)

        mode_text = "DEMO MODE" if self.demo_mode else "⚠  LIVE MODE"
        mode_col  = GOLD_L if self.demo_mode else RED
        tk.Label(topbar, text=mode_text, bg=CARD, fg=mode_col,
                 font=("Courier New", 11, "bold")).pack(side="left", padx=20)

        self._dot = StatusDot(topbar)
        self._dot.pack(side="right", padx=(0, 8))
        if self.offline:
            self._dot.set_offline()
        elif self.demo_mode:
            self._dot.set_demo()
        else:
            self._dot.set_live()

        tk.Label(topbar, text="OFFLINE" if self.offline else
                 ("DEMO" if self.demo_mode else "LIVE"),
                 bg=CARD, fg=GRAY, font=FONTS["small"]).pack(side="right", padx=2)

        GoldButton(topbar, "LOGOUT", command=self._on_logout,
                   danger=False).pack(side="right", padx=8, pady=8)

        # ── Main area ─────────────────────────────────────────────────────
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=24, pady=16)

        # Left column: account + controls
        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="y", padx=(0, 16))

        # Account card
        acc_card = self._make_card(left, "ACCOUNT")
        self._bal_var   = tk.StringVar(value="—")
        self._eq_var    = tk.StringVar(value="—")
        self._dpnl_var  = tk.StringVar(value="—")
        self._ddpct_var = tk.StringVar(value="—")
        self._trades_var= tk.StringVar(value="—")

        for label, var in [
            ("Balance",        self._bal_var),
            ("Equity",         self._eq_var),
            ("Daily P&L",      self._dpnl_var),
            ("Daily DD",       self._ddpct_var),
            ("Open Positions", self._trades_var),
        ]:
            row = tk.Frame(acc_card, bg=CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label:<18}", bg=CARD, fg=GRAY,
                     font=FONTS["mono"]).pack(side="left")
            tk.Label(row, textvariable=var, bg=CARD, fg=WHITE,
                     font=FONTS["value"]).pack(side="right")

        # Symbol / timeframe selectors
        sel_card = self._make_card(left, "SETTINGS")
        sym_row = tk.Frame(sel_card, bg=CARD)
        sym_row.pack(fill="x", pady=4)
        tk.Label(sym_row, text="Symbol:", bg=CARD, fg=GOLD,
                 font=FONTS["label"]).pack(side="left", padx=(0, 8))
        self.sym_var = tk.StringVar(value=DEFAULT_SYMBOL)
        ttk.Combobox(sym_row, textvariable=self.sym_var,
                     values=SYMBOLS, width=12,
                     state="readonly").pack(side="left")

        tf_row = tk.Frame(sel_card, bg=CARD)
        tf_row.pack(fill="x", pady=4)
        tk.Label(tf_row, text="Timeframe:", bg=CARD, fg=GOLD,
                 font=FONTS["label"]).pack(side="left", padx=(0, 8))
        self.tf_var = tk.StringVar(value=TIMEFRAME)
        ttk.Combobox(tf_row, textvariable=self.tf_var,
                     values=["M5", "M15", "H1", "H4", "D1"], width=8,
                     state="readonly").pack(side="left")

        bal_row = tk.Frame(sel_card, bg=CARD)
        bal_row.pack(fill="x", pady=4)
        tk.Label(bal_row, text="Backtest Balance $:", bg=CARD, fg=GOLD,
                 font=FONTS["label"]).pack(side="left", padx=(0, 8))
        self.bt_bal_var = tk.StringVar(value="10000")
        tk.Entry(bal_row, textvariable=self.bt_bal_var, width=10,
                 bg=INPUT, fg=WHITE, insertbackground=GOLD,
                 relief="flat", highlightthickness=1,
                 highlightbackground=GOLD_D, font=FONTS["value"]).pack(side="left")

        # Action buttons
        btn_card = self._make_card(left, "ACTIONS")
        GoldButton(btn_card, "▶  RUN BACKTEST",
                   command=self._on_backtest).pack(fill="x", pady=4)

        if not self.offline:
            GoldButton(btn_card, "▶  START TRADING",
                       command=self._on_start_trading).pack(fill="x", pady=4)
            GoldButton(btn_card, "■  STOP TRADING",
                       command=self._on_stop_trading).pack(fill="x", pady=4)
            GoldButton(btn_card, "✕  CLOSE ALL POSITIONS",
                       command=self._on_close_all, danger=True).pack(fill="x", pady=4)

        GoldButton(btn_card, "↺  REFRESH ACCOUNT",
                   command=self._refresh_account).pack(fill="x", pady=4)

        # Right column: log console
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        log_card = tk.Frame(right, bg=CARD, highlightthickness=1,
                            highlightbackground=GOLD_D)
        log_card.pack(fill="both", expand=True)
        tk.Label(log_card, text="  TRADING LOG", bg=CARD, fg=GOLD,
                 font=FONTS["subhead"], anchor="w").pack(fill="x", padx=10, pady=(10, 4))
        tk.Frame(log_card, bg=GOLD_D, height=1).pack(fill="x")

        self._log_text = tk.Text(
            log_card, bg="#0a0a0a", fg=GOLD, font=FONTS["mono"],
            relief="flat", state="disabled", wrap="word",
            insertbackground=GOLD, padx=10, pady=8,
        )
        self._log_text.pack(fill="both", expand=True)
        # Tag colours for log
        self._log_text.tag_config("gold",  foreground=GOLD_L)
        self._log_text.tag_config("green", foreground=GREEN)
        self._log_text.tag_config("red",   foreground=RED)
        self._log_text.tag_config("gray",  foreground=GRAY)
        self._log_text.tag_config("white", foreground=WHITE)

        scrollbar = tk.Scrollbar(log_card, command=self._log_text.yview,
                                 bg=CARD, troughcolor=INPUT)
        scrollbar.pack(side="right", fill="y")
        self._log_text["yscrollcommand"] = scrollbar.set

        # Status bar
        statusbar = tk.Frame(self, bg=CARD, height=28,
                             highlightthickness=1, highlightbackground=GOLD_D)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(statusbar, textvariable=self._status_var, bg=CARD, fg=GRAY,
                 font=FONTS["small"]).pack(side="left", padx=12)
        self._time_var = tk.StringVar()
        tk.Label(statusbar, textvariable=self._time_var, bg=CARD, fg=DIM,
                 font=FONTS["small"]).pack(side="right", padx=12)
        self._tick_clock()

    def _make_card(self, parent, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=GOLD_D)
        frame.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(frame, bg=CARD)
        inner.pack(padx=14, pady=(10, 12), fill="x")
        tk.Label(inner, text=title, bg=CARD, fg=GOLD,
                 font=FONTS["subhead"]).pack(anchor="w", pady=(0, 8))
        tk.Frame(inner, bg=GOLD_D, height=1).pack(fill="x", pady=(0, 8))
        return inner

    # ─── Log console helpers ──────────────────────────────────────────────

    def _log(self, msg: str, tag: str = "white"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_text.config(state="normal")
        self._log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    # ─── Account refresh ─────────────────────────────────────────────────

    def _refresh_account(self):
        if self.offline:
            self._bal_var.set("N/A (offline)")
            self._eq_var.set("N/A")
            self._dpnl_var.set("N/A")
            self._ddpct_var.set("N/A")
            self._trades_var.set("N/A")
            return

        account = self.fetcher.get_account_info()
        if not account:
            self._status_var.set("Cannot fetch account info.")
            return

        self._bal_var.set(f"{account['balance']:,.2f} {account['currency']}")
        self._eq_var.set(f"{account['equity']:,.2f} {account['currency']}")
        open_pos = self.fetcher.get_open_positions()
        self._trades_var.set(str(len(open_pos)))

        if self._trader:
            rm = self._trader._risk
            dpnl = rm.daily_pnl
            color = "green" if dpnl >= 0 else "red"
            self._dpnl_var.set(f"{dpnl:+.2f}")
            dd = rm.daily_loss_pct(account["balance"]) * 100
            self._ddpct_var.set(f"{dd:.2f}%")
        else:
            self._dpnl_var.set("—")
            self._ddpct_var.set("—")

    # ─── Backtest ────────────────────────────────────────────────────────

    def _on_backtest(self):
        symbol    = self.sym_var.get()
        timeframe = self.tf_var.get()
        try:
            init_bal = float(self.bt_bal_var.get())
        except ValueError:
            messagebox.showerror("Invalid Balance", "Enter a valid number for backtest balance.")
            return

        self._log(f"Running backtest — {symbol} {timeframe} starting balance=${init_bal:,.0f}",
                  "gold")
        self._status_var.set("Running backtest…")
        self.app.root.update()

        def _run():
            try:
                from indicators import IndicatorEngine
                from strategy   import SignalGenerator
                from backtest   import BacktestEngine
                import matplotlib
                matplotlib.use("TkAgg")
                import matplotlib.pyplot as plt

                df  = self.fetcher.get_ohlcv(symbol, timeframe, 1000)
                df  = IndicatorEngine().calculate(df)
                df  = SignalGenerator().generate_signals(df)
                eng = BacktestEngine(initial_balance=init_bal)
                res = eng.run(df)

                # Print to log panel
                for line in res.summary().split("\n"):
                    tag = "gold" if "═" in line or "╔" in line or "╚" in line else "white"
                    self.app.root.after(0, self._log, line, tag)

                # Show chart in new window
                fig = eng.plot(df, res, symbol=f"{symbol} {timeframe}")

                def _show():
                    self._status_var.set("Backtest complete — chart window opened.")
                    fig.canvas.manager.window.configure(bg=BG)
                    plt.show()

                self.app.root.after(0, _show)

            except Exception as exc:
                self.app.root.after(0, self._log, f"Backtest error: {exc}", "red")
                self.app.root.after(0, self._status_var.set, f"Error: {exc}")

        threading.Thread(target=_run, daemon=True).start()

    # ─── Trading controls ─────────────────────────────────────────────────

    def _on_start_trading(self):
        if self._trader and self._trader.is_running:
            messagebox.showinfo("Already Running", "The trading bot is already active.")
            return

        symbol    = self.sym_var.get()
        timeframe = self.tf_var.get()

        from trader import LiveTrader
        try:
            self._trader = LiveTrader(
                fetcher    = self.fetcher,
                demo_mode  = self.demo_mode,
                symbol     = symbol,
                timeframe  = timeframe,
                on_status  = self._on_trader_status,
            )
        except RuntimeError as exc:
            messagebox.showerror("Configuration Error", str(exc))
            return

        self._trade_thread = threading.Thread(target=self._trader.start, daemon=True)
        self._trade_thread.start()

        mode = "DEMO" if self.demo_mode else "LIVE"
        self._log(f"Trading started | {symbol} {timeframe} | {mode}", "green")
        self._status_var.set(f"Trading active — {symbol} {timeframe} [{mode}]")

    def _on_stop_trading(self):
        if self._trader and self._trader.is_running:
            self._trader.stop()
            self._log("Stop signal sent — finishing current cycle.", "gold")
            self._status_var.set("Stopping…")
        else:
            self._log("No active trading session.", "gray")

    def _on_close_all(self):
        if not self._trader:
            messagebox.showinfo("No Trader", "No active trading session.")
            return
        confirmed = messagebox.askyesno(
            "Close All Positions",
            f"Close ALL open positions for {self.sym_var.get()}?",
            icon="warning",
        )
        if confirmed:
            self._trader.close_all()
            self._log("Closed all positions.", "red")
            self._refresh_account()

    def _on_trader_status(self, status: dict):
        """Callback from LiveTrader (runs in trading thread — post to root)."""
        def _update():
            self._bal_var.set(f"{status['balance']:,.2f}")
            self._eq_var.set(f"{status['equity']:,.2f}")
            dpnl = status["daily_pnl"]
            self._dpnl_var.set(f"{dpnl:+.2f}")
            dd = status["daily_loss_pct"]
            self._ddpct_var.set(f"{dd:.2f}%")
            self._trades_var.set(str(len(status["open_positions"])))
            if status["is_halted"]:
                self._log("⚠ Daily loss limit triggered — trading halted.", "red")
        self.app.root.after(0, _update)

    # ─── Misc ─────────────────────────────────────────────────────────────

    def _on_logout(self):
        if self._trader and self._trader.is_running:
            self._trader.stop()
        if hasattr(self.fetcher, "disconnect"):
            self.fetcher.disconnect()
        self.app.show_login()

    def _tick_clock(self):
        self._time_var.set(datetime.utcnow().strftime("UTC  %Y-%m-%d  %H:%M:%S"))
        self.app.root.after(1000, self._tick_clock)


# ─── Application shell ────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AST Capital  ·  Trading Bot")
        self.root.geometry("1100x720")
        self.root.minsize(900, 620)
        self.root.configure(bg=BG)
        self._set_icon()
        self._apply_ttk_theme()
        self._current_screen: Optional[tk.Frame] = None
        self.show_login()

    def _set_icon(self):
        try:
            # Inline 16×16 gold diamond icon (base64 PNG)
            import base64
            ICON = (
                "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+g"
                "vaeTAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH6AEBCgwx5r0PVAAAACNJ"
                "REFUOMtj/P//PwMlgHHUAIZRAxhGDWAYNYBh1ACGQQIABbQAAfOHJuYAAAAASUVO"
                "RK5CYII="
            )
            data = base64.b64decode(ICON)
            img  = tk.PhotoImage(data=data)
            self.root.iconphoto(True, img)
        except Exception:
            pass

    def _apply_ttk_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=INPUT, background=CARD,
                        foreground=WHITE, arrowcolor=GOLD,
                        selectbackground=GOLD_D, selectforeground=WHITE)
        style.map("TCombobox",
                  fieldbackground=[("readonly", INPUT)],
                  foreground=[("readonly", WHITE)])

    def _swap(self, new_screen: tk.Frame):
        if self._current_screen:
            self._current_screen.destroy()
        self._current_screen = new_screen
        new_screen.pack(fill="both", expand=True)

    def show_login(self):
        self._swap(LoginScreen(self))

    def launch_dashboard(self, fetcher, demo_mode: bool, offline: bool = False):
        self._swap(DashScreen(self, fetcher, demo_mode, offline))

    def run(self):
        self.root.mainloop()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()

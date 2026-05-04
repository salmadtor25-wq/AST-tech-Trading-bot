"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                       Entry Point                            ║
╚══════════════════════════════════════════════════════════════╝
Usage:

  python main.py                  # Launch full GUI
  python main.py --backtest       # Headless backtest (no GUI)
  python main.py --demo           # Headless demo trading (CLI)
  python main.py --symbol GBPUSD  # Override symbol
  python main.py --tf H4          # Override timeframe
  python main.py --balance 5000   # Override backtest starting balance
"""
from __future__ import annotations

import argparse
import sys
import os

# Make sure bot/ directory is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import log_banner, log_info, log_error, log_separator
from config import DEFAULT_SYMBOL, TIMEFRAME, load_credentials


def _run_backtest(symbol: str, timeframe: str, balance: float) -> None:
    """Headless backtest — no GUI required."""
    from data       import DataFetcher
    from indicators import IndicatorEngine
    from strategy   import SignalGenerator
    from backtest   import BacktestEngine
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    log_banner()
    log_info(f"HEADLESS BACKTEST | {symbol} {timeframe} | Balance: {balance:.2f}")
    log_separator()

    fetcher = DataFetcher()

    # Optionally connect MT5 for live historical data
    login, password, server = load_credentials()
    if login and password and server:
        fetcher.connect(login, password, server)

    df  = fetcher.get_ohlcv(symbol, timeframe, 1000)
    df  = IndicatorEngine().calculate(df)
    df  = SignalGenerator().generate_signals(df)

    engine  = BacktestEngine(initial_balance=balance)
    results = engine.run(df)

    # Save chart
    from config import DATA_DIR
    fig = engine.plot(df, results, symbol=f"{symbol} {timeframe}")
    chart_path = DATA_DIR / f"backtest_{symbol}_{timeframe}.png"
    fig.savefig(chart_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    log_info(f"Chart saved to: {chart_path}")

    if fetcher.connected:
        fetcher.disconnect()


def _run_demo(symbol: str, timeframe: str) -> None:
    """Headless demo trading — runs until Ctrl+C."""
    from data   import DataFetcher
    from trader import LiveTrader

    log_banner()
    log_info(f"HEADLESS DEMO TRADING | {symbol} {timeframe}")
    log_separator()

    login, password, server = load_credentials()
    if not (login and password and server):
        log_error("No credentials found.  Run the GUI first to save them.")
        sys.exit(1)

    fetcher = DataFetcher()
    if not fetcher.connect(login, password, server):
        log_error("MT5 connection failed.")
        sys.exit(1)

    trader = LiveTrader(fetcher, demo_mode=True, symbol=symbol, timeframe=timeframe)
    try:
        trader.start()
    except KeyboardInterrupt:
        trader.stop()
    finally:
        fetcher.disconnect()


def _run_gui() -> None:
    """Launch the full Tkinter GUI."""
    try:
        from login_ui import main as gui_main
        gui_main()
    except ImportError as exc:
        log_error(f"GUI could not start: {exc}")
        log_error("Run with --backtest or --demo for headless mode.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="AST Capital Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--backtest",  action="store_true", help="Run headless backtest")
    parser.add_argument("--demo",      action="store_true", help="Run headless demo trading")
    parser.add_argument("--symbol",    default=DEFAULT_SYMBOL, help=f"Symbol (default: {DEFAULT_SYMBOL})")
    parser.add_argument("--tf",        default=TIMEFRAME,      help=f"Timeframe (default: {TIMEFRAME})")
    parser.add_argument("--balance",   type=float, default=10_000.0,
                        help="Starting balance for backtest (default: 10000)")

    args = parser.parse_args()

    if args.backtest:
        _run_backtest(args.symbol, args.tf, args.balance)
    elif args.demo:
        _run_demo(args.symbol, args.tf)
    else:
        _run_gui()


if __name__ == "__main__":
    main()

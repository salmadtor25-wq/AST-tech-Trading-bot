"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                      Logging Module                          ║
╚══════════════════════════════════════════════════════════════╝
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import LOG_FILE, TRADE_LOG_FILE, LOG_LEVEL, COLORS


# ─── ANSI colour helpers (terminal only) ──────────────────────────────────────
GOLD  = "\033[38;2;201;162;39m"
WHITE = "\033[97m"
GRAY  = "\033[90m"
GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"
BOLD  = "\033[1m"


class _GoldFormatter(logging.Formatter):
    """AST Capital-branded terminal formatter with gold/dark colours."""

    LEVEL_COLORS = {
        "DEBUG":    GRAY,
        "INFO":     GOLD,
        "WARNING":  "\033[38;2;255;140;0m",   # orange
        "ERROR":    RED,
        "CRITICAL": f"{RED}{BOLD}",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts    = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = self.LEVEL_COLORS.get(record.levelname, WHITE)
        level = f"{color}{record.levelname:<8}{RESET}"
        msg   = record.getMessage()
        return f"{GRAY}{ts}{RESET}  {level}  {WHITE}{msg}{RESET}"


class _FileFormatter(logging.Formatter):
    """Plain formatter for log files (no ANSI codes)."""

    def format(self, record: logging.LogRecord) -> str:
        ts  = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts}  {record.levelname:<8}  {record.getMessage()}"


def _build_logger(name: str, log_file: Path, level: str = LOG_LEVEL) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger   # already configured

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(_GoldFormatter())
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(_FileFormatter())
    logger.addHandler(fh)

    return logger


# ─── Public loggers ───────────────────────────────────────────────────────────
bot_logger   = _build_logger("ast.bot",   LOG_FILE)
trade_logger = _build_logger("ast.trade", TRADE_LOG_FILE)


# ─── Convenience wrappers ─────────────────────────────────────────────────────

def log_info(msg: str)     -> None: bot_logger.info(msg)
def log_warning(msg: str)  -> None: bot_logger.warning(msg)
def log_error(msg: str)    -> None: bot_logger.error(msg)
def log_debug(msg: str)    -> None: bot_logger.debug(msg)
def log_critical(msg: str) -> None: bot_logger.critical(msg)


def log_trade_open(
    symbol: str,
    direction: str,
    entry_price: float,
    sl: float,
    tp: float,
    lot_size: float,
    reason: str,
    ticket: Optional[int] = None,
) -> None:
    """Log a trade opening with full context."""
    ticket_str = f"  ticket={ticket}" if ticket else ""
    msg = (
        f"OPEN  {direction:<4} | {symbol} | "
        f"entry={entry_price:.5f}  SL={sl:.5f}  TP={tp:.5f}  "
        f"lots={lot_size:.2f}{ticket_str} | reason: {reason}"
    )
    trade_logger.info(msg)
    bot_logger.info(f"{GREEN if direction == 'BUY' else RED}▶ Trade opened:{RESET} {msg}")


def log_trade_close(
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    exit_reason: str,
    ticket: Optional[int] = None,
) -> None:
    """Log a trade closing with P&L."""
    sign      = "+" if pnl >= 0 else ""
    color_pnl = GREEN if pnl >= 0 else RED
    ticket_str = f"  ticket={ticket}" if ticket else ""
    msg = (
        f"CLOSE {direction:<4} | {symbol} | "
        f"entry={entry_price:.5f}  exit={exit_price:.5f}  "
        f"PnL={sign}{pnl:.2f}{ticket_str} | reason: {exit_reason}"
    )
    trade_logger.info(msg)
    bot_logger.info(f"{color_pnl}◀ Trade closed:{RESET} {msg}")


def log_signal(symbol: str, signal: str, reason: str) -> None:
    color = GREEN if signal == "BUY" else RED if signal == "SELL" else GRAY
    bot_logger.info(f"{color}◆ Signal [{signal}]{RESET} on {symbol}: {reason}")


def log_risk_block(reason: str) -> None:
    bot_logger.warning(f"\033[38;2;255;140;0m⚠ Risk block:{RESET} {reason}")


def log_separator(char: str = "─", width: int = 70) -> None:
    bot_logger.info(f"{GOLD}{char * width}{RESET}")


def log_banner() -> None:
    bot_logger.info(f"{GOLD}{'═' * 70}{RESET}")
    bot_logger.info(f"{GOLD}{'AST CAPITAL  —  Algorithmic Trading System':^70}{RESET}")
    bot_logger.info(f"{GOLD}{'═' * 70}{RESET}")

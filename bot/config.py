"""
╔══════════════════════════════════════════════════════════════╗
║              AST CAPITAL — ALGORITHMIC TRADING               ║
║                    Configuration Module                       ║
╚══════════════════════════════════════════════════════════════╝
"""
import json
from pathlib import Path

# ─── Directory Paths ──────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
LOGS_DIR         = BASE_DIR / "logs"
DATA_DIR         = BASE_DIR / "data"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"

LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ─── Trading Mode ─────────────────────────────────────────────────────────────
# ⚠ CRITICAL: Keep False until you have validated strategy in DEMO for 30+ days
LIVE_TRADING_ENABLED: bool = False   # ← change ONLY when ready for live money

# ─── Symbols & Timeframes ─────────────────────────────────────────────────────
DEFAULT_SYMBOL  = "EURUSD"
SYMBOLS         = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP"]

TIMEFRAME       = "H1"   # options: M5, M15, H1, H4, D1

# MT5 timeframe integer codes
TIMEFRAME_MAP = {
    "M1":  1,
    "M5":  5,
    "M15": 15,
    "M30": 30,
    "H1":  60,
    "H4":  240,
    "D1":  1440,
}

BARS_TO_FETCH = 1000   # candles to load for indicators + backtest

# ─── Strategy Parameters ──────────────────────────────────────────────────────
EMA_FAST_PERIOD  = 50
EMA_SLOW_PERIOD  = 200
RSI_PERIOD       = 14
ATR_PERIOD       = 14

# RSI entry thresholds
RSI_BUY_LOW   = 50   # RSI must be ABOVE this to buy
RSI_BUY_HIGH  = 70   # RSI must be BELOW this (not overbought)
RSI_SELL_LOW  = 30   # RSI must be ABOVE this (not oversold)
RSI_SELL_HIGH = 50   # RSI must be BELOW this to sell

# ATR multipliers for SL / TP
SL_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 2.0

# ─── Risk Management ──────────────────────────────────────────────────────────
RISK_PER_TRADE   = 0.01   # 1% of account balance per trade
MAX_OPEN_TRADES  = 3      # maximum concurrent positions
DAILY_LOSS_LIMIT = 0.05   # halt trading if daily drawdown hits 5%

MIN_LOT_SIZE = 0.01
MAX_LOT_SIZE = 10.0
LOT_STEP     = 0.01

# Minimum candles required before we can trade (warms up EMAs)
MIN_CANDLES_REQUIRED = EMA_SLOW_PERIOD + 10

# ─── Live-Trading Loop ────────────────────────────────────────────────────────
LOOP_SLEEP_SECONDS = 60   # seconds between each live-trading cycle

# ─── Default MT5 Credentials (overridden by credentials.json) ─────────────────
MT5_LOGIN    = 0
MT5_PASSWORD = ""
MT5_SERVER   = ""

# ─── AST Capital Dark / Gold UI Theme ─────────────────────────────────────────
COLORS = {
    "bg_dark":      "#080808",
    "bg_card":      "#0f0f0f",
    "bg_input":     "#181818",
    "bg_hover":     "#1f1c10",
    "gold_primary": "#C9A227",
    "gold_light":   "#FFD700",
    "gold_dim":     "#8B6914",
    "gold_border":  "#2e2510",
    "text_white":   "#F2F2F2",
    "text_gray":    "#888888",
    "text_dim":     "#555555",
    "green":        "#00C851",
    "red":          "#FF4444",
    "orange":       "#FF8C00",
}

FONTS = {
    "brand":   ("Georgia",     30, "bold"),
    "tagline": ("Georgia",     10, "italic"),
    "heading": ("Georgia",     15, "bold"),
    "subhead": ("Georgia",     12, "bold"),
    "label":   ("Courier New", 10),
    "value":   ("Courier New", 10, "bold"),
    "mono":    ("Courier New",  9),
    "small":   ("Courier New",  8),
    "button":  ("Georgia",     11, "bold"),
    "warning": ("Courier New",  9, "bold"),
}

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL       = "INFO"
LOG_FILE        = LOGS_DIR / "bot.log"
TRADE_LOG_FILE  = LOGS_DIR / "trades.log"


# ─── Credential Helpers ───────────────────────────────────────────────────────

def load_credentials() -> tuple[int, str, str]:
    """Return (login, password, server) from credentials.json, or defaults."""
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                creds = json.load(f)
            return int(creds.get("login", 0)), creds.get("password", ""), creds.get("server", "")
        except (json.JSONDecodeError, ValueError):
            pass
    return MT5_LOGIN, MT5_PASSWORD, MT5_SERVER


def save_credentials(login: int, password: str, server: str) -> None:
    """Persist MT5 credentials to credentials.json (chmod 600 on Unix)."""
    CREDENTIALS_FILE.write_text(
        json.dumps({"login": int(login), "password": password, "server": server}, indent=2)
    )
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except Exception:
        pass


def is_live_mode() -> bool:
    """True only if both the config flag and the saved 'live_mode' flag are True."""
    if not LIVE_TRADING_ENABLED:
        return False
    if CREDENTIALS_FILE.exists():
        try:
            data = json.loads(CREDENTIALS_FILE.read_text())
            return bool(data.get("live_mode", False))
        except Exception:
            pass
    return False


def set_live_mode(enabled: bool) -> None:
    """Toggle live-mode flag inside credentials.json."""
    login, password, server = load_credentials()
    data = {"login": int(login), "password": password, "server": server, "live_mode": enabled}
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except Exception:
        pass

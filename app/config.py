"""
AST Capital Trading Platform — Master Configuration
"""
import json
from pathlib import Path

BASE_DIR         = Path(__file__).parent.parent
LOGS_DIR         = BASE_DIR / "logs"
DATA_DIR         = BASE_DIR / "data"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"

for _d in [LOGS_DIR, DATA_DIR]:
    _d.mkdir(exist_ok=True)

# ── Server ────────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── Instruments ───────────────────────────────────────────────────────────────
DEFAULT_SYMBOL    = "EURUSD"
DEFAULT_TIMEFRAME = "H1"
SYMBOLS    = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURGBP","XAUUSD","GBPJPY"]
TIMEFRAMES = ["M5","M15","H1","H4","D1"]
BARS_TO_FETCH = 500

# ── Indicator periods ─────────────────────────────────────────────────────────
EMA_FAST        = 50
EMA_SLOW        = 200
RSI_PERIOD      = 14
ATR_PERIOD      = 14
ATR_MA_PERIOD   = 20
EMA_SLOPE_BARS  = 20     # bars to measure EMA slope over
CANDLE_LOOKBACK = 10     # bars for recent-high / recent-low

# ── RSI thresholds ────────────────────────────────────────────────────────────
RSI_BUY_MIN      = 50
RSI_BUY_MAX      = 70
RSI_SELL_MIN     = 30
RSI_SELL_MAX     = 50
RSI_OVERBOUGHT   = 80
RSI_OVERSOLD     = 20
RSI_DEAD_LOW     = 45
RSI_DEAD_HIGH    = 55

# ── Volatility / trend filter thresholds ─────────────────────────────────────
ATR_VOL_RATIO        = 0.70   # ATR must be ≥ 70% of its MA to count as "active"
EMA_SLOPE_THRESHOLD  = 0.0008 # EMA200 must move ≥ 0.08% over SLOPE_BARS to not be "flat"

# ── Risk management ───────────────────────────────────────────────────────────
RISK_PER_TRADE   = 0.01   # 1 %
MAX_OPEN_TRADES  = 3
DAILY_LOSS_LIMIT = 0.05   # 5 %
SL_ATR_MULT      = 1.5
TP_ATR_MULT      = 2.0
MIN_LOT          = 0.01
MAX_LOT          = 10.0
LOT_STEP         = 0.01

# ── Live-trading safety gate ──────────────────────────────────────────────────
# Set True ONLY after thorough demo validation (30+ days, 30+ trades)
LIVE_TRADING_ENABLED: bool = False

# ── Bot loop ──────────────────────────────────────────────────────────────────
BOT_LOOP_SECONDS     = 60    # interval between strategy evaluations
WS_TICK_SECONDS      = 1     # WebSocket tick broadcast interval
WS_ACCOUNT_SECONDS   = 5
WS_SIGNAL_SECONDS    = 30
WS_MARKET_SECONDS    = 60

# ── UI colour palette (exported so server can embed in /api/config) ───────────
PALETTE = {
    "bg":           "#080604",
    "bg2":          "#0f0c08",
    "bg3":          "#161109",
    "card":         "#1c1510",
    "card2":        "#221a12",
    "border":       "#2e2318",
    "brown":        "#8B5A2B",
    "brown2":       "#A06830",
    "brown3":       "#C08040",
    "brown4":       "#D4A060",
    "text":         "#EDE0CA",
    "text2":        "#BEA882",
    "text3":        "#7A6040",
    "green":        "#52A868",
    "red":          "#A85252",
    "orange":       "#C08040",
}

# ── Credential helpers ────────────────────────────────────────────────────────

def load_credentials() -> dict:
    if CREDENTIALS_FILE.exists():
        try:
            return json.loads(CREDENTIALS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_credentials(login: int, password: str, server: str, live_mode: bool = False) -> None:
    data = {"login": int(login), "password": password, "server": server, "live_mode": live_mode}
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except Exception:
        pass

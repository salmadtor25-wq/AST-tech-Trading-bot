"""
AST Capital Trading Platform — FastAPI Server
REST API + WebSocket real-time feed + static frontend serving.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import indicators, strategy
from app.config import (
    SYMBOLS, TIMEFRAMES, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME,
    BARS_TO_FETCH, LIVE_TRADING_ENABLED, WS_TICK_SECONDS,
    WS_ACCOUNT_SECONDS, WS_SIGNAL_SECONDS, WS_MARKET_SECONDS,
    PALETTE, save_credentials,
)
from app.market import get_market_status
from app.mt5_client import MT5Client
from app.risk import RiskManager
from app.trader import AutoTrader

log = logging.getLogger("ast.server")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR   = FRONTEND_DIR / "static"

# ── Application state (singleton) ─────────────────────────────────────────────

class _State:
    client:     Optional[MT5Client]  = None
    trader:     Optional[AutoTrader] = None
    demo_mode:  bool  = True
    symbol:     str   = DEFAULT_SYMBOL
    timeframe:  str   = DEFAULT_TIMEFRAME

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    @property
    def bot_running(self) -> bool:
        return self.trader is not None and self.trader.running

state = _State()

# ── WebSocket manager ─────────────────────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._conns: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._conns.add(ws)

    def disconnect(self, ws: WebSocket):
        self._conns.discard(ws)

    async def broadcast(self, data: dict):
        dead = set()
        for ws in self._conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self._conns -= dead

    @property
    def count(self) -> int:
        return len(self._conns)

ws_mgr = WSManager()

# ── Background broadcaster ────────────────────────────────────────────────────

async def _broadcaster():
    tick_n = 0
    while True:
        try:
            tick_n += 1

            if state.connected:
                # Price tick every second
                tick = state.client.get_tick(state.symbol)
                if tick:
                    await ws_mgr.broadcast({"type": "tick", "data": tick,
                                            "symbol": state.symbol})

                # Account every 5 s
                if tick_n % WS_ACCOUNT_SECONDS == 0:
                    acc = state.client.account_info()
                    if acc:
                        await ws_mgr.broadcast({"type": "account", "data": acc})

                # Positions every 5 s
                if tick_n % WS_ACCOUNT_SECONDS == 0:
                    pos = state.client.get_positions()
                    await ws_mgr.broadcast({"type": "positions", "data": pos})

                # Signal every 30 s
                if tick_n % WS_SIGNAL_SECONDS == 0:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, state.client.get_ohlcv, state.symbol, state.timeframe, 500)
                    df = indicators.calculate(df)
                    sig = strategy.evaluate(df)
                    await ws_mgr.broadcast({"type": "signal", "data": sig,
                                            "symbol": state.symbol, "timeframe": state.timeframe})

            # Market status every 60 s
            if tick_n % WS_MARKET_SECONDS == 0:
                mkt = get_market_status(state.symbol)
                await ws_mgr.broadcast({"type": "market", "data": mkt})

            # Bot status every 5 s
            if tick_n % WS_ACCOUNT_SECONDS == 0:
                bot_data = {
                    "running":    state.bot_running,
                    "symbol":     state.symbol,
                    "timeframe":  state.timeframe,
                    "demo_mode":  state.demo_mode,
                    "log":        state.trader.log_entries[-20:] if state.trader else [],
                    "last_signal": state.trader.last_signal if state.trader else {},
                    "risk":       state.trader.risk_status  if state.trader else {},
                }
                await ws_mgr.broadcast({"type": "bot", "data": bot_data})

        except Exception as exc:
            log.warning("Broadcaster error: %s", exc)

        await asyncio.sleep(WS_TICK_SECONDS)

# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_broadcaster())
    yield
    task.cancel()

app = FastAPI(title="AST Capital Trading Platform", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Frontend serving ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse({})

# ── Auth / Connection ─────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    login:     int
    password:  str
    server:    str
    live_mode: bool = False

@app.post("/api/connect")
async def connect(req: ConnectRequest):
    if req.live_mode and not LIVE_TRADING_ENABLED:
        raise HTTPException(400,
            "LIVE trading is disabled. Set LIVE_TRADING_ENABLED=True in app/config.py.")

    if req.live_mode:
        # Extra safety confirmation — frontend must set live_mode=true explicitly
        pass

    client = MT5Client()
    ok, msg = await asyncio.get_event_loop().run_in_executor(
        None, client.connect, req.login, req.password, req.server
    )
    if not ok:
        raise HTTPException(401, msg)

    # Tear down any existing session
    if state.client:
        await _stop_bot()
        state.client.disconnect()

    state.client    = client
    state.demo_mode = not req.live_mode
    save_credentials(req.login, req.password, req.server, req.live_mode)

    acc = client.account_info()
    await ws_mgr.broadcast({"type": "connected", "data": acc})
    return {"ok": True, "message": msg, "account": acc}

@app.post("/api/disconnect")
async def disconnect():
    await _stop_bot()
    if state.client:
        state.client.disconnect()
        state.client = None
    return {"ok": True}

@app.get("/api/status")
async def status():
    acc = state.client.account_info() if state.connected else None
    return {
        "connected":  state.connected,
        "demo_mode":  state.demo_mode,
        "bot_running":state.bot_running,
        "symbol":     state.symbol,
        "timeframe":  state.timeframe,
        "account":    acc,
        "market":     get_market_status(state.symbol),
        "ws_clients": ws_mgr.count,
    }

# ── Account ───────────────────────────────────────────────────────────────────

@app.get("/api/account")
async def account():
    _require_connection()
    return state.client.account_info()

# ── Market data / charts ──────────────────────────────────────────────────────

@app.get("/api/ohlcv")
async def ohlcv(symbol: str = DEFAULT_SYMBOL, timeframe: str = DEFAULT_TIMEFRAME,
                bars: int = 300):
    _require_connection()
    df = await asyncio.get_event_loop().run_in_executor(
        None, state.client.get_ohlcv, symbol, timeframe, min(bars, 1000)
    )
    df = indicators.calculate(df)
    return indicators.to_chart_payload(df)

@app.get("/api/signal")
async def signal_api(symbol: str = DEFAULT_SYMBOL, timeframe: str = DEFAULT_TIMEFRAME):
    _require_connection()
    df = await asyncio.get_event_loop().run_in_executor(
        None, state.client.get_ohlcv, symbol, timeframe, 500
    )
    df = indicators.calculate(df)
    sig = strategy.evaluate(df)
    # Update active symbol/tf to match what user is viewing
    state.symbol    = symbol
    state.timeframe = timeframe
    return sig

@app.get("/api/market")
async def market(symbol: str = DEFAULT_SYMBOL):
    return get_market_status(symbol)

# ── Positions ─────────────────────────────────────────────────────────────────

@app.get("/api/positions")
async def positions(symbol: Optional[str] = None):
    _require_connection()
    return state.client.get_positions(symbol)

@app.post("/api/positions/{ticket}/close")
async def close_position(ticket: int):
    _require_connection()
    ok, msg = state.client.close_position(ticket)
    if not ok:
        raise HTTPException(400, msg)
    if state.trader:
        acc = state.client.account_info()
        if acc:
            state.trader._rm.daily_reset(acc["balance"])
    return {"ok": True, "message": msg}

@app.post("/api/positions/close-all")
async def close_all(symbol: Optional[str] = None):
    _require_connection()
    results = state.client.close_all(symbol)
    return {"ok": True, "results": results}

# ── Trade history ─────────────────────────────────────────────────────────────

@app.get("/api/history")
async def history(days: int = 30):
    _require_connection()
    return state.client.get_history(days)

# ── Bot control ───────────────────────────────────────────────────────────────

class BotStartRequest(BaseModel):
    symbol:    str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME

@app.post("/api/bot/start")
async def bot_start(req: BotStartRequest):
    _require_connection()
    if state.bot_running:
        return {"ok": False, "message": "Bot already running"}

    state.symbol    = req.symbol
    state.timeframe = req.timeframe

    def _on_event(entry: dict):
        asyncio.run_coroutine_threadsafe(
            ws_mgr.broadcast({"type": "bot_log", "data": entry}),
            asyncio.get_event_loop(),
        )

    state.trader = AutoTrader(
        client    = state.client,
        symbol    = req.symbol,
        timeframe = req.timeframe,
        demo_mode = state.demo_mode,
        on_event  = _on_event,
    )
    await state.trader.start()
    return {"ok": True, "message": f"Bot started — {req.symbol} {req.timeframe}"}

@app.post("/api/bot/stop")
async def bot_stop():
    await _stop_bot()
    return {"ok": True, "message": "Bot stopped"}

@app.get("/api/bot/status")
async def bot_status():
    if not state.trader:
        return {"running": False, "log": [], "last_signal": {}, "risk": {}}
    return {
        "running":      state.trader.running,
        "symbol":       state.symbol,
        "timeframe":    state.timeframe,
        "demo_mode":    state.demo_mode,
        "last_eval":    state.trader.last_eval_time,
        "log":          state.trader.log_entries[-50:],
        "last_signal":  state.trader.last_signal,
        "risk":         state.trader.risk_status,
    }

@app.get("/api/bot/log")
async def bot_log():
    if not state.trader:
        return []
    return state.trader.log_entries

# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def config_api():
    return {"symbols": SYMBOLS, "timeframes": TIMEFRAMES, "palette": PALETTE,
            "live_enabled": LIVE_TRADING_ENABLED}

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_mgr.connect(ws)
    # Send initial state immediately
    if state.connected:
        acc = state.client.account_info()
        if acc:
            await ws.send_json({"type": "account", "data": acc})
        mkt = get_market_status(state.symbol)
        await ws.send_json({"type": "market", "data": mkt})
    try:
        while True:
            await ws.receive_text()   # keep-alive ping
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_connection():
    if not state.connected:
        raise HTTPException(401, "Not connected to MT5")

async def _stop_bot():
    if state.trader and state.trader.running:
        await state.trader.stop()
        state.trader = None

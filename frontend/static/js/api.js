/* ═══════════════════════════════════════════════════════
   AST Capital — REST API Client
═══════════════════════════════════════════════════════ */

const API = (() => {
  const BASE = "";   // same origin

  async function _req(method, path, body) {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(BASE + path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  }

  return {
    // Auth
    connect(login, password, server, live_mode) {
      return _req("POST", "/api/connect", { login: Number(login), password, server, live_mode });
    },
    disconnect() { return _req("POST", "/api/disconnect"); },
    status()     { return _req("GET",  "/api/status"); },

    // Account
    account()    { return _req("GET",  "/api/account"); },

    // Market data
    ohlcv(symbol, timeframe, bars = 300) {
      return _req("GET", `/api/ohlcv?symbol=${symbol}&timeframe=${timeframe}&bars=${bars}`);
    },
    signal(symbol, timeframe) {
      return _req("GET", `/api/signal?symbol=${symbol}&timeframe=${timeframe}`);
    },
    market(symbol = "EURUSD") {
      return _req("GET", `/api/market?symbol=${symbol}`);
    },

    // Positions
    positions(symbol) {
      const q = symbol ? `?symbol=${symbol}` : "";
      return _req("GET", `/api/positions${q}`);
    },
    closePosition(ticket)  { return _req("POST", `/api/positions/${ticket}/close`); },
    closeAll(symbol)       {
      const q = symbol ? `?symbol=${symbol}` : "";
      return _req("POST", `/api/positions/close-all${q}`);
    },

    // History
    history(days = 30) { return _req("GET", `/api/history?days=${days}`); },

    // Bot
    botStart(symbol, timeframe) { return _req("POST", "/api/bot/start", { symbol, timeframe }); },
    botStop()                   { return _req("POST", "/api/bot/stop"); },
    botStatus()                 { return _req("GET",  "/api/bot/status"); },
    botLog()                    { return _req("GET",  "/api/bot/log"); },

    // Config
    config() { return _req("GET", "/api/config"); },
  };
})();

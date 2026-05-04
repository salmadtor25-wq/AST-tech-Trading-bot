/* ═══════════════════════════════════════════════════════
   AST Capital — Main Application Logic
   SPA router · page controllers · real-time data binding
═══════════════════════════════════════════════════════ */

const App = (() => {

  // ── State ──────────────────────────────────────────────────
  let _state = {
    connected:    false,
    demoMode:     true,
    symbol:       "EURUSD",
    timeframe:    "H1",
    account:      null,
    positions:    [],
    botRunning:   false,
    marketOpen:   false,
    lastSignal:   null,
    currentPage:  "dashboard",
    chartLoaded:  false,
    miniLoaded:   false,
  };

  // ── Helpers ────────────────────────────────────────────────
  const $ = id => document.getElementById(id);

  function fmt(n, decimals = 2) {
    if (n == null || isNaN(n)) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }
  function fmtPnl(n) {
    if (n == null) return "—";
    const s = (n >= 0 ? "+" : "") + fmt(n);
    return s;
  }
  function clsPnl(el, n) {
    el.classList.remove("pos-pnl-green", "pos-pnl-red");
    if (n > 0) el.classList.add("pos-pnl-green");
    else if (n < 0) el.classList.add("pos-pnl-red");
  }
  function setText(id, txt) { const el = $(id); if (el) el.textContent = txt; }
  function showEl(id)   { const el = $(id); if (el) el.classList.remove("hidden"); }
  function hideEl(id)   { const el = $(id); if (el) el.classList.add("hidden"); }

  // ── UTC Clock ──────────────────────────────────────────────
  function _tickClock() {
    const el = $("sf-clock");
    if (el) el.textContent = new Date().toUTCString().slice(17, 25) + " UTC";
    setTimeout(_tickClock, 1000);
  }

  // ══════════════════════════════════════════════════════════
  //  LOGIN
  // ══════════════════════════════════════════════════════════

  function _initLogin() {
    const form   = $("login-form");
    const radios = form.querySelectorAll("input[type=radio]");

    radios.forEach(r => r.addEventListener("change", () => {
      const isLive = r.value === "live" && r.checked;
      $("live-warning").classList.toggle("hidden", !isLive);
    }));

    form.addEventListener("submit", async e => {
      e.preventDefault();
      const login    = $("f-login").value.trim();
      const password = $("f-pass").value;
      const server   = $("f-server").value.trim();
      const liveMode = form.querySelector("input[name=mode]:checked").value === "live";

      if (!login || !password || !server) {
        _showLoginError("Please fill in all fields.");
        return;
      }

      $("connect-text").textContent = "Connecting…";
      $("connect-spinner").classList.remove("hidden");
      $("btn-connect").disabled = true;
      hideEl("login-error");

      try {
        const res = await API.connect(Number(login), password, server, liveMode);
        _state.connected = true;
        _state.demoMode  = !liveMode;
        _state.account   = res.account;
        _launchApp(res.account, liveMode);
      } catch (err) {
        _showLoginError(err.message || "Connection failed. Check credentials and MT5 terminal.");
      } finally {
        $("connect-text").textContent = "CONNECT TO MT5";
        $("connect-spinner").classList.add("hidden");
        $("btn-connect").disabled = false;
      }
    });

    // Pre-fill from localStorage if available
    const saved = localStorage.getItem("ast_creds");
    if (saved) {
      try {
        const c = JSON.parse(saved);
        if (c.login)  $("f-login").value  = c.login;
        if (c.server) $("f-server").value = c.server;
      } catch (_) {}
    }
  }

  function _showLoginError(msg) {
    const el = $("login-error");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  // ══════════════════════════════════════════════════════════
  //  APP LAUNCH
  // ══════════════════════════════════════════════════════════

  async function _launchApp(account, liveMode) {
    // Save non-sensitive info
    if (account) {
      localStorage.setItem("ast_creds", JSON.stringify({ login: account.login, server: account.server }));
    }

    // Swap screens
    $("login-screen").style.display = "none";
    const appEl = $("app");
    appEl.classList.remove("hidden");
    appEl.style.display = "flex";

    // Mode indicator
    const modeEl = $("mode-indicator");
    if (liveMode) {
      modeEl.textContent = "LIVE";
      modeEl.classList.add("live");
      $("live-mode-warn").style.display = "block";
    } else {
      modeEl.textContent = "DEMO";
    }

    // Populate account info
    if (account) _updateAccountDisplay(account);

    // Populate selectors
    await _populateSelectors();

    // Start clock
    _tickClock();

    // Connect WebSocket
    WS.connect();

    // Initial data loads
    _loadMarketStatus();
    setTimeout(() => {
      _loadMiniChart();
      _loadSignal("dashboard");
    }, 600);

    // Navigation
    _initNavigation();
    _initTopbarControls();
    _initBotControls();
    _initPositionsPage();
    _initHistoryPage();
    _initSettingsPage();

    // Navigate to dashboard
    navTo("dashboard");
  }

  // ══════════════════════════════════════════════════════════
  //  SELECTORS
  // ══════════════════════════════════════════════════════════

  async function _populateSelectors() {
    let symbols    = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURGBP","XAUUSD","GBPJPY"];
    let timeframes = ["M5","M15","H1","H4","D1"];

    try {
      const cfg = await API.config();
      if (cfg.symbols)    symbols    = cfg.symbols;
      if (cfg.timeframes) timeframes = cfg.timeframes;
    } catch (_) {}

    const ids = ["header-symbol","chart-symbol","sig-symbol","bot-symbol"];
    ids.forEach(id => {
      const el = $(id);
      if (!el) return;
      el.innerHTML = "";
      symbols.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s; opt.textContent = s;
        if (s === _state.symbol) opt.selected = true;
        el.appendChild(opt);
      });
    });

    const tfIds = ["header-tf","chart-tf","bot-tf"];
    tfIds.forEach(id => {
      const el = $(id);
      if (!el) return;
      el.innerHTML = "";
      timeframes.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t; opt.textContent = t;
        if (t === _state.timeframe) opt.selected = true;
        el.appendChild(opt);
      });
    });

    // Sync sig-tf separately (only timeframes)
    const sigTf = $("sig-tf");
    if (sigTf) {
      sigTf.innerHTML = "";
      timeframes.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t; opt.textContent = t;
        if (t === _state.timeframe) opt.selected = true;
        sigTf.appendChild(opt);
      });
    }
  }

  // ══════════════════════════════════════════════════════════
  //  NAVIGATION
  // ══════════════════════════════════════════════════════════

  function _initNavigation() {
    document.querySelectorAll(".nav-item[data-page]").forEach(link => {
      link.addEventListener("click", e => {
        e.preventDefault();
        navTo(link.dataset.page);
      });
    });

    // Sidebar toggle
    $("sidebar-toggle").addEventListener("click", () => {
      $("sidebar").classList.toggle("collapsed");
    });
  }

  function navTo(page) {
    // Update nav links
    document.querySelectorAll(".nav-item[data-page]").forEach(l => {
      l.classList.toggle("active", l.dataset.page === page);
    });
    // Show/hide pages
    document.querySelectorAll(".page").forEach(p => {
      p.classList.toggle("active", p.id === `page-${page}`);
      p.style.display = p.id === `page-${page}` ? "block" : "none";
    });
    _state.currentPage = page;

    // Page-specific init
    if (page === "charts" && !_state.chartLoaded) {
      setTimeout(_initFullCharts, 100);
    }
    if (page === "charts") {
      setTimeout(_refreshChartPage, 200);
    }
    if (page === "positions") _loadPositions();
    if (page === "bot")       _loadBotStatus();
    if (page === "signals")   _loadSignal("signals");
    if (page === "history")   {} // user clicks Load manually
  }

  // ══════════════════════════════════════════════════════════
  //  TOPBAR CONTROLS
  // ══════════════════════════════════════════════════════════

  function _initTopbarControls() {
    $("header-symbol").addEventListener("change", e => {
      _state.symbol = e.target.value;
      setText("live-symbol-label", _state.symbol);
      _loadMarketStatus();
      if (_state.currentPage === "charts") _refreshChartPage();
    });

    $("header-tf").addEventListener("change", e => {
      _state.timeframe = e.target.value;
      if (_state.currentPage === "charts") _refreshChartPage();
    });

    $("btn-logout").addEventListener("click", async () => {
      if (confirm("Disconnect and return to login?")) {
        await API.disconnect().catch(() => {});
        location.reload();
      }
    });
  }

  // ══════════════════════════════════════════════════════════
  //  ACCOUNT DISPLAY
  // ══════════════════════════════════════════════════════════

  function _updateAccountDisplay(acc) {
    if (!acc) return;
    _state.account = acc;

    // Header
    setText("hdr-balance", fmt(acc.balance) + " " + (acc.currency || ""));
    setText("hdr-equity",  fmt(acc.equity));

    // Dashboard stats
    setText("d-balance",     fmt(acc.balance));
    setText("d-currency",    acc.currency || "");
    setText("d-equity",      fmt(acc.equity));
    setText("d-margin-level",`Margin Level: ${fmt(acc.margin_level)}%`);
    setText("d-profit",      fmtPnl(acc.profit));
    clsPnl($("d-profit"), acc.profit);
    setText("d-free-margin", fmt(acc.free_margin));
    setText("d-margin",      `Margin: ${fmt(acc.margin)}`);

    // Settings
    setText("si-login",    acc.login);
    setText("si-name",     acc.name    || "—");
    setText("si-server",   acc.server  || "—");
    setText("si-currency", acc.currency|| "—");
    setText("si-leverage", acc.leverage ? "1:" + acc.leverage : "—");
    setText("si-mode",     _state.demoMode ? "DEMO" : "LIVE");

    // Sidebar
    setText("sb-server",   acc.server  || "—");
    setText("sb-login",    acc.login   || "—");
    setText("sb-leverage", acc.leverage ? "1:" + acc.leverage : "—");
  }

  // ══════════════════════════════════════════════════════════
  //  MARKET STATUS
  // ══════════════════════════════════════════════════════════

  function _loadMarketStatus() {
    API.market(_state.symbol).then(mkt => _applyMarketStatus(mkt)).catch(() => {});
  }

  function _applyMarketStatus(mkt) {
    _state.marketOpen = mkt.open;
    const dot     = $("market-dot");
    const label   = $("market-label");
    if (dot)   { dot.className = "status-dot " + (mkt.open ? "open" : "closed"); }
    if (label) label.textContent = mkt.open ? mkt.session : "Closed";

    setText("d-mkt-status",  mkt.open ? "● OPEN" : "● CLOSED");
    setText("d-mkt-session", mkt.session || "—");
    setText("d-mkt-time",    mkt.utc_time || "—");

    const sbMkt = $("sb-market");
    if (sbMkt) sbMkt.textContent = `Market: ${mkt.open ? mkt.session : "Closed"}`;
  }

  // ══════════════════════════════════════════════════════════
  //  MINI CHART (Dashboard)
  // ══════════════════════════════════════════════════════════

  function _loadMiniChart() {
    if (!_state.miniLoaded) {
      Charts.initMini("mini-chart");
      _state.miniLoaded = true;
    }
    setText("mini-chart-label", `${_state.symbol} · ${_state.timeframe}`);
    API.ohlcv(_state.symbol, _state.timeframe, 100)
       .then(p => Charts.loadMini(p))
       .catch(() => {});
  }

  // ══════════════════════════════════════════════════════════
  //  FULL CHARTS PAGE
  // ══════════════════════════════════════════════════════════

  function _initFullCharts() {
    Charts.initMain("main-chart");
    Charts.initRsi("rsi-chart");
    Charts.initAtr("atr-chart");
    _state.chartLoaded = true;

    // Controls
    $("chart-symbol").addEventListener("change", e => {
      _state.symbol = e.target.value;
      $("header-symbol").value = e.target.value;
      _refreshChartPage();
    });
    $("chart-tf").addEventListener("change", e => {
      _state.timeframe = e.target.value;
      $("header-tf").value = e.target.value;
      _refreshChartPage();
    });
    $("chart-refresh").addEventListener("click", _refreshChartPage);
    $("chart-ema50").addEventListener("change",   _refreshChartPage);
    $("chart-ema200").addEventListener("change",  _refreshChartPage);
    $("chart-signals").addEventListener("change", _refreshChartPage);

    _refreshChartPage();
  }

  function _refreshChartPage() {
    const sym = $("chart-symbol")?.value || _state.symbol;
    const tf  = $("chart-tf")?.value    || _state.timeframe;
    setText("chart-main-label", `${sym} · ${tf} — Candlestick + EMA`);

    Promise.all([
      API.ohlcv(sym, tf, 400),
      API.signal(sym, tf),
    ]).then(([payload, sig]) => {
      const ema50  = $("chart-ema50")?.checked  ?? true;
      const ema200 = $("chart-ema200")?.checked ?? true;
      const sigs   = $("chart-signals")?.checked ?? true;
      Charts.loadData(payload, ema50, ema200, sigs);
      _applySignalToPanel(sig);
    }).catch(err => console.warn("Chart refresh error:", err));
  }

  function _applySignalToPanel(sig) {
    if (!sig) return;
    const pill   = $("chart-signal-pill");
    const reason = $("chart-signal-reason");
    if (pill)   { pill.className = `signal-pill ${sig.signal.toLowerCase()}`; pill.textContent = sig.signal; }
    if (reason) reason.textContent = sig.reason || "—";

    // Conditions panel
    const panel = $("conditions-panel");
    if (!panel) return;
    const c = sig.conditions || {};
    const v = sig.values     || {};

    const items = [
      { label: "Trend Filter",     pass: c.trend_buy || c.trend_sell, desc: c.trend_buy ? "↑ EMA50>EMA200, Price>EMA200" : c.trend_sell ? "↓ EMA50<EMA200, Price<EMA200" : "No trend alignment", val: `EMA50: ${v.ema50 ?? "—"}` },
      { label: "RSI Momentum",     pass: c.rsi_buy || c.rsi_sell,     desc: c.rsi_buy ? "RSI in [50–70]" : c.rsi_sell ? "RSI in [30–50]" : "RSI outside range", val: `RSI: ${v.rsi ?? "—"}` },
      { label: "RSI Not Extreme",  pass: c.rsi_safe,                  desc: c.rsi_safe ? "RSI safe (<80/>20)" : "RSI extreme — blocked", val: "" },
      { label: "Candle Confirm",   pass: c.candle_buy || c.candle_sell, desc: c.candle_buy ? "Bullish breaks high" : c.candle_sell ? "Bearish breaks low" : "Candle not confirmed", val: `High: ${v.recent_high ?? "—"}` },
      { label: "Volatility",       pass: c.volatility,                desc: c.volatility ? "ATR active" : "Low volatility — blocked", val: `ATR: ${v.atr ?? "—"}` },
      { label: "Market Trending",  pass: c.trending,                  desc: c.trending ? "EMA slope OK" : "EMA flat — sideways block", val: `Slope: ${v.ema200_slope_pct ?? "—"}%` },
      { label: "RSI Active Zone",  pass: c.rsi_active,                desc: c.rsi_active ? "RSI outside 45–55 dead zone" : "RSI in dead zone — blocked", val: "" },
    ];

    panel.innerHTML = items.map(it => `
      <div class="cp-item">
        <span class="cp-dot ${it.pass ? "pass" : "fail"}"></span>
        <span class="cp-label">${it.label}</span>
        <span class="cp-value">${it.val}</span>
      </div>
    `).join("");

    // Raw values
    const cv = $("cond-values");
    if (cv) cv.innerHTML = `
      <div><span>Close</span><span>${v.close ?? "—"}</span></div>
      <div><span>EMA 200</span><span>${v.ema200 ?? "—"}</span></div>
      <div><span>ATR-MA</span><span>${v.atr_ma ?? "—"}</span></div>
      <div><span>Recent High</span><span>${v.recent_high ?? "—"}</span></div>
      <div><span>Recent Low</span><span>${v.recent_low ?? "—"}</span></div>
    `;
  }

  // ══════════════════════════════════════════════════════════
  //  SIGNAL PAGE
  // ══════════════════════════════════════════════════════════

  function _loadSignal(context) {
    const sym = context === "signals"
      ? ($("sig-symbol")?.value || _state.symbol)
      : _state.symbol;
    const tf  = context === "signals"
      ? ($("sig-tf")?.value || _state.timeframe)
      : _state.timeframe;

    API.signal(sym, tf).then(sig => {
      _state.lastSignal = sig;
      _applySignalDashboard(sig);
      if (context === "signals") _applySignalPage(sig, sym, tf);
    }).catch(() => {});
  }

  function _applySignalDashboard(sig) {
    const pill   = $("d-signal-pill");
    const reason = $("d-signal-reason");
    if (!pill) return;
    pill.className   = `signal-pill ${sig.signal.toLowerCase()}`;
    pill.textContent = sig.signal;
    if (reason) reason.textContent = sig.reason || "—";

    // Header daily P&L (from risk if available)
    setText("hdr-dpnl", "—");
  }

  function _applySignalPage(sig, sym, tf) {
    const pill   = $("sig-pill");
    const reason = $("sig-reason");
    const label  = $("sig-label");
    if (pill)   { pill.className = `bsd-pill ${sig.signal.toLowerCase()}`; pill.textContent = sig.signal; }
    if (reason) reason.textContent = sig.reason || "—";
    if (label)  label.textContent = `${sym} · ${tf}`;

    // Signal badge
    const badge = $("signal-badge");
    if (badge) badge.textContent = sig.signal !== "NONE" ? "!" : "";

    // Conditions grid
    const grid = $("sig-conditions-grid");
    if (!grid) return;
    const c = sig.conditions || {};
    const v = sig.values     || {};

    const condDefs = [
      { key: "trend_buy",    label: "Trend (Buy)",     desc: `Price>EMA200 & EMA50>EMA200` },
      { key: "trend_sell",   label: "Trend (Sell)",    desc: `Price<EMA200 & EMA50<EMA200` },
      { key: "rsi_buy",      label: "RSI Buy Zone",    desc: `RSI ${v.rsi ?? "—"} in [50-70]` },
      { key: "rsi_sell",     label: "RSI Sell Zone",   desc: `RSI ${v.rsi ?? "—"} in [30-50]` },
      { key: "rsi_safe",     label: "RSI Not Extreme", desc: `Avoid >80 or <20` },
      { key: "candle_buy",   label: "Candle (Buy)",    desc: `Bullish + breaks ${CANDLE_LOOKBACK ?? 10}-bar high` },
      { key: "candle_sell",  label: "Candle (Sell)",   desc: `Bearish + breaks ${CANDLE_LOOKBACK ?? 10}-bar low` },
      { key: "volatility",   label: "Volatility",      desc: `ATR≥70% of ATR-MA` },
      { key: "trending",     label: "Market Trending", desc: `EMA slope ≥0.08%` },
      { key: "rsi_active",   label: "RSI Active Zone", desc: `Not in 45–55 dead zone` },
    ];

    grid.innerHTML = condDefs.map(d => {
      const val  = c[d.key];
      const icon = val ? "✓" : "✗";
      const cls  = val ? "pass" : "fail";
      return `
        <div class="cond-item">
          <span class="cond-icon ${cls}">${icon}</span>
          <div class="cond-text">
            <span class="cond-name">${d.label}</span>
            <span class="cond-desc">${d.desc}</span>
          </div>
        </div>`;
    }).join("");

    // Snapshot
    setText("sn-close",  v.close   ?? "—");
    setText("sn-ema50",  v.ema50   ?? "—");
    setText("sn-ema200", v.ema200  ?? "—");
    setText("sn-rsi",    v.rsi     ?? "—");
    setText("sn-atr",    v.atr     ?? "—");
    setText("sn-atrma",  v.atr_ma  ?? "—");
    setText("sn-rhigh",  v.recent_high ?? "—");
    setText("sn-rlow",   v.recent_low  ?? "—");
    setText("sn-slope",  v.ema200_slope_pct != null ? v.ema200_slope_pct + "%" : "—");

    setText("sn-entry", sig.entry ?? "—");
    setText("sn-sl",    sig.sl    ?? "—");
    setText("sn-tp",    sig.tp    ?? "—");
  }

  function _initSignalsPage() {
    $("sig-refresh").addEventListener("click", () => _loadSignal("signals"));
    $("sig-symbol").addEventListener("change", () => _loadSignal("signals"));
    $("sig-tf").addEventListener("change",     () => _loadSignal("signals"));
  }

  // ══════════════════════════════════════════════════════════
  //  POSITIONS PAGE
  // ══════════════════════════════════════════════════════════

  function _initPositionsPage() {
    $("pos-refresh").addEventListener("click",   _loadPositions);
    $("pos-close-all").addEventListener("click", async () => {
      if (!confirm("Close ALL open positions?")) return;
      await API.closeAll().catch(e => alert(e.message));
      _loadPositions();
    });
  }

  function _loadPositions() {
    API.positions().then(pos => {
      _state.positions = pos;
      _renderPositions(pos);
      _updatePositionStats(pos);
      $("pos-badge").textContent = pos.length || "";
      setText("d-positions", `${pos.length} position${pos.length !== 1 ? "s" : ""}`);
      setText("d-open-trades", pos.length);
    }).catch(() => {});
  }

  function _renderPositions(pos) {
    const tbody = $("positions-tbody");
    const dbody = $("d-pos-tbody");
    if (!tbody) return;

    if (!pos.length) {
      const emptyRow = `<tr><td colspan="12" class="empty-row">No open positions</td></tr>`;
      tbody.innerHTML = emptyRow;
      if (dbody) dbody.innerHTML = `<tr><td colspan="9" class="empty-row">No open positions</td></tr>`;
      return;
    }

    tbody.innerHTML = pos.map(p => `
      <tr>
        <td>${p.ticket}</td>
        <td>${p.symbol}</td>
        <td class="${p.type === "BUY" ? "type-buy" : "type-sell"}">${p.type}</td>
        <td>${p.volume}</td>
        <td>${p.price_open}</td>
        <td>${p.price_cur ?? "—"}</td>
        <td class="hl-red">${p.sl  || "—"}</td>
        <td class="hl-green">${p.tp || "—"}</td>
        <td class="${p.profit >= 0 ? "pos-pnl-green" : "pos-pnl-red"}">${fmtPnl(p.profit)}</td>
        <td>${p.swap || 0}</td>
        <td>${p.time || "—"}</td>
        <td><button class="btn-xs btn-danger" onclick="App._closePos(${p.ticket})">Close</button></td>
      </tr>`).join("");

    if (dbody) {
      dbody.innerHTML = pos.slice(0, 5).map(p => `
        <tr>
          <td>${p.symbol}</td>
          <td class="${p.type === "BUY" ? "type-buy" : "type-sell"}">${p.type}</td>
          <td>${p.volume}</td>
          <td>${p.price_open}</td>
          <td>${p.price_cur ?? "—"}</td>
          <td class="${p.profit >= 0 ? "pos-pnl-green" : "pos-pnl-red"}">${fmtPnl(p.profit)}</td>
          <td class="hl-red">${p.sl || "—"}</td>
          <td class="hl-green">${p.tp || "—"}</td>
          <td><button class="btn-xs btn-danger" onclick="App._closePos(${p.ticket})">✕</button></td>
        </tr>`).join("");
    }
  }

  function _updatePositionStats(pos) {
    const count  = pos.length;
    const vol    = pos.reduce((s, p) => s + (p.volume || 0), 0);
    const pnl    = pos.reduce((s, p) => s + (p.profit || 0), 0);
    setText("p-count",  count);
    setText("p-volume", vol.toFixed(2));
    const pnlEl = $("p-pnl");
    if (pnlEl) { pnlEl.textContent = fmtPnl(pnl); clsPnl(pnlEl, pnl); }
  }

  async function _closePos(ticket) {
    if (!confirm(`Close position #${ticket}?`)) return;
    try {
      await API.closePosition(ticket);
      _loadPositions();
    } catch (e) { alert(e.message); }
  }

  // ══════════════════════════════════════════════════════════
  //  HISTORY PAGE
  // ══════════════════════════════════════════════════════════

  function _initHistoryPage() {
    $("hist-refresh").addEventListener("click", _loadHistory);
  }

  function _loadHistory() {
    const days = $("hist-days")?.value || 30;
    API.history(days).then(deals => {
      _renderHistory(deals);
    }).catch(e => console.warn(e));
  }

  function _renderHistory(deals) {
    const tbody = $("history-tbody");
    if (!tbody) return;

    if (!deals.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-row">No trades in this period</td></tr>`;
      setText("h-total", 0); setText("h-pnl","—"); setText("h-comm","—"); setText("h-wr","—");
      return;
    }

    const totalPnl  = deals.reduce((s, d) => s + d.profit, 0);
    const totalComm = deals.reduce((s, d) => s + d.commission, 0);
    const wins      = deals.filter(d => d.profit > 0).length;
    const wr        = deals.length ? ((wins / deals.length) * 100).toFixed(1) : 0;

    setText("h-total", deals.length);
    const pnlEl = $("h-pnl");
    if (pnlEl) { pnlEl.textContent = fmtPnl(totalPnl); clsPnl(pnlEl, totalPnl); }
    setText("h-comm", fmt(totalComm));
    setText("h-wr",   `${wr}%`);

    tbody.innerHTML = deals.map(d => `
      <tr>
        <td>${d.ticket}</td>
        <td>${d.symbol}</td>
        <td class="${d.type === "BUY" ? "type-buy" : "type-sell"}">${d.type}</td>
        <td>${d.volume}</td>
        <td>${d.price}</td>
        <td class="${d.profit >= 0 ? "pos-pnl-green" : "pos-pnl-red"}">${fmtPnl(d.profit)}</td>
        <td>${fmt(d.commission)}</td>
        <td>${fmt(d.swap)}</td>
        <td>${d.time}</td>
      </tr>`).join("");
  }

  // ══════════════════════════════════════════════════════════
  //  BOT CONTROL
  // ══════════════════════════════════════════════════════════

  function _initBotControls() {
    $("btn-bot-start").addEventListener("click", async () => {
      const sym = $("bot-symbol")?.value || _state.symbol;
      const tf  = $("bot-tf")?.value    || _state.timeframe;
      try {
        await API.botStart(sym, tf);
        _state.symbol    = sym;
        _state.timeframe = tf;
        _setBotRunning(true);
        _addLog({ type: "bot_started", message: `Bot started — ${sym} ${tf}`, time: _nowTime() });
      } catch (e) { alert(e.message); }
    });

    $("btn-bot-stop").addEventListener("click", async () => {
      try {
        await API.botStop();
        _setBotRunning(false);
        _addLog({ type: "bot_stopped", message: "Bot stopped by user.", time: _nowTime() });
      } catch (e) { alert(e.message); }
    });

    $("log-clear").addEventListener("click", () => {
      $("log-console").innerHTML = `<div class="log-entry system">Log cleared.</div>`;
    });
  }

  function _setBotRunning(running) {
    _state.botRunning = running;

    $("btn-bot-start").disabled = running;
    $("btn-bot-stop").disabled  = !running;

    const dot   = $("bot-big-dot");
    const label = $("bot-state-label");
    const mode  = $("bot-mode-label");
    const navDot = $("bot-running-dot");
    const bsmDot = $("bsm-dot");
    const bsmLbl = $("bsm-label");

    if (dot)    { dot.className = `bsd-big-dot ${running ? "running" : "stopped"}`; }
    if (label)  label.textContent = running ? "RUNNING" : "STOPPED";
    if (mode)   mode.textContent  = `${_state.demoMode ? "DEMO" : "LIVE"} · ${_state.symbol} ${_state.timeframe}`;
    if (navDot) navDot.classList.toggle("hidden", !running);
    if (bsmDot) { bsmDot.className = `bsm-dot ${running ? "running" : "stopped"}`; }
    if (bsmLbl) bsmLbl.textContent = running ? "Running" : "Stopped";
  }

  function _loadBotStatus() {
    API.botStatus().then(s => {
      _setBotRunning(s.running);
      if (s.log?.length) {
        s.log.forEach(e => _addLog(e, true));
      }
      if (s.last_signal) _applyBotSignal(s.last_signal);
      if (s.risk) _applyRisk(s.risk);
    }).catch(() => {});
  }

  function _applyBotSignal(sig) {
    const pill   = $("bot-sig-pill");
    const reason = $("bot-sig-reason");
    if (pill)   { pill.className = `signal-pill ${sig.signal?.toLowerCase() ?? "none"}`; pill.textContent = sig.signal || "NONE"; }
    if (reason) reason.textContent = sig.reason || "No evaluation yet";
  }

  function _applyRisk(risk) {
    if (!risk) return;
    const pct    = Math.min((risk.daily_loss_pct || 0) / (risk.daily_loss_limit || 5) * 100, 100);
    const fill   = $("risk-meter-fill");
    if (fill) fill.style.width = pct + "%";
    setText("risk-pnl-lbl",  `${(risk.daily_loss_pct || 0).toFixed(2)}%`);
    const dpnlEl = $("r-dpnl");
    if (dpnlEl) { dpnlEl.textContent = fmtPnl(risk.daily_pnl); clsPnl(dpnlEl, risk.daily_pnl); }
    setText("r-trades", risk.trades_today ?? "—");
    const statEl = $("r-status");
    if (statEl) {
      if (risk.is_halted) { statEl.textContent = "HALTED"; statEl.className = "hl-red"; }
      else { statEl.textContent = "Active"; statEl.className = "hl-green"; }
    }
    // Also update header dpnl
    const hdrEl = $("hdr-dpnl");
    if (hdrEl) { hdrEl.textContent = fmtPnl(risk.daily_pnl); }
  }

  function _addLog(entry, silent = false) {
    const console_ = $("log-console");
    if (!console_) return;
    const div = document.createElement("div");
    div.className = `log-entry ${entry.type || "system"}`;
    div.textContent = `[${entry.time || _nowTime()}] ${entry.message}`;
    console_.appendChild(div);
    if (!silent) console_.scrollTop = console_.scrollHeight;
    // Cap at 300 entries
    while (console_.children.length > 300) console_.removeChild(console_.firstChild);
  }

  // ══════════════════════════════════════════════════════════
  //  SETTINGS PAGE
  // ══════════════════════════════════════════════════════════

  function _initSettingsPage() {
    $("btn-disconnect").addEventListener("click", async () => {
      if (!confirm("Disconnect and return to login screen?")) return;
      await API.disconnect().catch(() => {});
      location.reload();
    });
  }

  // ══════════════════════════════════════════════════════════
  //  WEBSOCKET HANDLERS
  // ══════════════════════════════════════════════════════════

  function _bindWS() {
    WS.on("tick", data => {
      if (!data) return;
      setText("live-bid",    data.bid?.toFixed(5) ?? "—");
      setText("live-ask",    data.ask?.toFixed(5) ?? "—");
      setText("live-spread", data.spread ? `${data.spread}p` : "");
      setText("sb-last-update", "Updated: " + new Date().toLocaleTimeString());
    });

    WS.on("account", data => {
      _updateAccountDisplay(data);
    });

    WS.on("positions", data => {
      _state.positions = data;
      if (_state.currentPage === "positions") _renderPositions(data);
      _updatePositionStats(data);
      $("pos-badge").textContent = data.length || "";
      setText("d-positions",   `${data.length} position${data.length !== 1 ? "s" : ""}`);
      setText("d-open-trades", data.length);
    });

    WS.on("signal", data => {
      _state.lastSignal = data;
      _applySignalDashboard(data);
      if (_state.currentPage === "signals") _applySignalPage(data, _state.symbol, _state.timeframe);
      if (_state.currentPage === "charts")  _applySignalToPanel(data);
    });

    WS.on("market", data => {
      _applyMarketStatus(data);
    });

    WS.on("bot", data => {
      if (data.running !== undefined) _setBotRunning(data.running);
      if (data.last_signal) _applyBotSignal(data.last_signal);
      if (data.risk)        _applyRisk(data.risk);
    });

    WS.on("bot_log", data => {
      _addLog(data);
    });

    WS.on("connected", data => {
      if (data) _updateAccountDisplay(data);
    });
  }

  // ══════════════════════════════════════════════════════════
  //  HELPERS
  // ══════════════════════════════════════════════════════════

  function _nowTime() {
    return new Date().toLocaleTimeString("en-GB", { hour12: false });
  }

  const CANDLE_LOOKBACK = 10;

  // ══════════════════════════════════════════════════════════
  //  INIT
  // ══════════════════════════════════════════════════════════

  function init() {
    _initLogin();
    _bindWS();
    _initSignalsPage();

    // Show all pages as display:none initially (CSS handles .active)
    document.querySelectorAll(".page").forEach(p => p.style.display = "none");
  }

  // ── Public API ─────────────────────────────────────────────
  return { init, navTo, _closePos };
})();

// Boot
document.addEventListener("DOMContentLoaded", () => App.init());

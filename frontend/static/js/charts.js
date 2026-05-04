/* ═══════════════════════════════════════════════════════
   AST Capital — TradingView Lightweight Charts Manager
═══════════════════════════════════════════════════════ */

const Charts = (() => {

  const THEME = {
    bg:      "#1a140d",
    bg2:     "#211910",
    grid:    "#2e2115",
    border:  "#3d2e1c",
    text:    "#BEA882",
    brown:   "#C08040",
    brown2:  "#D4A060",
    green:   "#52A868",
    red:     "#A85252",
    orange:  "#C08040",
  };

  const CHART_OPTS = {
    layout:        { background: { color: THEME.bg }, textColor: THEME.text },
    grid:          { vertLines: { color: THEME.grid }, horzLines: { color: THEME.grid } },
    crosshair:     { mode: 1 },
    rightPriceScale: { borderColor: THEME.border },
    timeScale:     { borderColor: THEME.border, timeVisible: true, secondsVisible: false },
  };

  // ── Instances ──────────────────────────────────────────────
  let _main, _mainSeries, _ema50Series, _ema200Series;
  let _rsi,  _rsiSeries,  _rsiOB, _rsiOS, _rsiMid;
  let _atr,  _atrSeries;
  let _mini, _miniSeries;

  // ── Main chart ────────────────────────────────────────────

  function initMain(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;

    _main = LightweightCharts.createChart(el, {
      ...CHART_OPTS,
      width:  el.clientWidth,
      height: el.clientHeight,
    });

    _mainSeries = _main.addCandlestickSeries({
      upColor:        THEME.green,
      downColor:      THEME.red,
      borderUpColor:  THEME.green,
      borderDownColor:THEME.red,
      wickUpColor:    THEME.green,
      wickDownColor:  THEME.red,
    });

    _ema50Series = _main.addLineSeries({
      color:       THEME.brown,
      lineWidth:   1,
      lineStyle:   0,
      crosshairMarkerVisible: false,
      lastValueVisible: true,
      priceLineVisible: false,
      title: "EMA 50",
    });

    _ema200Series = _main.addLineSeries({
      color:       THEME.brown2,
      lineWidth:   2,
      lineStyle:   2,
      crosshairMarkerVisible: false,
      lastValueVisible: true,
      priceLineVisible: false,
      title: "EMA 200",
    });

    window.addEventListener("resize", () => _main?.applyOptions({ width: el.clientWidth }));
  }

  function initRsi(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    _rsi = LightweightCharts.createChart(el, {
      ...CHART_OPTS,
      width:  el.clientWidth,
      height: el.clientHeight,
    });
    _rsiSeries = _rsi.addLineSeries({ color: THEME.orange, lineWidth: 1, priceLineVisible: false });
    _rsiOB     = _rsi.addLineSeries({ color: THEME.red,   lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    _rsiOS     = _rsi.addLineSeries({ color: THEME.green, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    _rsiMid    = _rsi.addLineSeries({ color: THEME.grid,  lineWidth: 1, lineStyle: 3, priceLineVisible: false, lastValueVisible: false });
    window.addEventListener("resize", () => _rsi?.applyOptions({ width: el.clientWidth }));
  }

  function initAtr(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    _atr = LightweightCharts.createChart(el, {
      ...CHART_OPTS,
      width:  el.clientWidth,
      height: el.clientHeight,
    });
    _atrSeries = _atr.addLineSeries({ color: THEME.brown, lineWidth: 1, priceLineVisible: false });
    window.addEventListener("resize", () => _atr?.applyOptions({ width: el.clientWidth }));
  }

  function initMini(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    _mini = LightweightCharts.createChart(el, {
      ...CHART_OPTS,
      width:       el.clientWidth,
      height:      el.clientHeight,
      rightPriceScale: { visible: false },
      timeScale:   { visible: false },
    });
    _miniSeries = _mini.addAreaSeries({
      lineColor:   THEME.brown,
      topColor:    "rgba(192,128,64,.2)",
      bottomColor: "rgba(192,128,64,.01)",
      lineWidth:   1,
      priceLineVisible: false,
    });
    window.addEventListener("resize", () => _mini?.applyOptions({ width: el.clientWidth }));
  }

  // ── Data loading ──────────────────────────────────────────

  function loadData(payload, showEma50, showEma200, showSignals) {
    if (!_main) return;

    _mainSeries.setData(payload.candles || []);

    _ema50Series.setData(showEma50  ? (payload.ema50  || []) : []);
    _ema200Series.setData(showEma200 ? (payload.ema200 || []) : []);

    if (showSignals && payload.markers?.length) {
      _mainSeries.setMarkers(payload.markers);
    } else {
      _mainSeries.setMarkers([]);
    }

    // RSI
    if (_rsiSeries && payload.rsi) {
      _rsiSeries.setData(payload.rsi);
      // Static overbought/oversold lines at same timestamps
      const ts = payload.rsi.map(r => r.time);
      _rsiOB.setData(ts.map(t => ({ time: t, value: 70 })));
      _rsiOS.setData(ts.map(t => ({ time: t, value: 30 })));
      _rsiMid.setData(ts.map(t => ({ time: t, value: 50 })));

      const last = payload.rsi.at(-1);
      if (last) document.getElementById("rsi-value-badge").textContent = `RSI: ${last.value.toFixed(1)}`;
    }

    // ATR
    if (_atrSeries && payload.atr) {
      _atrSeries.setData(payload.atr);
      const last = payload.atr.at(-1);
      if (last) document.getElementById("atr-value-badge").textContent = `ATR: ${last.value.toFixed(5)}`;
    }

    _main.timeScale().fitContent();
    _rsi?.timeScale().fitContent();
    _atr?.timeScale().fitContent();
  }

  function loadMini(payload) {
    if (!_mini || !payload.candles?.length) return;
    const data = payload.candles.map(c => ({ time: c.time, value: c.close }));
    _miniSeries.setData(data);
    _mini.timeScale().fitContent();
  }

  // ── Real-time update (update last candle) ─────────────────

  function updateLastCandle(tick, symbol, currentSymbol) {
    if (!_mainSeries || symbol !== currentSymbol) return;
    const price = (tick.bid + tick.ask) / 2;
    // TradingView doesn't provide current bar time from a tick — update the last bar's close
    // We can only do this properly if we track the current bar's open time
    // For now, set a last-price marker
  }

  function addTradeMarker(time, direction, price) {
    if (!_mainSeries) return;
    const existing = _mainSeries.markers ? [..._mainSeries.markers()] : [];
    existing.push({
      time,
      position: direction === "BUY" ? "belowBar" : "aboveBar",
      color:    direction === "BUY" ? THEME.green : THEME.red,
      shape:    direction === "BUY" ? "arrowUp"   : "arrowDown",
      text:     direction,
      size:     1,
    });
    _mainSeries.setMarkers(existing);
  }

  function destroyAll() {
    [_main, _rsi, _atr, _mini].forEach(c => c?.remove());
    _main = _rsi = _atr = _mini = null;
    _mainSeries = _ema50Series = _ema200Series = null;
    _rsiSeries = _rsiOB = _rsiOS = _rsiMid = null;
    _atrSeries = _miniSeries = null;
  }

  return { initMain, initRsi, initAtr, initMini, loadData, loadMini, updateLastCandle, addTradeMarker, destroyAll };
})();

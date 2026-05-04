/* ═══════════════════════════════════════════════════════
   AST Capital — WebSocket Client
   Auto-reconnect, typed message dispatch
═══════════════════════════════════════════════════════ */

const WS = (() => {
  let _ws      = null;
  let _retries = 0;
  let _handlers = {};

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url   = `${proto}://${location.host}/ws`;
    _ws = new WebSocket(url);

    _ws.onopen = () => {
      _retries = 0;
      _emit("_connected");
      document.getElementById("ws-indicator").classList.add("connected");
      document.getElementById("sb-ws-status").textContent = "WebSocket: connected";
      // keep-alive ping every 20s
      _ws._pingInterval = setInterval(() => {
        if (_ws.readyState === WebSocket.OPEN) _ws.send("ping");
      }, 20000);
    };

    _ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        _emit(msg.type, msg.data, msg);
        _emit("*", msg);   // wildcard handler
      } catch (e) { /* ignore non-JSON */ }
    };

    _ws.onclose = () => {
      clearInterval(_ws._pingInterval);
      document.getElementById("ws-indicator").classList.remove("connected");
      document.getElementById("sb-ws-status").textContent = "WebSocket: reconnecting…";
      _emit("_disconnected");
      const delay = Math.min(1000 * 2 ** _retries, 30000);
      _retries++;
      setTimeout(connect, delay);
    };

    _ws.onerror = () => _ws.close();
  }

  function on(type, fn) {
    if (!_handlers[type]) _handlers[type] = [];
    _handlers[type].push(fn);
  }

  function off(type, fn) {
    if (_handlers[type]) _handlers[type] = _handlers[type].filter(h => h !== fn);
  }

  function _emit(type, data, raw) {
    (_handlers[type] || []).forEach(fn => {
      try { fn(data, raw); } catch (e) { console.error("WS handler error:", e); }
    });
  }

  return { connect, on, off };
})();

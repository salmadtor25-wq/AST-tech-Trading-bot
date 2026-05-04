# ◈ AST CAPITAL — Algorithmic Trading Bot

> **Disclaimer:** This software does not guarantee profit. Past performance is not indicative of future results. Always backtest thoroughly and trade in DEMO mode before risking real capital.

---

## Architecture

```
AST-tech-Trading-bot/
├── bot/
│   ├── main.py          ← entry point (GUI + CLI)
│   ├── config.py        ← all settings, colours, risk params
│   ├── logger.py        ← gold-themed terminal + file logging
│   ├── data.py          ← MT5 data fetcher + CSV cache
│   ├── indicators.py    ← EMA50, EMA200, RSI14, ATR14
│   ├── strategy.py      ← signal generation (EMA cross + RSI)
│   ├── risk.py          ← position sizing, daily loss limit
│   ├── backtest.py      ← bar-by-bar engine + matplotlib charts
│   ├── trader.py        ← live/demo order execution via MT5
│   └── login_ui.py      ← dark-gold Tkinter GUI
├── requirements.txt
└── README.md
```

---

## 1 — Install Dependencies

```bash
pip install -r requirements.txt
```

> **MetaTrader 5** only runs on **Windows**.  
> On Linux/macOS you can still run headless backtests using CSV cache or synthetic data.

---

## 2 — Run the GUI (recommended)

```bash
cd bot
python main.py
```

This opens the AST Capital login screen where you enter your MT5 credentials.

**Your credentials look like this:**

| Field          | Example value         |
|----------------|-----------------------|
| Account Login  | `12345678`            |
| Password       | `your_password`       |
| Broker Server  | `YourBroker-Server`   |

Credentials are saved to `bot/credentials.json` (chmod 600, git-ignored).

---

## 3 — Run a Headless Backtest (no MT5 / GUI needed)

```bash
cd bot
python main.py --backtest --symbol EURUSD --tf H1 --balance 10000
```

- Fetches data from MT5 if connected, otherwise uses CSV cache or synthetic data.
- Outputs results to terminal and saves a chart PNG to `bot/data/`.

---

## 4 — Connect MetaTrader 5

1. Install [MetaTrader 5](https://www.metatrader5.com/) on Windows.
2. Log in to your **demo account** in the MT5 terminal.
3. Enable **"Allow Algorithmic Trading"** in Tools → Options → Expert Advisors.
4. Run the bot — it will connect via the MT5 Python API running on the same machine.

---

## 5 — Run Demo Trading (CLI)

```bash
cd bot
python main.py --demo --symbol EURUSD --tf H1
```

Press `Ctrl+C` to stop gracefully.

---

## 6 — Enable LIVE Trading

> ⚠ **Read carefully before enabling live trading.**

1. Test in **DEMO mode** for a minimum of 30 days / 30+ trades.
2. Review backtest results — ensure drawdown is acceptable.
3. Open `bot/config.py` and set:
   ```python
   LIVE_TRADING_ENABLED = True
   ```
4. In the GUI, select **LIVE** mode and confirm the warning dialog.

The bot will still ask for a second confirmation before any real-money session starts.

---

## Strategy Summary

| Component     | Setting                              |
|---------------|--------------------------------------|
| Trend filter  | Price vs EMA 200                     |
| Entry trigger | EMA 50 crosses EMA 200               |
| Confirmation  | RSI 14 in [50–70] BUY / [30–50] SELL |
| Stop Loss     | 1.5 × ATR (14)                       |
| Take Profit   | 2.0 × ATR (14)                       |
| Risk/trade    | 1% of account balance                |
| Max positions | 3 simultaneous                        |
| Daily halt    | Trading stops at 5% daily loss       |

---

## Risk Parameters (config.py)

```python
RISK_PER_TRADE   = 0.01   # 1%
MAX_OPEN_TRADES  = 3
DAILY_LOSS_LIMIT = 0.05   # 5%
SL_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 2.0
```

---

## 3 Ways to Improve the Strategy

### 1 — Add a Volume / Volatility Filter
Require ATR to be above its 20-period moving average before taking a trade.  
Low-volatility environments produce more false crossovers.

### 2 — Add Session Filter
Only trade during the London (07:00–15:00 UTC) and New York (13:00–21:00 UTC) sessions.  
Asian-session crossovers on major pairs have historically lower follow-through.

### 3 — Multi-Timeframe Confirmation
Before entering on H1, confirm the H4 trend is aligned (H4 EMA50 > EMA200 for buys).  
This reduces counter-trend entries significantly.

---

## Avoiding Overfitting

- **Walk-forward test:** split data — train on 70%, test on unseen 30%.
- **Never optimise parameters on the test set.** Tune only on training data.
- **Keep the strategy simple:** fewer parameters = less overfitting surface area.
- **Test on multiple symbols and timeframes** — a robust edge works broadly.
- **Use enough trades:** aim for 100+ trades per test period for statistical significance.

---

## Safe Pre-Live Checklist

- [ ] 30+ days of demo trading completed
- [ ] Win rate > 40% AND profit factor > 1.3 in backtest AND demo
- [ ] Max drawdown in demo < 10%
- [ ] Daily loss limit never triggered unexpectedly
- [ ] Position sizing verified manually (check lot sizes placed)
- [ ] VPS / stable internet confirmed
- [ ] Broker swap/commission costs factored in
- [ ] `LIVE_TRADING_ENABLED = True` set consciously and deliberately

---

*© 2024 AST Capital — For authorised users only.*

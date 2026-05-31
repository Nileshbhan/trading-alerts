# Verity Trading Alert System v2.0

## Tonight's Setup (7 PM — 15 minutes)

### Step 1 — Get Telegram Chat ID
1. Open Telegram → message @VerityTradingAlerts_bot → send /start
2. Open browser: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
3. Find "id" inside "chat" object — that's your CHAT_ID

### Step 2 — Push to GitHub
```bash
cd trading-alerts
git init
git add .
git commit -m "Verity Trading Alert System v2.0"
git remote add origin https://github.com/Nileshbhan/trading-alerts
git push -u origin main
```

### Step 3 — Deploy on Railway
1. railway.app → New Project → Deploy from GitHub repo
2. Add environment variables:
   TELEGRAM_BOT_TOKEN = (your new token)
   TELEGRAM_CHAT_ID   = (from step 1)
3. Deploy. Done. Runs 24/7 forever.

### Step 4 — Test
Railway logs will show "✅ Telegram connected" on startup.
You'll receive a test message on Telegram immediately.

---

## What You'll Receive on Telegram

### 7:45 AM Daily (Waka Waka 🎵):
- Today's instrument (Nifty/Sensex)
- Expiry day flag
- New series flag
- Global/Asian futures
- Brent/WTI crude
- GIFT Nifty, VIX, Rupee
- FII cash + F&O data
- Moving averages (auto-computed)

### 10:30 AM Daily:
- Mandatory contra trade evaluation

### 3:00 PM (Expiry Eve):
- Max pain gap alert if close is 200+ pts from max pain

### Anytime During Market Hours:
- Double Top/Bottom
- Triple Top/Bottom
- Stop Hunt detected
- Max Pain Gap
- Near key support/resistance
- Sharp velocity move (50+ pts)
- Hammer / Shooting Star
- Bullish/Bearish Engulfing
- Morning/Evening Star
- Doji (indecision)
- MA Cross (20 EMA)
- Narrow range day → SKIP alert

---

## Monthly Maintenance
Update in main.py:
1. _new_series_dates — add first trading day of each new series
2. KEY_RESISTANCE / KEY_SUPPORT in config.py — review every Monday

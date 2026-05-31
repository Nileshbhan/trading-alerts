# config.py — All settings in one place
import os

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

# ─── Market Hours (IST) ──────────────────────────────────────────────────────
MARKET_OPEN_HOUR   = 9
MARKET_OPEN_MIN    = 15
MARKET_CLOSE_HOUR  = 15
MARKET_CLOSE_MIN   = 30

# ─── Fetch Interval ──────────────────────────────────────────────────────────
FETCH_INTERVAL_MINS = 2  # Every 2 minutes during market hours

# ─── Pattern Detection Thresholds ───────────────────────────────────────────
DOUBLE_TOP_TOLERANCE    = 0.002   # 0.2% — peaks within this = double top
DOUBLE_BOTTOM_TOLERANCE = 0.002
MIN_PATTERN_CANDLES     = 3       # Min candles between peaks/troughs
VELOCITY_THRESHOLD      = 50      # Points — single candle sharp move
LEVEL_PROXIMITY         = 30      # Points — alert when near key level
MAX_PAIN_GAP_THRESHOLD  = 200     # Points — max pain gap trade trigger
NARROW_RANGE_THRESHOLD  = 100     # Points — day range below this = skip
NARROW_RANGE_VIX        = 14      # VIX below this + narrow range = skip day

# ─── Weekly Instrument Schedule ──────────────────────────────────────────────
# Mon/Wed/Fri = Nifty options (Tue expiry)
# Tue/Thu     = Sensex options (Thu expiry)
INSTRUMENT_SCHEDULE = {
    0: "NIFTY",    # Monday
    1: "SENSEX",   # Tuesday   ← Nifty expiry day
    2: "NIFTY",    # Wednesday
    3: "SENSEX",   # Thursday  ← Sensex expiry day
    4: "NIFTY",    # Friday
}
EXPIRY_DAYS = {1: "NIFTY", 3: "SENSEX"}  # Day: expiring instrument

# ─── Key Levels (update every Monday) ───────────────────────────────────────
KEY_RESISTANCE = [24000, 23800, 23700]
KEY_SUPPORT    = [23600, 23400, 23200, 23000]

# ─── Alert Cooldown (minutes) ────────────────────────────────────────────────
ALERT_COOLDOWN_MINS = 15  # Don't repeat same pattern within 15 mins

# ─── Data Sources ────────────────────────────────────────────────────────────
# NSE = PRIMARY (live OHLC, VIX, option chain, MAs)
# Moneycontrol = SECONDARY (crude, FII, global futures, rupee)
# Yahoo Finance = BACKUP (if NSE fails)
NSE_BASE     = "https://www.nseindia.com/api"
MC_BASE      = "https://priceapi.moneycontrol.com/pricefeed"
YAHOO_NIFTY  = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=5m&range=1d"

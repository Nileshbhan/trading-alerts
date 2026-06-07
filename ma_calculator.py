
# ma_calculator.py — FIXED
# Added: weekly_high, weekly_low, monthly_high, monthly_low for multi-timeframe detection
# Added: MA proximity alert support
 
import requests
from datetime import datetime, timedelta
import pytz
 
IST = pytz.timezone("Asia/Kolkata")
 
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com"
}
 
def fetch_nse_historical(symbol="NIFTY 50", days=250):
    """Fetch historical daily OHLC from NSE"""
    try:
        end = datetime.now(IST)
        start = end - timedelta(days=days)
        url = (f"https://www.nseindia.com/api/historical/indicesHistory"
               f"?indexType={symbol}"
               f"&from={start.strftime('%d-%m-%Y')}"
               f"&to={end.strftime('%d-%m-%Y')}")
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        r = session.get(url, headers=NSE_HEADERS, timeout=10)
        data = r.json()
        closes = [float(d["CLOSE"]) for d in data["data"]["indexCloseOnlineRecords"]]
        highs  = [float(d["EOD_HIGH_INDEX_VAL"]) for d in data["data"]["indexCloseOnlineRecords"]]
        lows   = [float(d["EOD_LOW_INDEX_VAL"])  for d in data["data"]["indexCloseOnlineRecords"]]
        return closes, highs, lows
    except Exception as e:
        print(f"NSE historical fetch error: {e}")
        return [], [], []
 
def calculate_ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return round(ema, 2)
 
def calculate_sma(values, period):
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 2)
 
def get_all_mas():
    """
    Compute all MAs + weekly/monthly high/low for multi-timeframe detection.
    Returns dict with ema_20, ema_50, sma_200, weekly_high, weekly_low,
    monthly_high, monthly_low, ma_proximity_alerts
    """
    closes, highs, lows = fetch_nse_historical(days=300)
    if not closes:
        return {}
 
    ema_20  = calculate_ema(closes, 20)
    ema_50  = calculate_ema(closes, 50)
    sma_200 = calculate_sma(closes, 200)
 
    # Weekly = last 5 trading days
    weekly_high  = max(highs[-5:])  if len(highs) >= 5  else None
    weekly_low   = min(lows[-5:])   if len(lows)  >= 5  else None
 
    # Monthly = last 22 trading days
    monthly_high = max(highs[-22:]) if len(highs) >= 22 else None
    monthly_low  = min(lows[-22:])  if len(lows)  >= 22 else None
 
    current_price = closes[-1] if closes else 0
 
    # Proximity alerts — within 75 pts of any key MA
    proximity_alerts = []
    ma_levels = {
        "20 EMA": ema_20,
        "50 EMA": ema_50,
        "200 SMA": sma_200
    }
    for name, level in ma_levels.items():
        if level and abs(current_price - level) <= 75:
            direction = "above" if current_price > level else "below"
            gap = round(abs(current_price - level), 0)
            proximity_alerts.append(
                f"⚡ {name} at {level} — price {gap} pts {direction}"
            )
 
    return {
        "ema_20":          ema_20,
        "ema_50":          ema_50,
        "sma_200":         sma_200,
        "weekly_high":     round(weekly_high,  2) if weekly_high  else None,
        "weekly_low":      round(weekly_low,   2) if weekly_low   else None,
        "monthly_high":    round(monthly_high, 2) if monthly_high else None,
        "monthly_low":     round(monthly_low,  2) if monthly_low  else None,
        "proximity_alerts": proximity_alerts
    }
 
def interpret_mas(mas, current_price):
    """Human-readable MA summary for morning brief"""
    if not mas:
        return "MA data unavailable"
 
    ema_20  = mas.get("ema_20")
    ema_50  = mas.get("ema_50")
    sma_200 = mas.get("sma_200")
    alerts  = mas.get("proximity_alerts", [])
 
    lines = ["📊 *Key MA Levels:*"]
    if ema_20:
        rel = "above ✅" if current_price > ema_20 else "below ⚠️"
        lines.append(f"  20 EMA:  {ema_20}  — price {rel}")
    if ema_50:
        rel = "above ✅" if current_price > ema_50 else "below ⚠️"
        lines.append(f"  50 EMA:  {ema_50}  — price {rel}")
    if sma_200:
        rel = "above ✅" if current_price > sma_200 else "below ⚠️"
        lines.append(f"  200 SMA: {sma_200} — price {rel}")
 
    w_high = mas.get("weekly_high")
    w_low  = mas.get("weekly_low")
    m_high = mas.get("monthly_high")
    m_low  = mas.get("monthly_low")
 
    if w_high and w_low:
        lines.append(f"  Weekly range: {w_low} — {w_high}")
    if m_high and m_low:
        lines.append(f"  Monthly range: {m_low} — {m_high}")
 
    if alerts:
        lines.append("\n⚡ *Proximity Alerts:*")
        for a in alerts:
            lines.append(f"  {a}")
 
    return "\n".join(lines)
 

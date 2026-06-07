
# main.py — Entry point, scheduler, orchestrator
 
import time
from datetime import datetime, date
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
 
from fetcher import fetch_all, fetch_vix, init_nse_session
from detector import run_all_checks, get_weekly_bias, check_narrow_range, check_max_pain_gap
from alerts import (send_pattern_alert, send_morning_briefing_reminder,
                    send_contra_reminder, send_narrow_range_alert,
                    send_max_pain_gap_alert, send_stop_out_warning, test_connection)
from store import store
from ma_calculator import get_all_mas, interpret_mas
from config import (FETCH_INTERVAL_MINS, INSTRUMENT_SCHEDULE, EXPIRY_DAYS,
                    ALERT_COOLDOWN_MINS, MAX_PAIN_GAP_THRESHOLD)
 
IST = pytz.timezone("Asia/Kolkata")
 
# ─── State ───────────────────────────────────────────────────────────────────
_last_fetch_data = {}
_mas_cache = {}
_mas_last_fetched = None
_morning_sent_date = None
_new_series_dates = []  # Manually update monthly
 
def is_market_hours():
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t
 
def is_pre_market():
    """7:30 AM to 9:15 AM"""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    pre_open = now.replace(hour=7, minute=30, second=0, microsecond=0)
    market   = now.replace(hour=9, minute=15, second=0, microsecond=0)
    return pre_open <= now < market
 
def get_today_instrument():
    day = datetime.now(IST).weekday()
    return INSTRUMENT_SCHEDULE.get(day, "NIFTY")
 
def is_expiry_day():
    day = datetime.now(IST).weekday()
    return day in EXPIRY_DAYS
 
def is_new_series():
    today = date.today()
    return today in _new_series_dates
 
def get_cached_mas():
    """Fetch MAs once per day at market open"""
    global _mas_cache, _mas_last_fetched
    today = date.today()
    if _mas_last_fetched != today:
        print("Computing MAs from NSE daily data...")
        _mas_cache = get_all_mas()
        _mas_last_fetched = today
        print(f"MAs computed: {_mas_cache}")
    return _mas_cache
 
# ─── Morning Briefing ────────────────────────────────────────────────────────
def send_morning_briefing():
    global _morning_sent_date
    today = date.today()
    if _morning_sent_date == today:
        return
 
    print("Sending morning briefing...")
    data = fetch_all()
    mas = get_cached_mas()
    instrument = get_today_instrument()
    expiry = is_expiry_day()
    new_series = is_new_series()
 
    sent = send_morning_briefing_reminder(
        instrument=instrument,
        is_expiry=expiry,
        is_new_series=new_series,
        crude=data.get("crude", {}),
        global_mkts=data.get("global_markets", {}),
        fii=data.get("fii", {}),
        gift_nifty=data.get("gift_nifty", 0),
        vix=data.get("candle").vix if data.get("candle") else 0,
        mas=mas,
        rupee=data.get("rupee", 0)
    )
    if sent:
        _morning_sent_date = today
        print("✅ Morning briefing sent")
 
# ─── Contra Reminder ─────────────────────────────────────────────────────────
def send_contra():
    if not is_market_hours():
        return
    latest = store.latest()
    if not latest:
        return
    bias = get_weekly_bias()
    send_contra_reminder(
        current_price=latest.close,
        current_bias=bias[0],
        vix=latest.vix,
        pcr=latest.pcr
    )
    print("✅ Contra reminder sent")
 
# ─── Max Pain Gap Check (Eve of expiry) ─────────────────────────────────────
def check_expiry_eve_max_pain():
    now = datetime.now(IST)
    tomorrow_day = (now.weekday() + 1) % 7
    if tomorrow_day not in EXPIRY_DAYS:
        return
    latest = store.latest()
    if not latest:
        return
    oc_data = store.last_oc_data
    max_pain = oc_data.get("max_pain", 0)
    if not max_pain:
        return
    gap = abs(latest.close - max_pain)
    if gap >= MAX_PAIN_GAP_THRESHOLD:
        instrument = EXPIRY_DAYS[tomorrow_day]
        send_max_pain_gap_alert(latest.close, max_pain, instrument)
        print(f"✅ Max pain gap alert sent: {gap} pts from {max_pain}")
 
# ─── Main Fetch & Detect Loop ────────────────────────────────────────────────
def fetch_and_detect():
    if not is_market_hours():
        return
 
    now_str = datetime.now(IST).strftime("%H:%M:%S")
    print(f"[{now_str}] Fetching...")
 
    # Fetch all data
    data = fetch_all()
    candle = data.get("candle")
    if not candle:
        print("No candle data received")
        return
 
    # Update store
    store.add(candle)
    store.last_oc_data = data.get("oc_data", {})
    print(f"Nifty: {candle.close} | VIX: {candle.vix} | PCR: {candle.pcr} | MaxPain: {store.last_oc_data.get('max_pain')}")
 
    # Get cached MAs + update store for multi-timeframe detection
    mas = get_cached_mas()
    if mas:
        store.last_mas = mas
    ema_20 = mas.get("ema_20") if mas else None
 
    # Get instrument + bias
    instrument = get_today_instrument()
    weekly_bias = get_weekly_bias()
 
    # Narrow range check — alert once
    day_range = store.get_day_range()
    if check_narrow_range(store.get_highs(), store.get_lows(), candle.vix):
        if store.can_alert("narrow_range", cooldown_mins=120):
            send_narrow_range_alert(day_range, candle.vix)
            store.mark_alerted("narrow_range")
            return
 
    # Run all pattern checks
    patterns = run_all_checks(
        max_pain=store.last_oc_data.get("max_pain", 0),
        ema_20=ema_20
    )
 
    # Send alerts for new patterns
    for pattern in patterns:
        pattern_name = pattern["pattern"]
        if store.can_alert(pattern_name, ALERT_COOLDOWN_MINS):
            sent = send_pattern_alert(
                pattern_data=pattern,
                latest_candle=candle,
                weekly_bias=weekly_bias,
                instrument=instrument,
                oc_data=store.last_oc_data
            )
            if sent:
                store.mark_alerted(pattern_name)
                print(f"🚨 Alert sent: {pattern_name}")
 
# ─── Daily Reset ─────────────────────────────────────────────────────────────
def daily_reset():
    store.reset_daily()
    init_nse_session()
    print("✅ Daily reset complete")
 
# ─── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Verity Trading Alert System v2.0 Starting...")
    print("Patterns: Double/Triple Top-Bottom, Stop Hunt, Max Pain Gap,")
    print("          Hammer, Shooting Star, Engulfing, Doji, Morning/Evening Star,")
    print("          Key Levels, MA Cross, Velocity, Narrow Range")
    print("Schedule: Mon/Wed/Fri=Nifty | Tue/Thu=Sensex | Expiry days auto-detected")
    print("Alerts → Telegram @VerityTradingAlerts_bot")
 
    # Init NSE session
    init_nse_session()
 
    # Test Telegram
    print("Testing Telegram connection...")
    if test_connection():
        print("✅ Telegram connected")
    else:
        print("❌ Telegram failed — check token and chat ID")
 
    # Compute MAs on startup
    get_cached_mas()
 
    # Scheduler
    scheduler = BlockingScheduler(timezone=IST)
 
    # Main fetch every 2 mins during market hours
    scheduler.add_job(fetch_and_detect, 'interval',
                      minutes=FETCH_INTERVAL_MINS, id='fetch')
 
    # Morning briefing — 7:45 AM weekdays
    scheduler.add_job(send_morning_briefing, 'cron',
                      hour=7, minute=45, id='morning')
 
    # Contra reminder — 10:30 AM weekdays
    scheduler.add_job(send_contra, 'cron',
                      hour=10, minute=30, id='contra')
 
    # Max pain gap check — 3:00 PM (eve of expiry)
    scheduler.add_job(check_expiry_eve_max_pain, 'cron',
                      hour=15, minute=0, id='maxpain_gap')
 
    # Daily reset — 8:00 AM
    scheduler.add_job(daily_reset, 'cron',
                      hour=8, minute=0, id='reset')
 
    print("\n✅ All jobs scheduled. System running.\n")
 
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("System stopped.")
 

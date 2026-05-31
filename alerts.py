# alerts.py — Telegram alert sender

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from datetime import datetime

def _send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False

def send_pattern_alert(pattern_data, latest_candle, weekly_bias, instrument, oc_data):
    now = datetime.now().strftime("%I:%M %p")
    max_pain = oc_data.get("max_pain", "N/A")
    ce_walls = ", ".join(str(x) for x in oc_data.get("ce_walls", []))
    pe_walls = ", ".join(str(x) for x in oc_data.get("pe_walls", []))

    msg = f"""
🚨 *VERITY TRADING ALERT*
⏰ {now} | 📊 {instrument}

*{pattern_data['pattern']}*
📍 Level: {pattern_data['level']}
ℹ️ {pattern_data['detail']}
💡 {pattern_data['action']}

━━━━━━━━━━━━━━
📈 Nifty: `{latest_candle.close}`
😰 VIX: `{latest_candle.vix}`
📉 PCR: `{latest_candle.pcr}`
🎯 Max Pain: `{max_pain}`
🔴 CE Walls: `{ce_walls}`
🟢 PE Walls: `{pe_walls}`
━━━━━━━━━━━━━━
📅 Bias: {weekly_bias[0]}

_Paste in Claude for full trade call_
"""
    return _send(msg)

def send_morning_briefing_reminder(instrument, is_expiry, is_new_series,
                                    crude, global_mkts, fii, gift_nifty,
                                    vix, mas, rupee):
    now_str = datetime.now().strftime("%A, %d %b %Y")

    # Format global markets
    mkt_lines = ""
    for name, val in global_mkts.items():
        emoji = "🟢" if float(val.get("chg_pct", 0)) >= 0 else "🔴"
        mkt_lines += f"{emoji} {name}: {val.get('last')} ({val.get('chg_pct')}%)\n"

    expiry_flag = "⚡ *EXPIRY DAY*" if is_expiry else ""
    new_series_flag = "🆕 *FIRST DAY OF NEW SERIES*" if is_new_series else ""

    ma_lines = ""
    if mas:
        ma_lines = f"""
📐 *Moving Averages*
20 EMA: `{mas.get('ema_20')}` | 50 EMA: `{mas.get('ema_50')}` | 200 SMA: `{mas.get('sma_200')}`
"""

    msg = f"""
🌅 *GOOD MORNING — VERITY TRADING*
🎵 _Waka Waka! Time to make money!_
📅 {now_str}
{expiry_flag}
{new_series_flag}

📊 *Today's Instrument: {instrument}*

━━━━━━━━━━━━━━
🌍 *Global Markets*
{mkt_lines}
━━━━━━━━━━━━━━
🛢️ *Crude*
Brent: `${crude.get('brent')}` | WTI: `${crude.get('wti')}`

💱 Rupee: `{rupee}`
🎁 GIFT Nifty: `{gift_nifty}`
😰 VIX: `{vix}`
{ma_lines}
━━━━━━━━━━━━━━
🏦 *FII Activity*
Cash: `{fii.get('fii_cash')}` Cr | DII: `{fii.get('dii_cash')}` Cr
Index Fut: `{fii.get('fii_index_fut')}` Cr
Index Opt: `{fii.get('fii_index_opt')}` Cr

━━━━━━━━━━━━━━
_Market opens in 90 mins. Type: Brief me_
"""
    return _send(msg)

def send_contra_reminder(current_price, current_bias, vix, pcr):
    now = datetime.now().strftime("%I:%M %p")
    msg = f"""
⚡ *10:30 AM — MANDATORY CONTRA TRADE CHECK*
⏰ {now}

Current Nifty: `{current_price}`
Current Bias: {current_bias}
VIX: `{vix}` | PCR: `{pcr}`

❓ *Is the OPPOSITE trade better right now?*
• Double top/bottom visible?
• Draggers vs pullers ratio?
• Stop hunt completed?
• Macro override active?

_Paste in Claude for contra trade analysis_
"""
    return _send(msg)

def send_narrow_range_alert(day_range, vix):
    msg = f"""
⛔ *SKIP TRADING TODAY*

Narrow range day detected:
📏 Range so far: `{round(day_range, 0)}` pts
😴 VIX: `{vix}` (below 14)

Insufficient range for meaningful R/R.
*No trades today — preserve capital.*
"""
    return _send(msg)

def send_max_pain_gap_alert(current, max_pain, instrument):
    gap = current - max_pain
    direction = "BELOW" if gap < 0 else "ABOVE"
    fade_trade = "CE (buy)" if gap < 0 else "PE (sell)"
    msg = f"""
🎯 *MAX PAIN GAP TRADE ALERT*
📊 {instrument} Expiry Tomorrow

Current: `{current}`
Max Pain: `{max_pain}`
Gap: `{abs(round(gap, 0))}` pts *{direction}* max pain

*Rule: Fade toward max pain*
💡 Evaluate: {fade_trade}
Entry tomorrow — fade the gap direction
"""
    return _send(msg)

def send_stop_out_warning(consecutive_stops):
    msg = f"""
⚠️ *STOP-OUT WARNING*

{consecutive_stops} consecutive stops hit.

{"🛑 *HALT TRADING TODAY* — 3 stops reached. System rule." if consecutive_stops >= 3 else f"⚠️ {consecutive_stops}/3 stops. Be careful."}

Review setup before next trade.
"""
    return _send(msg)

def test_connection():
    """Test Telegram connection"""
    msg = "✅ *Verity Trading Alert System* — Connection test successful!\n\n_System is online and monitoring._"
    return _send(msg)

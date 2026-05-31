# detector.py — Complete pattern detection engine

from config import *
from store import store
from datetime import datetime

# ─── Local extrema helpers ──────────────────────────────────────────────────
def find_local_maxima(values, min_gap=3):
    peaks = []
    for i in range(min_gap, len(values) - min_gap):
        if all(values[i] >= values[i-j] for j in range(1, min_gap+1)) and \
           all(values[i] >= values[i+j] for j in range(1, min_gap+1)):
            peaks.append((i, values[i]))
    return peaks

def find_local_minima(values, min_gap=3):
    troughs = []
    for i in range(min_gap, len(values) - min_gap):
        if all(values[i] <= values[i-j] for j in range(1, min_gap+1)) and \
           all(values[i] <= values[i+j] for j in range(1, min_gap+1)):
            troughs.append((i, values[i]))
    return troughs

# ─── Double Top / Bottom ────────────────────────────────────────────────────
def check_double_top(highs):
    peaks = find_local_maxima(highs)
    if len(peaks) < 2:
        return None
    p1_idx, p1_val = peaks[-2]
    p2_idx, p2_val = peaks[-1]
    diff = abs(p1_val - p2_val) / p1_val
    if diff <= DOUBLE_TOP_TOLERANCE and (p2_idx - p1_idx) >= MIN_PATTERN_CANDLES:
        return {
            "pattern": "Double Top 🔴",
            "level": round((p1_val + p2_val) / 2, 2),
            "detail": f"Top 1: {round(p1_val,2)} | Top 2: {round(p2_val,2)}",
            "action": "⚠️ Evaluate PE trade — sell on rally"
        }
    return None

def check_double_bottom(lows):
    troughs = find_local_minima(lows)
    if len(troughs) < 2:
        return None
    t1_idx, t1_val = troughs[-2]
    t2_idx, t2_val = troughs[-1]
    diff = abs(t1_val - t2_val) / t1_val
    if diff <= DOUBLE_BOTTOM_TOLERANCE and (t2_idx - t1_idx) >= MIN_PATTERN_CANDLES:
        return {
            "pattern": "Double Bottom 🟢",
            "level": round((t1_val + t2_val) / 2, 2),
            "detail": f"Bottom 1: {round(t1_val,2)} | Bottom 2: {round(t2_val,2)}",
            "action": "⚠️ Evaluate CE trade — buy the dip"
        }
    return None

# ─── Triple Top / Bottom ────────────────────────────────────────────────────
def check_triple_top(highs):
    peaks = find_local_maxima(highs)
    if len(peaks) < 3:
        return None
    p1_idx, p1 = peaks[-3]
    p2_idx, p2 = peaks[-2]
    p3_idx, p3 = peaks[-1]
    avg = (p1 + p2 + p3) / 3
    if all(abs(p - avg) / avg <= DOUBLE_TOP_TOLERANCE * 1.5 for p in [p1, p2, p3]):
        return {
            "pattern": "Triple Top 🔴🔴",
            "level": round(avg, 2),
            "detail": f"3 peaks near {round(avg,2)} — strong resistance",
            "action": "⚠️ Strong PE signal — high conviction sell"
        }
    return None

def check_triple_bottom(lows):
    troughs = find_local_minima(lows)
    if len(troughs) < 3:
        return None
    t1_idx, t1 = troughs[-3]
    t2_idx, t2 = troughs[-2]
    t3_idx, t3 = troughs[-1]
    avg = (t1 + t2 + t3) / 3
    if all(abs(t - avg) / avg <= DOUBLE_BOTTOM_TOLERANCE * 1.5 for t in [t1, t2, t3]):
        return {
            "pattern": "Triple Bottom 🟢🟢",
            "level": round(avg, 2),
            "detail": f"3 troughs near {round(avg,2)} — strong support",
            "action": "⚠️ Strong CE signal — high conviction buy"
        }
    return None

# ─── Stop Hunt Detection ────────────────────────────────────────────────────
def check_stop_hunt(lows, closes, highs):
    """Detect stop hunt: breach of key level followed by immediate recovery"""
    if len(closes) < 3:
        return None

    # Bearish stop hunt: price dips below recent low then recovers
    recent_low = min(lows[-6:-1]) if len(lows) > 6 else min(lows[:-1])
    if lows[-1] < recent_low and closes[-1] > recent_low:
        return {
            "pattern": "Stop Hunt 🎯 (Bearish → Bullish)",
            "level": round(closes[-1], 2),
            "detail": f"Dipped to {round(lows[-1],2)}, recovering above {round(recent_low,2)}",
            "action": "⚠️ Potential mean reversion UP — evaluate CE"
        }

    # Bullish stop hunt: price spikes above recent high then reverses
    recent_high = max(highs[-6:-1]) if len(highs) > 6 else max(highs[:-1])
    if highs[-1] > recent_high and closes[-1] < recent_high:
        return {
            "pattern": "Stop Hunt 🎯 (Bullish → Bearish)",
            "level": round(closes[-1], 2),
            "detail": f"Spiked to {round(highs[-1],2)}, reversing below {round(recent_high,2)}",
            "action": "⚠️ Potential mean reversion DOWN — evaluate PE"
        }
    return None

# ─── Max Pain Gap Detection ─────────────────────────────────────────────────
def check_max_pain_gap(current_price, max_pain):
    """Alert when price is 200+ pts from max pain"""
    if not max_pain:
        return None
    gap = current_price - max_pain
    if abs(gap) >= MAX_PAIN_GAP_THRESHOLD:
        direction = "BELOW" if gap < 0 else "ABOVE"
        fade = "CE trade (buy)" if gap < 0 else "PE trade (sell)"
        return {
            "pattern": f"Max Pain Gap ⚡ ({abs(round(gap,0))} pts {direction} max pain)",
            "level": current_price,
            "detail": f"Max Pain: {max_pain} | Current: {current_price} | Gap: {round(abs(gap),0)} pts",
            "action": f"⚠️ Fade toward max pain — evaluate {fade}"
        }
    return None

# ─── Key Level Proximity ────────────────────────────────────────────────────
def check_key_levels(close):
    for level in KEY_RESISTANCE:
        if abs(close - level) <= LEVEL_PROXIMITY:
            return {
                "pattern": f"Near Resistance {level} 🔴",
                "level": level,
                "detail": f"Price {close} within {LEVEL_PROXIMITY} pts of resistance",
                "action": "Watch for rejection — potential PE"
            }
    for level in KEY_SUPPORT:
        if abs(close - level) <= LEVEL_PROXIMITY:
            return {
                "pattern": f"Near Support {level} 🟢",
                "level": level,
                "detail": f"Price {close} within {LEVEL_PROXIMITY} pts of support",
                "action": "Watch for bounce — potential CE"
            }
    return None

# ─── Velocity / Sharp Move ──────────────────────────────────────────────────
def check_velocity(closes):
    if len(closes) < 2:
        return None
    move = abs(closes[-1] - closes[-2])
    if move >= VELOCITY_THRESHOLD:
        direction = "🔴 DOWN" if closes[-1] < closes[-2] else "🟢 UP"
        return {
            "pattern": f"Sharp Move {direction} ({round(move,0)} pts)",
            "level": round(closes[-1], 2),
            "detail": f"Single candle move of {round(move,0)} points",
            "action": "High velocity — watch for reversal at next support/resistance"
        }
    return None

# ─── Candlestick Patterns ───────────────────────────────────────────────────
def check_hammer(candles_list):
    if not candles_list:
        return None
    c = candles_list[-1]
    body = abs(c.close - c.open)
    if body == 0:
        return None
    lower_wick = min(c.open, c.close) - c.low
    upper_wick = c.high - max(c.open, c.close)
    if lower_wick >= 2 * body and upper_wick <= body * 0.5:
        return {
            "pattern": "Hammer 🟢",
            "level": round(c.close, 2),
            "detail": f"Long lower wick ({round(lower_wick,1)} pts), small body ({round(body,1)} pts)",
            "action": "Bullish reversal signal — evaluate CE"
        }
    if upper_wick >= 2 * body and lower_wick <= body * 0.5:
        return {
            "pattern": "Shooting Star 🔴",
            "level": round(c.close, 2),
            "detail": f"Long upper wick ({round(upper_wick,1)} pts), small body ({round(body,1)} pts)",
            "action": "Bearish reversal signal — evaluate PE"
        }
    return None

def check_engulfing(candles_list):
    if len(candles_list) < 2:
        return None
    prev = candles_list[-2]
    curr = candles_list[-1]
    prev_body = abs(prev.close - prev.open)
    curr_body = abs(curr.close - curr.open)
    if prev_body == 0 or curr_body == 0:
        return None
    # Bullish engulfing
    if (prev.close < prev.open and curr.close > curr.open and
            curr.open <= prev.close and curr.close >= prev.open and
            curr_body > prev_body):
        return {
            "pattern": "Bullish Engulfing 🟢🟢",
            "level": round(curr.close, 2),
            "detail": f"Green candle engulfs previous red — {round(curr_body,1)} pt body",
            "action": "Strong bullish reversal — evaluate CE"
        }
    # Bearish engulfing
    if (prev.close > prev.open and curr.close < curr.open and
            curr.open >= prev.close and curr.close <= prev.open and
            curr_body > prev_body):
        return {
            "pattern": "Bearish Engulfing 🔴🔴",
            "level": round(curr.close, 2),
            "detail": f"Red candle engulfs previous green — {round(curr_body,1)} pt body",
            "action": "Strong bearish reversal — evaluate PE"
        }
    return None

def check_doji(candles_list):
    if not candles_list:
        return None
    c = candles_list[-1]
    body = abs(c.close - c.open)
    total_range = c.high - c.low
    if total_range > 0 and body / total_range <= 0.1:
        return {
            "pattern": "Doji ⚠️",
            "level": round(c.close, 2),
            "detail": f"Indecision candle — body only {round(body,1)} pts of {round(total_range,1)} range",
            "action": "Wait for next candle direction — do not trade yet"
        }
    return None

def check_morning_evening_star(candles_list):
    """3-candle reversal patterns"""
    if len(candles_list) < 3:
        return None
    c1, c2, c3 = candles_list[-3], candles_list[-2], candles_list[-1]
    # Morning Star: red, small body, green
    if (c1.close < c1.open and
            abs(c2.close - c2.open) < abs(c1.close - c1.open) * 0.3 and
            c3.close > c3.open and c3.close > (c1.open + c1.close) / 2):
        return {
            "pattern": "Morning Star 🌟🟢",
            "level": round(c3.close, 2),
            "detail": "3-candle bullish reversal pattern",
            "action": "Strong bullish signal — evaluate CE"
        }
    # Evening Star: green, small body, red
    if (c1.close > c1.open and
            abs(c2.close - c2.open) < abs(c1.close - c1.open) * 0.3 and
            c3.close < c3.open and c3.close < (c1.open + c1.close) / 2):
        return {
            "pattern": "Evening Star 🌟🔴",
            "level": round(c3.close, 2),
            "detail": "3-candle bearish reversal pattern",
            "action": "Strong bearish signal — evaluate PE"
        }
    return None

# ─── Narrow Range Day Detection ─────────────────────────────────────────────
def check_narrow_range(highs, lows, vix):
    """Skip day signal: VIX < 14 + small range"""
    if len(highs) < 5 or len(lows) < 5:
        return None
    day_range = max(highs) - min(lows)
    if day_range < NARROW_RANGE_THRESHOLD and vix < NARROW_RANGE_VIX:
        return {
            "pattern": "Narrow Range Day ⛔",
            "level": 0,
            "detail": f"Range only {round(day_range,0)} pts | VIX {vix}",
            "action": "SKIP TRADING TODAY — insufficient range for meaningful R/R"
        }
    return None

# ─── MA Cross ───────────────────────────────────────────────────────────────
def check_ma_cross_intraday(closes, ema_20):
    """Alert when intraday price crosses 20 EMA"""
    if not ema_20 or len(closes) < 2:
        return None
    prev = closes[-2]
    curr = closes[-1]
    if prev < ema_20 <= curr:
        return {
            "pattern": "Price Crossed ABOVE 20 EMA 🟢",
            "level": round(curr, 2),
            "detail": f"20 EMA: {ema_20}",
            "action": "Bullish momentum — evaluate CE"
        }
    if prev > ema_20 >= curr:
        return {
            "pattern": "Price Crossed BELOW 20 EMA 🔴",
            "level": round(curr, 2),
            "detail": f"20 EMA: {ema_20}",
            "action": "Bearish momentum — evaluate PE"
        }
    return None

# ─── Weekly Bias Check ──────────────────────────────────────────────────────
def get_weekly_bias():
    """Mon/Wed = put writers (green). Tue/Thu = call writers (red). Fri = neutral"""
    day = datetime.now().weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
    bias_map = {
        0: ("PUT WRITERS DAY 🟢", "Monday — green bias. Buy dips. Double dip = CE entry."),
        1: ("CALL WRITERS DAY 🔴", "Tuesday — NIFTY EXPIRY. Red bias after 10:30 AM. Double top = PE entry."),
        2: ("PUT WRITERS DAY 🟢", "Wednesday — green bias. Buy dips. Double dip = CE entry."),
        3: ("CALL WRITERS DAY 🔴", "Thursday — SENSEX EXPIRY. Red bias after 10:30 AM. Double top = PE entry."),
        4: ("NEUTRAL ⚪", "Friday — no expiry. Trade only high conviction setups.")
    }
    return bias_map.get(day, ("UNKNOWN", ""))

# ─── Master detector ────────────────────────────────────────────────────────
def run_all_checks(max_pain=0, ema_20=None):
    if store.count() < 5:
        return []

    detected = []
    closes = store.get_closes()
    highs  = store.get_highs()
    lows   = store.get_lows()
    candles = list(store.candles)
    latest  = store.latest()

    checks = [
        check_double_top(highs),
        check_double_bottom(lows),
        check_triple_top(highs),
        check_triple_bottom(lows),
        check_stop_hunt(lows, closes, highs),
        check_max_pain_gap(latest.close, max_pain),
        check_key_levels(latest.close),
        check_velocity(closes),
        check_hammer(candles),
        check_engulfing(candles),
        check_doji(candles),
        check_morning_evening_star(candles),
        check_narrow_range(highs, lows, latest.vix),
        check_ma_cross_intraday(closes, ema_20) if ema_20 else None,
    ]

    for result in checks:
        if result:
            detected.append(result)

    return detected

# ma_calculator.py — Auto-compute MAs from NSE daily OHLC

from fetcher import fetch_nifty_daily_history

def compute_sma(closes, period):
    """Simple Moving Average"""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def compute_ema(closes, period):
    """Exponential Moving Average"""
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period  # Seed with SMA
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 2)

def get_all_mas():
    """Fetch history and compute all MAs"""
    closes = fetch_nifty_daily_history(days=250)
    if not closes:
        return None

    return {
        "ema_20":  compute_ema(closes, 20),
        "ema_50":  compute_ema(closes, 50),
        "sma_200": compute_sma(closes, 200),
        "last_close": closes[-1] if closes else 0,
        "data_points": len(closes)
    }

def interpret_mas(mas, current_price):
    """Generate bias from MA positions"""
    if not mas:
        return "MA data unavailable"

    signals = []
    if mas["ema_20"] and current_price > mas["ema_20"]:
        signals.append("✅ Above 20 EMA")
    elif mas["ema_20"]:
        signals.append("❌ Below 20 EMA")

    if mas["ema_50"] and current_price > mas["ema_50"]:
        signals.append("✅ Above 50 EMA")
    elif mas["ema_50"]:
        signals.append("❌ Below 50 EMA")

    if mas["sma_200"] and current_price > mas["sma_200"]:
        signals.append("✅ Above 200 SMA")
    elif mas["sma_200"]:
        signals.append("❌ Below 200 SMA")

    bullish = sum(1 for s in signals if "✅" in s)
    if bullish == 3:
        bias = "BULLISH — above all MAs"
    elif bullish == 2:
        bias = "MILDLY BULLISH"
    elif bullish == 1:
        bias = "MILDLY BEARISH"
    else:
        bias = "BEARISH — below all MAs"

    return {"signals": signals, "bias": bias}

def check_ma_cross(mas, current_price, prev_price):
    """Alert if price just crossed a key MA"""
    if not mas:
        return None
    crosses = []
    for label, ma_val in [("20 EMA", mas["ema_20"]),
                           ("50 EMA", mas["ema_50"]),
                           ("200 SMA", mas["sma_200"])]:
        if not ma_val:
            continue
        if prev_price < ma_val <= current_price:
            crosses.append(f"🟢 Price crossed ABOVE {label} at {ma_val}")
        elif prev_price > ma_val >= current_price:
            crosses.append(f"🔴 Price crossed BELOW {label} at {ma_val}")
    return crosses if crosses else None

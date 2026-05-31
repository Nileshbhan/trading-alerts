# fetcher.py — NSE PRIMARY, Moneycontrol secondary, Yahoo backup

import requests
import json
import time
from datetime import datetime, timedelta
from store import Candle

# ─── NSE Session ────────────────────────────────────────────────────────────
nse_session = requests.Session()
nse_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive"
})

_nse_session_init = False

def init_nse_session():
    global _nse_session_init
    try:
        r = nse_session.get("https://www.nseindia.com", timeout=15)
        if r.status_code == 200:
            _nse_session_init = True
            print("✅ NSE session initialised")
            return True
    except Exception as e:
        print(f"NSE session init failed: {e}")
    return False

def ensure_nse_session():
    global _nse_session_init
    if not _nse_session_init:
        init_nse_session()

# ─── Nifty Intraday OHLC (5-min candles) ───────────────────────────────────
def fetch_nifty_intraday():
    """Fetch today's 5-min OHLC from NSE"""
    ensure_nse_session()
    try:
        url = "https://www.nseindia.com/api/chart-databyindex?index=NIFTY%2050"
        r = nse_session.get(url, timeout=10)
        data = r.json()
        candles_raw = data.get("grapthData", [])
        if not candles_raw:
            return []
        candles = []
        for c in candles_raw:
            # NSE format: [epoch_ms, open, high, low, close]
            candles.append(Candle(
                timestamp=datetime.fromtimestamp(c[0]/1000),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4])
            ))
        return candles
    except Exception as e:
        print(f"NSE intraday fetch failed: {e}")
        return []

def fetch_nifty_latest_candle():
    """Get most recent 5-min candle"""
    candles = fetch_nifty_intraday()
    if candles:
        return candles[-1]
    return fetch_nifty_yahoo_latest()

# ─── Nifty Daily OHLC (for MA computation) ─────────────────────────────────
def fetch_nifty_daily_history(days=250):
    """Fetch daily OHLC history from NSE for MA computation"""
    ensure_nse_session()
    try:
        end = datetime.now()
        start = end - timedelta(days=days + 50)  # Buffer for weekends/holidays
        url = (
            f"https://www.nseindia.com/api/historical/cm/equity?"
            f"symbol=NIFTY%2050&series=EQ&"
            f"from={start.strftime('%d-%m-%Y')}&to={end.strftime('%d-%m-%Y')}"
        )
        r = nse_session.get(url, timeout=15)
        data = r.json()
        records = data.get("data", [])
        closes = []
        for rec in sorted(records, key=lambda x: x.get("CH_TIMESTAMP", "")):
            try:
                closes.append(float(rec.get("CH_CLOSING_PRICE", 0)))
            except:
                pass
        return closes[-days:] if len(closes) >= days else closes
    except Exception as e:
        print(f"NSE daily history fetch failed: {e}")
        return []

# ─── VIX ────────────────────────────────────────────────────────────────────
def fetch_vix():
    ensure_nse_session()
    try:
        url = "https://www.nseindia.com/api/allIndices"
        r = nse_session.get(url, timeout=10)
        data = r.json()
        for item in data.get("data", []):
            if item.get("index") == "INDIA VIX":
                return float(item.get("last", 0))
    except Exception as e:
        print(f"VIX fetch failed: {e}")
    return 0.0

# ─── PCR & Max Pain from NSE Option Chain ───────────────────────────────────
def fetch_option_chain_data():
    """Returns pcr, max_pain, call_oi_walls, put_oi_walls"""
    ensure_nse_session()
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        r = nse_session.get(url, timeout=15)
        data = r.json()

        filtered = data.get("filtered", {})
        pe_oi = filtered.get("PE", {}).get("totOI", 0)
        ce_oi = filtered.get("CE", {}).get("totOI", 0)
        pcr = round(pe_oi / ce_oi, 2) if ce_oi > 0 else 0.0

        # Max pain calculation
        records = data.get("records", {}).get("data", [])
        strikes = {}
        for rec in records:
            strike = rec.get("strikePrice", 0)
            ce_oi_s = rec.get("CE", {}).get("openInterest", 0) if rec.get("CE") else 0
            pe_oi_s = rec.get("PE", {}).get("openInterest", 0) if rec.get("PE") else 0
            strikes[strike] = {"ce": ce_oi_s, "pe": pe_oi_s}

        # Max pain = strike where total option pain is minimum
        min_pain = float('inf')
        max_pain_strike = 0
        strike_list = sorted(strikes.keys())
        for test_strike in strike_list:
            pain = 0
            for s, oi in strikes.items():
                if s < test_strike:
                    pain += oi["ce"] * (test_strike - s)
                elif s > test_strike:
                    pain += oi["pe"] * (s - test_strike)
            if pain < min_pain:
                min_pain = pain
                max_pain_strike = test_strike

        # OI walls — top 3 CE and PE strikes by OI
        ce_walls = sorted(strikes.items(), key=lambda x: x[1]["ce"], reverse=True)[:3]
        pe_walls = sorted(strikes.items(), key=lambda x: x[1]["pe"], reverse=True)[:3]

        return {
            "pcr": pcr,
            "max_pain": max_pain_strike,
            "ce_walls": [s for s, _ in ce_walls],
            "pe_walls": [s for s, _ in pe_walls]
        }
    except Exception as e:
        print(f"Option chain fetch failed: {e}")
        return {"pcr": 0.0, "max_pain": 0, "ce_walls": [], "pe_walls": []}

# ─── GIFT Nifty ─────────────────────────────────────────────────────────────
def fetch_gift_nifty():
    try:
        url = "https://www.nseindia.com/api/allIndices"
        r = nse_session.get(url, timeout=10)
        data = r.json()
        for item in data.get("data", []):
            if "GIFT" in item.get("index", "").upper():
                return float(item.get("last", 0))
    except:
        pass
    # Fallback: try investing.com
    return 0.0

# ─── Brent/WTI Crude (Moneycontrol secondary) ───────────────────────────────
def fetch_crude():
    """Fetch Brent and WTI from Moneycontrol"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # Brent
        r = requests.get(
            "https://priceapi.moneycontrol.com/pricefeed/commodity/crude-oil-brent",
            headers=headers, timeout=10
        )
        brent_data = r.json()
        brent = float(brent_data.get("data", {}).get("pricecurrent", 0))

        # WTI
        r2 = requests.get(
            "https://priceapi.moneycontrol.com/pricefeed/commodity/crude-oil",
            headers=headers, timeout=10
        )
        wti_data = r2.json()
        wti = float(wti_data.get("data", {}).get("pricecurrent", 0))

        return {"brent": brent, "wti": wti, "timestamp": datetime.now().strftime("%H:%M")}
    except Exception as e:
        print(f"Crude fetch failed: {e}")
        return {"brent": 0.0, "wti": 0.0, "timestamp": "N/A"}

# ─── FII F&O Data (Moneycontrol secondary) ──────────────────────────────────
def fetch_fii_data():
    """Fetch FII cash + F&O from Moneycontrol"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://priceapi.moneycontrol.com/pricefeed/notional/derivative/fii-dii-data"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        fii = data.get("data", {})
        return {
            "fii_cash": fii.get("fii_cash_net", "N/A"),
            "dii_cash": fii.get("dii_cash_net", "N/A"),
            "fii_index_fut": fii.get("fii_index_futures_net", "N/A"),
            "fii_index_opt": fii.get("fii_index_options_net", "N/A"),
            "timestamp": datetime.now().strftime("%H:%M")
        }
    except Exception as e:
        print(f"FII fetch failed: {e}")
        return {
            "fii_cash": "N/A", "dii_cash": "N/A",
            "fii_index_fut": "N/A", "fii_index_opt": "N/A",
            "timestamp": "N/A"
        }

# ─── Global/Asian Futures (Moneycontrol secondary) ──────────────────────────
def fetch_global_markets():
    """Fetch Dow, S&P, Nasdaq, Nikkei, Hang Seng, Shanghai, DAX, FTSE"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://priceapi.moneycontrol.com/pricefeed/notional/globalindices"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        markets = {}
        for item in data.get("data", []):
            name = item.get("index_name", "")
            last = item.get("last", 0)
            chg_pct = item.get("per_change", 0)
            markets[name] = {"last": last, "chg_pct": chg_pct}
        return markets
    except Exception as e:
        print(f"Global markets fetch failed: {e}")
        return {}

# ─── Rupee/Dollar ────────────────────────────────────────────────────────────
def fetch_rupee():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://priceapi.moneycontrol.com/pricefeed/currency/usdinr"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        return float(data.get("data", {}).get("pricecurrent", 0))
    except:
        return 0.0

# ─── Yahoo Finance Backup ────────────────────────────────────────────────────
def fetch_nifty_yahoo_latest():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=5m&range=1d"
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        result = data["chart"]["result"][0]
        quotes = result["indicators"]["quote"][0]
        timestamps = result["timestamp"]
        idx = -1
        return Candle(
            timestamp=datetime.fromtimestamp(timestamps[idx]),
            open=float(quotes["open"][idx] or 0),
            high=float(quotes["high"][idx] or 0),
            low=float(quotes["low"][idx] or 0),
            close=float(quotes["close"][idx] or 0)
        )
    except Exception as e:
        print(f"Yahoo backup failed: {e}")
        return None

# ─── Master fetch ────────────────────────────────────────────────────────────
def fetch_all():
    """Fetch everything needed for one cycle"""
    candle = fetch_nifty_latest_candle()
    oc_data = fetch_option_chain_data()
    crude = fetch_crude()
    fii = fetch_fii_data()
    global_mkts = fetch_global_markets()

    if candle:
        candle.vix = fetch_vix()
        candle.pcr = oc_data.get("pcr", 0.0)

    return {
        "candle": candle,
        "oc_data": oc_data,
        "crude": crude,
        "fii": fii,
        "global_markets": global_mkts,
        "rupee": fetch_rupee(),
        "gift_nifty": fetch_gift_nifty(),
        "fetched_at": datetime.now().strftime("%H:%M:%S")
    }

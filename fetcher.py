# fetcher.py — NSE PRIMARY, Moneycontrol secondary, Yahoo backup
# FIXED: Updated Moneycontrol API endpoints for crude, rupee, FII, global markets
 
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
    candles = fetch_nifty_intraday()
    if candles:
        return candles[-1]
    return fetch_nifty_yahoo_latest()
 
# ─── Nifty Daily OHLC (for MA computation) ─────────────────────────────────
def fetch_nifty_daily_history(days=250):
    ensure_nse_session()
    try:
        end = datetime.now()
        start = end - timedelta(days=days + 50)
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
    ensure_nse_session()
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        r = nse_session.get(url, timeout=15)
        data = r.json()
 
        filtered = data.get("filtered", {})
        pe_oi = filtered.get("PE", {}).get("totOI", 0)
        ce_oi = filtered.get("CE", {}).get("totOI", 0)
        pcr = round(pe_oi / ce_oi, 2) if ce_oi > 0 else 0.0
 
        records = data.get("records", {}).get("data", [])
        strikes = {}
        for rec in records:
            strike = rec.get("strikePrice", 0)
            ce_oi_s = rec.get("CE", {}).get("openInterest", 0) if rec.get("CE") else 0
            pe_oi_s = rec.get("PE", {}).get("openInterest", 0) if rec.get("PE") else 0
            strikes[strike] = {"ce": ce_oi_s, "pe": pe_oi_s}
 
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
    return 0.0
 
# ─── Brent/WTI Crude — FIXED ENDPOINTS ──────────────────────────────────────
def fetch_crude():
    """
    PRIMARY: Yahoo Finance (most reliable, free, no auth needed)
    FALLBACK: Investing.com
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
 
        # Brent via Yahoo Finance
        brent_url = "https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF?interval=5m&range=1d"
        r1 = requests.get(brent_url, headers=headers, timeout=10)
        brent_data = r1.json()
        brent_quotes = brent_data["chart"]["result"][0]["indicators"]["quote"][0]
        brent_closes = [x for x in brent_quotes["close"] if x is not None]
        brent = round(brent_closes[-1], 2) if brent_closes else 0.0
 
        # WTI via Yahoo Finance
        wti_url = "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF?interval=5m&range=1d"
        r2 = requests.get(wti_url, headers=headers, timeout=10)
        wti_data = r2.json()
        wti_quotes = wti_data["chart"]["result"][0]["indicators"]["quote"][0]
        wti_closes = [x for x in wti_quotes["close"] if x is not None]
        wti = round(wti_closes[-1], 2) if wti_closes else 0.0
 
        return {"brent": brent, "wti": wti, "timestamp": datetime.now().strftime("%H:%M")}
 
    except Exception as e:
        print(f"Crude fetch failed: {e}")
        return {"brent": 0.0, "wti": 0.0, "timestamp": "N/A"}
 
# ─── FII F&O Data — FIXED ENDPOINTS ─────────────────────────────────────────
def fetch_fii_data():
    """
    PRIMARY: NSE participant-wise OI data
    FALLBACK: Return N/A gracefully
    """
    try:
        ensure_nse_session()
        url = "https://www.nseindia.com/api/fii-stats"
        r = nse_session.get(url, timeout=10)
        data = r.json()
        fii = data.get("data", [{}])[0] if data.get("data") else {}
        return {
            "fii_cash": fii.get("netAmount", "N/A"),
            "dii_cash": fii.get("diiNetAmount", "N/A"),
            "fii_index_fut": fii.get("indexFutNet", "N/A"),
            "fii_index_opt": fii.get("indexOptNet", "N/A"),
            "timestamp": datetime.now().strftime("%H:%M")
        }
    except Exception as e:
        print(f"FII NSE fetch failed: {e}")
        # Fallback — try Moneycontrol
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
            r = requests.get(url, headers=headers, timeout=10)
            # Return N/A if Moneycontrol also fails
            return {
                "fii_cash": "N/A", "dii_cash": "N/A",
                "fii_index_fut": "N/A", "fii_index_opt": "N/A",
                "timestamp": "N/A"
            }
        except:
            return {
                "fii_cash": "N/A", "dii_cash": "N/A",
                "fii_index_fut": "N/A", "fii_index_opt": "N/A",
                "timestamp": "N/A"
            }
 
# ─── Global Markets — FIXED ENDPOINTS ───────────────────────────────────────
def fetch_global_markets():
    """
    PRIMARY: Yahoo Finance for major indices
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        symbols = {
            "Dow Jones": "%5EDJI",
            "S&P 500":   "%5EGSPC",
            "Nasdaq":    "%5EIXIC",
            "Nikkei":    "%5EN225",
            "Hang Seng": "%5EHSI",
            "DAX":       "%5EGDAXI",
            "FTSE":      "%5EFTSE"
        }
        markets = {}
        for name, symbol in symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                r = requests.get(url, headers=headers, timeout=8)
                data = r.json()
                result = data["chart"]["result"][0]
                closes = result["indicators"]["quote"][0]["close"]
                closes = [x for x in closes if x is not None]
                if len(closes) >= 2:
                    last = round(closes[-1], 2)
                    prev = round(closes[-2], 2)
                    chg_pct = round(((last - prev) / prev) * 100, 2)
                    markets[name] = {"last": last, "chg_pct": chg_pct}
            except:
                continue
        return markets
    except Exception as e:
        print(f"Global markets fetch failed: {e}")
        return {}
 
# ─── Rupee/Dollar — FIXED ENDPOINT ──────────────────────────────────────────
def fetch_rupee():
    """PRIMARY: Yahoo Finance USDINR"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDINR%3DX?interval=5m&range=1d"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        quotes = data["chart"]["result"][0]["indicators"]["quote"][0]
        closes = [x for x in quotes["close"] if x is not None]
        return round(closes[-1], 2) if closes else 0.0
    except Exception as e:
        print(f"Rupee fetch failed: {e}")
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
 

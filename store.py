# store.py — Rolling price history + state management

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    vix: float = 0.0
    pcr: float = 0.0

class PriceStore:
    def __init__(self, maxlen=150):
        self.candles = deque(maxlen=maxlen)  # ~5 hours of 2-min candles
        self._alert_log = {}   # pattern_name → last_alert_time
        self.consecutive_stops = 0
        self.daily_pnl_pts = 0
        self.last_oc_data = {}
        self.last_mas = {}

    def add(self, candle: Candle):
        self.candles.append(candle)

    def get_closes(self):
        return [c.close for c in self.candles]

    def get_highs(self):
        return [c.high for c in self.candles]

    def get_lows(self):
        return [c.low for c in self.candles]

    def get_day_range(self):
        if not self.candles:
            return 0
        return max(self.get_highs()) - min(self.get_lows())

    def latest(self) -> Optional[Candle]:
        return self.candles[-1] if self.candles else None

    def count(self):
        return len(self.candles)

    def can_alert(self, pattern_name, cooldown_mins=15):
        if pattern_name not in self._alert_log:
            return True
        elapsed = (datetime.now() - self._alert_log[pattern_name]).seconds / 60
        return elapsed >= cooldown_mins

    def mark_alerted(self, pattern_name):
        self._alert_log[pattern_name] = datetime.now()

    def reset_daily(self):
        """Call at market open each day"""
        self.candles.clear()
        self._alert_log.clear()
        self.consecutive_stops = 0
        self.daily_pnl_pts = 0

# Global singleton
store = PriceStore()

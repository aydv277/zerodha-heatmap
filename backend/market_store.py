"""
In-memory market data store.
Receives ticks from Kite WebSocket, computes % changes across timeframes,
and serves the latest state to the API / frontend WebSocket.
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

from config import ALL_GROUPS

# ── Price history ──────────────────────────────────────────────────────────
# symbol → deque of { "ts": epoch, "ltp": float }
MAX_HISTORY = 6_000

_lock = threading.Lock()
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

# symbol → latest full tick dict from Kite (has ohlc, ltp, volume, etc.)
_latest_tick: dict[str, dict] = {}

# instrument_token → symbol mapping (built at login)
_token_map: dict[int, str] = {}

# All instrument tokens we're subscribed to
_subscribed_tokens: list[int] = []

# Historical candle data: symbol → { "day": [...], "5minute": [...] }
_historical: dict[str, dict] = defaultdict(dict)


def set_token_map(mapping: dict[int, str], tokens: list[int]):
    global _token_map, _subscribed_tokens
    with _lock:
        _token_map = mapping
        _subscribed_tokens = tokens


def get_token_map() -> dict[int, str]:
    return _token_map


def get_subscribed_tokens() -> list[int]:
    return _subscribed_tokens


def seed_quote(symbol: str, tick_data: dict):
    """Seed the store with quote data fetched via REST API."""
    with _lock:
        _latest_tick[symbol] = tick_data
        ltp = tick_data.get("last_price", 0)
        if ltp:
            _history[symbol].append({"ts": time.time(), "ltp": ltp})


def seed_historical(symbol: str, candles: list, interval: str):
    """Store historical candle data for computing multi-timeframe changes."""
    with _lock:
        _historical[symbol][interval] = candles


def on_tick(tick: dict):
    """Called from KiteTicker on_ticks callback for each tick."""
    token = tick.get("instrument_token")
    symbol = _token_map.get(token)
    if not symbol:
        return
    ltp = tick.get("last_price", 0)
    now = time.time()
    with _lock:
        _latest_tick[symbol] = tick
        _history[symbol].append({"ts": now, "ltp": ltp})


def _price_at(symbol: str, seconds_ago: int) -> float | None:
    """Return the LTP closest to seconds_ago seconds in the past."""
    hist = _history.get(symbol)
    if not hist:
        return None
    target = time.time() - seconds_ago
    best = None
    best_diff = float("inf")
    for entry in reversed(hist):
        diff = abs(entry["ts"] - target)
        if diff < best_diff:
            best_diff = diff
            best = entry["ltp"]
        if entry["ts"] < target - 60:
            break
    return best


TIMEFRAME_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


def _compute_changes(symbol: str) -> dict[str, float]:
    """Compute % change for each timeframe using live ticks or historical data."""
    tick = _latest_tick.get(symbol)
    if not tick:
        return {tf: 0.0 for tf in TIMEFRAME_SECONDS}
    ltp = tick.get("last_price", 0)
    if ltp == 0:
        return {tf: 0.0 for tf in TIMEFRAME_SECONDS}

    changes = {}
    hist_data = _historical.get(symbol, {})
    daily_candles = hist_data.get("day", [])
    minute_candles = hist_data.get("5minute", [])

    for tf, secs in TIMEFRAME_SECONDS.items():
        old_price = _price_at(symbol, secs)
        if old_price and old_price != 0:
            changes[tf] = round(((ltp - old_price) / old_price) * 100, 4)
            continue
        ref_price = _get_historical_ref_price(tf, ltp, tick, daily_candles, minute_candles)
        if ref_price and ref_price != 0:
            changes[tf] = round(((ltp - ref_price) / ref_price) * 100, 4)
        else:
            changes[tf] = 0.0
    return changes


def _get_historical_ref_price(tf: str, ltp: float, tick: dict,
                               daily_candles: list, minute_candles: list) -> float | None:
    """Get the reference (old) price for a timeframe from historical data."""
    ohlc = tick.get("ohlc", {})
    if tf == "1d":
        if len(daily_candles) >= 2:
            return daily_candles[-2].get("close", 0)
        prev_close = ohlc.get("close", 0)
        if prev_close:
            return prev_close
        return ohlc.get("open", 0)
    elif tf == "1w":
        if len(daily_candles) >= 6:
            return daily_candles[-6].get("close", 0)
        elif len(daily_candles) >= 2:
            return daily_candles[0].get("close", 0)
        return None
    elif tf == "4h":
        if len(minute_candles) >= 48:
            return minute_candles[-48].get("close", 0)
        return None
    elif tf == "1h":
        if len(minute_candles) >= 12:
            return minute_candles[-12].get("close", 0)
        return None
    elif tf == "15m":
        if len(minute_candles) >= 3:
            return minute_candles[-3].get("close", 0)
        return None
    elif tf == "5m":
        if len(minute_candles) >= 1:
            return minute_candles[-1].get("close", 0)
        return None
    return None


def build_stock_entry(symbol: str) -> dict[str, Any]:
    tick = _latest_tick.get(symbol, {})
    ohlc = tick.get("ohlc", {})
    return {
        "symbol": symbol,
        "name": symbol,
        "ltp": tick.get("last_price", 0),
        "open": ohlc.get("open", 0),
        "high": ohlc.get("high", 0),
        "low": ohlc.get("low", 0),
        "volume": tick.get("volume_traded", 0),
        "changes": _compute_changes(symbol),
    }


# ── Instrument name enrichment ────────────────────────────────────────────
_instrument_names: dict[str, str] = {}


def set_instrument_names(names: dict[str, str]):
    global _instrument_names
    _instrument_names = names


def get_snapshot() -> dict:
    """Build the full API response payload."""
    groups = {}
    with _lock:
        for group_key, symbols in ALL_GROUPS.items():
            entries = []
            for sym in symbols:
                entry = build_stock_entry(sym)
                entry["name"] = _instrument_names.get(sym, sym)
                entries.append(entry)
            groups[group_key] = entries
    return {
        "connected": len(_latest_tick) > 0,
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "tickCount": len(_latest_tick),
        "groups": groups,
    }
"""
In-memory market data store.
Receives ticks from Kite WebSocket, computes % changes across timeframes,
and serves the latest state to the API / frontend WebSocket.
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

from config import ALL_GROUPS

# ── Price history ──────────────────────────────────────────────────────────
# symbol → deque of { "ts": epoch, "ltp": float }
# We keep ~8 hours of ticks (sampled every 5 s ≈ 5 760 entries max)
MAX_HISTORY = 6_000

_lock = threading.Lock()
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

# symbol → latest full tick dict from Kite (has ohlc, ltp, volume, etc.)
_latest_tick: dict[str, dict] = {}

# instrument_token → symbol mapping (built at login)
_token_map: dict[int, str] = {}

# All instrument tokens we're subscribed to
_subscribed_tokens: list[int] = []


def set_token_map(mapping: dict[int, str], tokens: list[int]):
    global _token_map, _subscribed_tokens
    with _lock:
        _token_map = mapping
        _subscribed_tokens = tokens


def get_subscribed_tokens() -> list[int]:
    return _subscribed_tokens


def on_tick(tick: dict):
    """Called from KiteTicker on_ticks callback for each tick."""
    token = tick.get("instrument_token")
    symbol = _token_map.get(token)
    if not symbol:
        return
    ltp = tick.get("last_price", 0)
    now = time.time()
    with _lock:
        _latest_tick[symbol] = tick
        _history[symbol].append({"ts": now, "ltp": ltp})


def _price_at(symbol: str, seconds_ago: int) -> float | None:
    """Return the LTP closest to `seconds_ago` seconds in the past."""
    hist = _history.get(symbol)
    if not hist:
        return None
    target = time.time() - seconds_ago
    best = None
    best_diff = float("inf")
    # Iterate backwards (most recent first) for speed
    for entry in reversed(hist):
        diff = abs(entry["ts"] - target)
        if diff < best_diff:
            best_diff = diff
            best = entry["ltp"]
        # Once we're past the target going backwards, we can stop
        if entry["ts"] < target - 60:
            break
    return best


TIMEFRAME_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


def _compute_changes(symbol: str) -> dict[str, float]:
    """Compute % change for each timeframe."""
    tick = _latest_tick.get(symbol)
    if not tick:
        return {tf: 0.0 for tf in TIMEFRAME_SECONDS}
    ltp = tick.get("last_price", 0)
    if ltp == 0:
        return {tf: 0.0 for tf in TIMEFRAME_SECONDS}

    changes = {}
    for tf, secs in TIMEFRAME_SECONDS.items():
        old_price = _price_at(symbol, secs)
        if old_price and old_price != 0:
            changes[tf] = round(((ltp - old_price) / old_price) * 100, 4)
        else:
            # Fallback: use OHLC day open for 1d, otherwise 0
            ohlc = tick.get("ohlc", {})
            day_open = ohlc.get("open", 0)
            if tf == "1d" and day_open and day_open != 0:
                changes[tf] = round(((ltp - day_open) / day_open) * 100, 4)
            else:
                changes[tf] = 0.0
    return changes


def build_stock_entry(symbol: str) -> dict[str, Any]:
    tick = _latest_tick.get(symbol, {})
    ohlc = tick.get("ohlc", {})
    return {
        "symbol": symbol,
        "name": symbol,  # Will be enriched with full name from instruments
        "ltp": tick.get("last_price", 0),
        "open": ohlc.get("open", 0),
        "high": ohlc.get("high", 0),
        "low": ohlc.get("low", 0),
        "volume": tick.get("volume_traded", 0),
        "changes": _compute_changes(symbol),
    }


# ── Instrument name enrichment ────────────────────────────────────────────
_instrument_names: dict[str, str] = {}


def set_instrument_names(names: dict[str, str]):
    global _instrument_names
    _instrument_names = names


def get_snapshot() -> dict:
    """Build the full API response payload."""
    groups = {}
    with _lock:
        for group_key, symbols in ALL_GROUPS.items():
            entries = []
            for sym in symbols:
                entry = build_stock_entry(sym)
                entry["name"] = _instrument_names.get(sym, sym)
                entries.append(entry)
            groups[group_key] = entries

    return {
        "connected": len(_latest_tick) > 0,
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "tickCount": len(_latest_tick),
        "groups": groups,
    }

"""
Manages the Kite Connect session: login, token resolution, and WebSocket ticker.
"""

import logging
import threading
from datetime import datetime, timedelta, date
from kiteconnect import KiteConnect, KiteTicker

from config import KITE_API_KEY, KITE_API_SECRET, ALL_GROUPS
import market_store

log = logging.getLogger("kite_manager")

# ── Singleton state ────────────────────────────────────────────────────────
kite: KiteConnect = KiteConnect(api_key=KITE_API_KEY)
ticker: KiteTicker | None = None
access_token: str | None = None
_ticker_thread: threading.Thread | None = None


def get_login_url() -> str:
    return kite.login_url()


def complete_login(request_token: str) -> dict:
    """Exchange request_token for access_token, resolve instruments, start ticker."""
    global access_token, ticker

    data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    log.info("Login successful. Access token set.")

    # Resolve symbols → instrument tokens
    _resolve_instruments()

    # Fetch initial quote data (works even when market is closed)
    _fetch_initial_quotes()

    # Fetch historical candles for multi-timeframe % changes
    _fetch_historical_data()

    # Start WebSocket ticker
    _start_ticker()

    return {"status": "ok", "user": data.get("user_name", "")}


def _fetch_initial_quotes():
    """Fetch current quotes for all symbols to populate LTP and OHLC data
    even when the market is closed."""
    try:
        all_symbols = set()
        for syms in ALL_GROUPS.values():
            all_symbols.update(syms)
        sym_list = [f"NSE:{s}" for s in all_symbols]
        for i in range(0, len(sym_list), 250):
            batch = sym_list[i:i + 250]
            quotes = kite.quote(batch)
            for key, q in quotes.items():
                symbol = key.replace("NSE:", "")
                tick_data = {
                    "instrument_token": q.get("instrument_token", 0),
                    "last_price": q.get("last_price", 0),
                    "ohlc": q.get("ohlc", {}),
                    "volume_traded": q.get("volume", 0),
                    "change": q.get("net_change", 0),
                }
                market_store.seed_quote(symbol, tick_data)
            log.info(f"Fetched quotes batch {i // 250 + 1}: {len(quotes)} instruments")
    except Exception as e:
        log.error(f"Failed to fetch initial quotes: {e}")


def _fetch_historical_data():
    """Fetch historical candles for multi-timeframe % changes."""
    try:
        token_map = market_store.get_token_map()
        if not token_map:
            log.warning("No token map available for historical data fetch")
            return
        today = date.today()
        from_date = today - timedelta(days=10)
        count = 0
        for tok, symbol in token_map.items():
            try:
                daily_data = kite.historical_data(
                    instrument_token=tok, from_date=from_date,
                    to_date=today, interval="day")
                if daily_data:
                    market_store.seed_historical(symbol, daily_data, "day")
                    count += 1
                intra_from = today - timedelta(days=2)
                intra_data = kite.historical_data(
                    instrument_token=tok, from_date=intra_from,
                    to_date=today, interval="5minute")
                if intra_data:
                    market_store.seed_historical(symbol, intra_data, "5minute")
            except Exception as e:
                log.debug(f"Historical data error for {symbol}: {e}")
                continue
        log.info(f"Fetched historical data for {count} instruments")
    except Exception as e:
        log.error(f"Failed to fetch historical data: {e}")


def _resolve_instruments():
    """Fetch NSE instruments and map trading symbols → instrument tokens."""
    instruments = kite.instruments("NSE")
    all_symbols = set()
    for syms in ALL_GROUPS.values():
        all_symbols.update(syms)
    token_map: dict[int, str] = {}
    names: dict[str, str] = {}
    tokens: list[int] = []
    for inst in instruments:
        tsym = inst["tradingsymbol"]
        if tsym in all_symbols:
            tok = inst["instrument_token"]
            token_map[tok] = tsym
            names[tsym] = inst.get("name", tsym)
            tokens.append(tok)
    market_store.set_token_map(token_map, tokens)
    market_store.set_instrument_names(names)
    log.info(f"Resolved {len(tokens)} instruments out of {len(all_symbols)} requested.")


def _start_ticker():
    """Start KiteTicker in a background thread."""
    global ticker, _ticker_thread
    if ticker:
        try:
            ticker.close()
        except Exception:
            pass
    ticker = KiteTicker(KITE_API_KEY, access_token)
    def on_ticks(ws, ticks):
        for t in ticks:
            market_store.on_tick(t)
    def on_connect(ws, response):
        tokens = market_store.get_subscribed_tokens()
        if tokens:
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
            log.info(f"Subscribed to {len(tokens)} tokens in FULL mode.")
    def on_close(ws, code, reason):
        log.warning(f"Ticker closed: {code} — {reason}")
    def on_error(ws, code, reason):
        log.error(f"Ticker error: {code} — {reason}")
    ticker.on_ticks = on_ticks
    ticker.on_connect = on_connect
    ticker.on_close = on_close
    ticker.on_error = on_error
    _ticker_thread = threading.Thread(target=ticker.connect, kwargs={"threaded": True}, daemon=True)
    _ticker_thread.start()
    log.info("KiteTicker started in background thread.")


def is_connected() -> bool:
    return access_token is not None and ticker is not None

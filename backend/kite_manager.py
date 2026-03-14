"""
Manages the Kite Connect session: login, token resolution, and WebSocket ticker.
"""

import logging
import threading
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

    # Start WebSocket ticker
    _start_ticker()

    return {"status": "ok", "user": data.get("user_name", "")}


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
            # Subscribe in full mode to get OHLC + volume
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

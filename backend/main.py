"""
FastAPI backend for the Zerodha Market Heatmap.

Endpoints:
  GET  /auth/login          → Redirect to Kite login page
  GET  /auth/callback       → Kite OAuth callback (exchanges request_token)
  GET  /api/market/overview  → Full market snapshot (JSON)
  WS   /ws/market            → Real-time market data via WebSocket
"""

import asyncio
import json
import logging
import time

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_URL, REDIRECT_URL
import kite_manager
import market_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-18s  %(levelname)-7s  %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Zerodha Market Heatmap API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Hostinger / mobile access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static app/ folder at root (index.html)
APP_DIR = Path(__file__).parent.parent / "app"
if APP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static")


# ── Auth endpoints ─────────────────────────────────────────────────────────
@app.get("/auth/login")
async def auth_login():
    """Redirect user to Zerodha Kite login page."""
    url = kite_manager.get_login_url()
    return RedirectResponse(url)


@app.get("/auth/callback")
async def auth_callback(request_token: str = Query(...)):
    """
    Kite redirects here with ?request_token=xxx&action=login.
    We exchange it for an access token, start the ticker, then redirect to frontend.
    """
    try:
        result = kite_manager.complete_login(request_token)
        log.info(f"Auth complete for user: {result.get('user', 'unknown')}")
        return RedirectResponse(f"{FRONTEND_URL}?auth=success")
    except Exception as e:
        log.error(f"Auth failed: {e}")
        return RedirectResponse(f"{FRONTEND_URL}?auth=failed&error={str(e)}")


@app.get("/auth/status")
async def auth_status():
    """Check if the backend has an active Kite session."""
    return {"connected": kite_manager.is_connected()}


# ── Market data endpoints ──────────────────────────────────────────────────
@app.get("/api/market/overview")
async def market_overview():
    """Return full market snapshot for all groups."""
    return JSONResponse(content=market_store.get_snapshot())


# ── WebSocket for real-time push ───────────────────────────────────────────
_ws_clients: set[WebSocket] = set()


@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    log.info(f"WS client connected. Total: {len(_ws_clients)}")
    try:
        while True:
            # Push snapshot every 2 seconds
            snapshot = market_store.get_snapshot()
            await websocket.send_text(json.dumps(snapshot))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning(f"WS error: {e}")
    finally:
        _ws_clients.discard(websocket)
        log.info(f"WS client disconnected. Total: {len(_ws_clients)}")


# ── Health check ───────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "kite_connected": kite_manager.is_connected(),
        "tick_count": len(market_store._latest_tick),
        "timestamp": time.time(),
    }


# ── Serve app/index.html at root ───────────────────────────────────────────
@app.get("/")
async def serve_app():
    """Serve the single-page app."""
    index = Path(__file__).parent.parent / "app" / "index.html"
    if index.exists():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=index.read_text(), status_code=200)
    return JSONResponse(content={"error": "app/index.html not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# Zerodha Market Heatmap — Quickstart

## Prerequisites
- Python 3.10+
- Node.js 18+
- A Zerodha Kite Connect app (developers.kite.trade)

## 1. Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Runs on **http://localhost:8000**

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on **http://localhost:5173** (proxies API calls to backend)

## 3. Login Flow

1. Open **http://localhost:5173** — you'll see a "Login with Zerodha" button
2. Click it → redirects to Kite login page
3. After login, Kite redirects back to the backend callback
4. Backend exchanges the request token for an access token
5. Starts the WebSocket ticker for live data
6. Frontend redirects and starts streaming

## 4. Kite Connect Setup

Make sure your Kite Connect app has the redirect URL set to:
```
http://localhost:8000/auth/callback
```

## Architecture

```
Frontend (React + Vite)  ←—  WebSocket  —→  Backend (FastAPI)
                                                  ↕
                                          Kite Connect API
                                          Kite WebSocket
```

- Backend handles all Kite API communication (keys never reach the browser)
- WebSocket pushes market snapshots to the frontend every 2 seconds
- Falls back to REST polling if WebSocket disconnects
- Price history is stored in-memory for % change calculations across timeframes

import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/market`;
const API_URL = "/api/market/overview";
const AUTH_STATUS_URL = "/auth/status";

export function useMarketData() {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const [wsStatus, setWsStatus] = useState("disconnected"); // disconnected | connecting | connected
  const [authStatus, setAuthStatus] = useState("checking"); // checking | authenticated | unauthenticated
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const pollTimer = useRef(null);

  // Check auth status
  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch(AUTH_STATUS_URL);
      const json = await res.json();
      setAuthStatus(json.connected ? "authenticated" : "unauthenticated");
      return json.connected;
    } catch {
      setAuthStatus("unauthenticated");
      return false;
    }
  }, []);

  // Fetch snapshot via REST (fallback / initial load)
  const fetchSnapshot = useCallback(async () => {
    try {
      const res = await fetch(API_URL);
      if (!res.ok) throw new Error("fetch failed");
      const json = await res.json();
      setData(json);
      setConnected(json.connected);
    } catch {
      setConnected(false);
    }
  }, []);

  // Connect WebSocket
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setWsStatus("connecting");
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setWsStatus("connected");
      // Clear polling when WS is alive
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const json = JSON.parse(event.data);
        setData(json);
        setConnected(json.connected);
      } catch {}
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      wsRef.current = null;
      // Fallback to polling
      if (!pollTimer.current) {
        pollTimer.current = setInterval(fetchSnapshot, 5000);
      }
      // Try reconnect in 3s
      reconnectTimer.current = setTimeout(connectWs, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [fetchSnapshot]);

  // Initial setup
  useEffect(() => {
    checkAuth().then((authed) => {
      if (authed) {
        fetchSnapshot();
        connectWs();
      }
    });

    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (pollTimer.current) clearInterval(pollTimer.current);
    };
  }, [checkAuth, connectWs, fetchSnapshot]);

  const refresh = useCallback(() => {
    fetchSnapshot();
  }, [fetchSnapshot]);

  const login = useCallback(() => {
    window.location.href = "/auth/login";
  }, []);

  return { data, connected, wsStatus, authStatus, refresh, login, checkAuth };
}

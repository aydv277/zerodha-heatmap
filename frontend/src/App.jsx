import React, { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RefreshCw, TrendingUp, TrendingDown, Minus, Wifi, WifiOff,
  Search, LogIn, LayoutGrid, LayoutList, ArrowUpDown, Clock,
  BarChart3, Activity, ChevronDown,
} from "lucide-react";
import { cn } from "./lib/utils";
import { useMarketData } from "./lib/useMarketData";

// ── Constants ──────────────────────────────────────────────────────────────
const TIMEFRAMES = [
  { value: "5m", label: "5 Min", short: "5m" },
  { value: "15m", label: "15 Min", short: "15m" },
  { value: "1h", label: "1 Hour", short: "1h" },
  { value: "4h", label: "4 Hour", short: "4h" },
  { value: "1d", label: "1 Day", short: "1d" },
  { value: "1w", label: "1 Week", short: "1w" },
];

const GROUPS = [
  { key: "nifty20", label: "NIFTY 20", short: "N20" },
  { key: "nifty50", label: "NIFTY 50", short: "N50" },
  { key: "banking50", label: "Banking 50", short: "BNK" },
  { key: "midcap50", label: "Mid Cap 50", short: "MID" },
  { key: "smallcap50", label: "Small Cap 50", short: "SML" },
];

const SORT_OPTIONS = [
  { value: "change_desc", label: "Top Gainers" },
  { value: "change_asc", label: "Top Losers" },
  { value: "alpha", label: "A → Z" },
  { value: "volume", label: "Volume" },
];

// ── Heat coloring ──────────────────────────────────────────────────────────
function getHeatConfig(pct) {
  if (pct <= -3) return { bg: "bg-red-950", text: "text-red-100", border: "border-red-800", badge: "bg-red-900/80 text-red-100", label: "Major Bear" };
  if (pct <= -1.5) return { bg: "bg-red-800", text: "text-red-50", border: "border-red-600", badge: "bg-red-700/80 text-red-50", label: "Med Bear" };
  if (pct <= -0.4) return { bg: "bg-orange-50", text: "text-orange-900", border: "border-orange-200", badge: "bg-orange-200/80 text-orange-800", label: "Slight Bear" };
  if (pct < 0.4) return { bg: "bg-amber-50", text: "text-amber-900", border: "border-amber-200", badge: "bg-amber-200/80 text-amber-800", label: "Sideways" };
  if (pct < 1.5) return { bg: "bg-emerald-50", text: "text-emerald-900", border: "border-emerald-200", badge: "bg-emerald-200/80 text-emerald-800", label: "Slight Bull" };
  if (pct < 3) return { bg: "bg-emerald-500", text: "text-emerald-950", border: "border-emerald-600", badge: "bg-emerald-600/80 text-emerald-50", label: "Med Bull" };
  return { bg: "bg-emerald-800", text: "text-emerald-50", border: "border-emerald-900", badge: "bg-emerald-900/80 text-emerald-50", label: "Major Bull" };
}

function TrendIcon({ value, className }) {
  if (value > 0.05) return <TrendingUp className={cn("h-4 w-4 text-emerald-500", className)} />;
  if (value < -0.05) return <TrendingDown className={cn("h-4 w-4 text-red-500", className)} />;
  return <Minus className={cn("h-4 w-4 text-amber-500", className)} />;
}

function formatNum(n) {
  return Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatVol(n) {
  if (!n) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(2) + " L";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + " K";
  return n.toString();
}

// ── Components ─────────────────────────────────────────────────────────────

function LoginScreen({ onLogin }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md rounded-3xl bg-white p-8 shadow-lg text-center space-y-6"
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50">
          <BarChart3 className="h-8 w-8 text-blue-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Market Heatmap</h1>
          <p className="mt-2 text-sm text-slate-500">
            Connect your Zerodha account to stream live market data across NIFTY, Banking, Mid Cap, and Small Cap stocks.
          </p>
        </div>
        <button
          onClick={onLogin}
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-blue-700 active:scale-[0.98]"
        >
          <LogIn className="h-4 w-4" />
          Login with Zerodha
        </button>
        <p className="text-xs text-slate-400">
          Uses Kite Connect API. Your credentials never touch this app.
        </p>
      </motion.div>
    </div>
  );
}

function StatCard({ icon: Icon, title, value, sub, accent }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
      <div className="flex items-center gap-2">
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", accent)}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-xs font-medium text-slate-500">{title}</span>
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function StockCard({ stock, timeframe, view }) {
  const change = stock.changes?.[timeframe] ?? 0;
  const heat = getHeatConfig(change);

  if (view === "compact") {
    return (
      <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
        <div
          className={cn(
            "flex items-center justify-between rounded-xl border px-4 py-3 transition-all hover:shadow-sm",
            heat.bg, heat.text, heat.border
          )}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div className="font-semibold text-sm tracking-wide">{stock.symbol}</div>
            <div className="text-xs opacity-70 truncate hidden sm:block">{stock.name}</div>
          </div>
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="text-sm font-semibold">₹{formatNum(stock.ltp)}</div>
            <div className={cn("flex items-center gap-1 text-sm font-bold min-w-[80px] justify-end")}>
              <TrendIcon value={change} className={heat.text} />
              {change > 0 ? "+" : ""}{change.toFixed(2)}%
            </div>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold hidden md:inline", heat.badge)}>
              {heat.label}
            </span>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div layout initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
      <div
        className={cn(
          "rounded-2xl border p-4 transition-all hover:shadow-md hover:scale-[1.01]",
          heat.bg, heat.text, heat.border
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-bold tracking-wide">{stock.symbol}</div>
            <div className="mt-0.5 text-xs opacity-70 truncate">{stock.name}</div>
          </div>
          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap", heat.badge)}>
            {heat.label}
          </span>
        </div>

        <div className="mt-4 flex items-end justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wider opacity-60">LTP</div>
            <div className="text-xl font-bold">₹{formatNum(stock.ltp)}</div>
          </div>
          <div className="text-right">
            <div className="flex items-center justify-end gap-1 text-base font-bold">
              <TrendIcon value={change} className={heat.text} />
              {change > 0 ? "+" : ""}{change.toFixed(2)}%
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-4 gap-1.5 pt-3 border-t border-current/10">
          {[
            { label: "Open", val: stock.open },
            { label: "High", val: stock.high },
            { label: "Low", val: stock.low },
            { label: "Vol", val: null, volVal: stock.volume },
          ].map(({ label, val, volVal }) => (
            <div key={label} className="text-center">
              <div className="text-[9px] uppercase tracking-wider opacity-50">{label}</div>
              <div className="text-xs font-semibold mt-0.5">
                {volVal !== undefined ? formatVol(volVal) : `₹${formatNum(val)}`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function HeatLegend() {
  const items = [
    { label: "Major Bear", cls: "bg-red-950 text-red-100" },
    { label: "Med Bear", cls: "bg-red-800 text-red-50" },
    { label: "Slight Bear", cls: "bg-orange-200 text-orange-800" },
    { label: "Sideways", cls: "bg-amber-200 text-amber-800" },
    { label: "Slight Bull", cls: "bg-emerald-200 text-emerald-800" },
    { label: "Med Bull", cls: "bg-emerald-500 text-emerald-950" },
    { label: "Major Bull", cls: "bg-emerald-800 text-emerald-50" },
  ];
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((i) => (
        <span key={i.label} className={cn("rounded-full px-2.5 py-1 text-[10px] font-semibold", i.cls)}>
          {i.label}
        </span>
      ))}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const { data, connected, wsStatus, authStatus, refresh, login } = useMarketData();

  const [timeframe, setTimeframe] = useState("1d");
  const [group, setGroup] = useState("nifty20");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("change_desc");
  const [view, setView] = useState("grid"); // grid | compact

  // Show login screen if not authenticated
  if (authStatus === "unauthenticated") {
    return <LoginScreen onLogin={login} />;
  }

  const stocks = data?.groups?.[group] ?? [];

  const filtered = useMemo(() => {
    let list = stocks.filter((s) => {
      const hay = `${s.symbol} ${s.name}`.toLowerCase();
      return hay.includes(query.toLowerCase());
    });

    list.sort((a, b) => {
      const ca = a.changes?.[timeframe] ?? 0;
      const cb = b.changes?.[timeframe] ?? 0;
      switch (sort) {
        case "change_desc": return cb - ca;
        case "change_asc": return ca - cb;
        case "alpha": return a.symbol.localeCompare(b.symbol);
        case "volume": return (b.volume ?? 0) - (a.volume ?? 0);
        default: return cb - ca;
      }
    });

    return list;
  }, [stocks, query, sort, timeframe]);

  const summary = useMemo(() => {
    const vals = stocks.map((s) => s.changes?.[timeframe] ?? 0);
    const green = vals.filter((v) => v >= 0.4).length;
    const red = vals.filter((v) => v <= -0.4).length;
    const side = vals.length - green - red;
    const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    return { green, red, side, avg, total: vals.length };
  }, [stocks, timeframe]);

  const wsColor = wsStatus === "connected" ? "text-emerald-500" : wsStatus === "connecting" ? "text-amber-500" : "text-red-400";

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ─ Header ────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-xl border-b border-slate-100 shadow-sm">
        <div className="mx-auto max-w-[1600px] px-4 py-3 md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            {/* Title + status */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600">
                <BarChart3 className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900 leading-tight">Market Heatmap</h1>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    {connected ? <Wifi className="h-3 w-3 text-emerald-500" /> : <WifiOff className="h-3 w-3 text-red-400" />}
                    {connected ? "Live" : "Offline"}
                  </span>
                  <span>·</span>
                  <span className={cn("flex items-center gap-1", wsColor)}>
                    <Activity className="h-3 w-3" />
                    WS {wsStatus}
                  </span>
                  {data?.tickCount > 0 && (
                    <>
                      <span>·</span>
                      <span>{data.tickCount} tickers</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Timeframe pills */}
              <div className="flex rounded-xl bg-slate-100 p-1 gap-0.5">
                {TIMEFRAMES.map((tf) => (
                  <button
                    key={tf.value}
                    onClick={() => setTimeframe(tf.value)}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                      timeframe === tf.value
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    {tf.short}
                  </button>
                ))}
              </div>

              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search..."
                  className="h-9 w-44 rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-xs outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100 transition"
                />
              </div>

              {/* Sort */}
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none cursor-pointer"
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>

              {/* View toggle */}
              <div className="flex rounded-xl bg-slate-100 p-1">
                <button
                  onClick={() => setView("grid")}
                  className={cn(
                    "rounded-lg p-1.5 transition",
                    view === "grid" ? "bg-white shadow-sm text-slate-900" : "text-slate-400"
                  )}
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setView("compact")}
                  className={cn(
                    "rounded-lg p-1.5 transition",
                    view === "compact" ? "bg-white shadow-sm text-slate-900" : "text-slate-400"
                  )}
                >
                  <LayoutList className="h-4 w-4" />
                </button>
              </div>

              {/* Refresh */}
              <button
                onClick={refresh}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-slate-700 transition"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ─ Body ──────────────────────────────────────────────────────── */}
      <main className="mx-auto max-w-[1600px] px-4 py-6 md:px-6 space-y-6">
        {/* Stats row */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard
            icon={TrendingUp}
            title="Advancing"
            value={summary.green}
            sub={`of ${summary.total} stocks`}
            accent="bg-emerald-50 text-emerald-600"
          />
          <StatCard
            icon={TrendingDown}
            title="Declining"
            value={summary.red}
            sub={`of ${summary.total} stocks`}
            accent="bg-red-50 text-red-600"
          />
          <StatCard
            icon={Minus}
            title="Sideways"
            value={summary.side}
            sub="±0.4% band"
            accent="bg-amber-50 text-amber-600"
          />
          <StatCard
            icon={Activity}
            title="Avg Move"
            value={`${summary.avg > 0 ? "+" : ""}${summary.avg.toFixed(2)}%`}
            sub={TIMEFRAMES.find((t) => t.value === timeframe)?.label}
            accent="bg-blue-50 text-blue-600"
          />
        </div>

        {/* Legend + Group tabs */}
        <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <HeatLegend />
            <div className="flex rounded-xl bg-slate-100 p-1 gap-0.5 overflow-x-auto">
              {GROUPS.map((g) => (
                <button
                  key={g.key}
                  onClick={() => setGroup(g.key)}
                  className={cn(
                    "rounded-lg px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all",
                    group === g.key
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <span className="hidden sm:inline">{g.label}</span>
                  <span className="sm:hidden">{g.short}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Stock grid / list */}
        <AnimatePresence mode="popLayout">
          {filtered.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-2xl bg-white p-12 text-center text-slate-400 shadow-sm border border-slate-100"
            >
              {authStatus === "checking" ? (
                <div className="flex items-center justify-center gap-2">
                  <RefreshCw className="h-5 w-5 animate-spin" />
                  Connecting to Zerodha...
                </div>
              ) : (
                <div>
                  <Search className="mx-auto h-8 w-8 mb-3 opacity-40" />
                  <div className="font-medium">No stocks found</div>
                  <div className="text-xs mt-1">
                    {query ? "Try a different search term" : "Waiting for market data..."}
                  </div>
                </div>
              )}
            </motion.div>
          ) : view === "compact" ? (
            <div className="space-y-1.5">
              {filtered.map((stock) => (
                <StockCard
                  key={`${group}-${stock.symbol}`}
                  stock={stock}
                  timeframe={timeframe}
                  view="compact"
                />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {filtered.map((stock) => (
                <StockCard
                  key={`${group}-${stock.symbol}`}
                  stock={stock}
                  timeframe={timeframe}
                  view="grid"
                />
              ))}
            </div>
          )}
        </AnimatePresence>
      </main>

      {/* ─ Footer ────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-100 bg-white/50 py-4 text-center text-xs text-slate-400">
        Zerodha Market Heatmap · Data via Kite Connect · {new Date().getFullYear()}
      </footer>
    </div>
  );
}

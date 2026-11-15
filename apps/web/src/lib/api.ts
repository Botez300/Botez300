import type {
  BarsResponse, IndicatorResult, IndicatorSpec, Preset, ProviderInfo, SavedScan, ScanDefinition, ScanResult,
  Session, SymbolInfo, Timeframe, Universe, Watchlist,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function detail(body: unknown, fallback: string): string {
  const d = (body as { detail?: unknown } | null)?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`).join("; ");
  return fallback;
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "same-origin",
    headers: init?.json !== undefined ? { "content-type": "application/json" } : undefined,
    body: init?.json !== undefined ? JSON.stringify(init.json) : undefined,
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detail(body, `Request failed (${res.status})`));
  return body as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, json?: unknown) => request<T>(path, { method: "POST", json: json ?? {} });
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

const barsCache = new Map<string, Promise<BarsResponse>>();

export const api = {
  me: () => get<Session>("/auth/me"),
  login: (email: string, password: string) => post<Session>("/auth/login", { email, password }),
  register: (email: string, password: string, display_name: string) =>
    post<Session>("/auth/register", { email, password, display_name }),
  logout: () => post<void>("/auth/logout"),

  provider: () => get<ProviderInfo>("/provider"),
  search: (q: string, limit = 12) =>
    get<{ results: SymbolInfo[] }>(`/symbols/search?q=${encodeURIComponent(q)}&limit=${limit}`).then((r) => r.results),
  symbol: (symbol: string) => get<SymbolInfo>(`/symbols/${encodeURIComponent(symbol)}`),
  /** Bars are cached per page load so the chart, its indicators and tiles share one request. */
  bars: (symbol: string, timeframe: Timeframe = "1D", limit = 20000) => {
    const key = `${symbol}|${timeframe}|${limit}`;
    let hit = barsCache.get(key);
    if (!hit) {
      hit = get<BarsResponse>(`/bars/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=${limit}`);
      barsCache.set(key, hit);
      hit.catch(() => barsCache.delete(key));
    }
    return hit;
  },
  indicators: () => get<{ indicators: IndicatorSpec[] }>("/indicators").then((r) => r.indicators),
  compute: (symbol: string, timeframe: Timeframe, indicator: string, params: Record<string, unknown>) =>
    post<IndicatorResult>("/indicators/compute", { symbol, timeframe, indicator, params, limit: 20000 }),

  watchlists: () => get<{ watchlists: Watchlist[] }>("/watchlists").then((r) => r.watchlists),
  createWatchlist: (name: string) => post<Watchlist>("/watchlists", { name }),
  deleteWatchlist: (id: string) => del<void>(`/watchlists/${id}`),
  addSymbol: (id: string, symbol: string) => post<Watchlist>(`/watchlists/${id}/symbols`, { symbol }),
  removeSymbol: (id: string, symbol: string) => del<Watchlist>(`/watchlists/${id}/symbols/${encodeURIComponent(symbol)}`),

  presets: () => get<{ presets: Preset[] }>("/scans/presets").then((r) => r.presets),
  runScan: (definition: ScanDefinition, universe: Universe) => post<ScanResult>("/scans/run", { definition, universe }),
  savedScans: () => get<{ scans: SavedScan[] }>("/scans/saved").then((r) => r.scans),
  saveScan: (name: string, definition: ScanDefinition, universe: Universe) =>
    post<SavedScan>("/scans/saved", { name, definition, universe }),
  deleteScan: (id: string) => del<void>(`/scans/saved/${id}`),
};

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/badges";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { num, pct, price, tone } from "@/lib/format";
import type { Preset, ScanDefinition, ScanResult, Universe, Watchlist } from "@/lib/types";

// One pass over the list that reads the values the monitor shows; every rule is always true.
const MONITOR: ScanDefinition = {
  filter: {
    logic: "or",
    rules: [
      { left: { field: "close" }, op: ">", right: { value: 0 } },
      { left: { field: "close", offset: 1 }, op: ">", right: { value: 0 } },
      { left: { indicator: "rsi", params: { length: 14 } }, op: ">=", right: { value: 0 } },
      { left: { indicator: "sma", params: { length: 50 } }, op: ">", right: { value: 0 } },
      { left: { indicator: "sma", params: { length: 200 } }, op: ">", right: { value: 0 } },
    ],
  },
  limit: 200,
};

function Monitor({ universe, title }: { universe: Universe; title: string }) {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(universe);
  useEffect(() => {
    setResult(null);
    api.runScan(MONITOR, JSON.parse(key) as Universe).then(setResult).catch((e) => setError(e.message));
  }, [key]);

  return (
    <section className="panel" aria-label={title} data-testid="monitor">
      <div className="panel-title flex items-center gap-2">{title}{result && <StatusBadge status={result.data_status} />}
        {result?.rows[0] && <span className="ml-auto font-normal normal-case tracking-normal">Last completed session {result.rows[0].bar_date}</span>}
      </div>
      {error && <p role="alert" className="p-3 text-xs text-down">{error}</p>}
      {!result && !error && <p className="p-3 text-xs text-dim">Loading…</p>}
      {result && result.rows.length === 0 && <p className="p-3 text-xs text-dim">Nothing to show yet.</p>}
      {result && result.rows.length > 0 && (
        <div className="max-h-[26rem] overflow-auto">
          <table className="w-full border-collapse">
            <thead className="sticky top-0 bg-panel">
              <tr className="border-b border-line">
                <th className="th">Symbol</th><th className="th text-right">Close</th><th className="th text-right">1-day</th>
                <th className="th text-right">RSI 14</th><th className="th">vs 50d</th><th className="th">vs 200d</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((r) => {
                const v = r.values;
                const close = v["close 1D"] ?? null;
                const prev = v["close[1] 1D"] ?? null;
                const side = (ma: number | null | undefined) => close == null || ma == null
                  ? <span className="text-dim">n/a</span>
                  : <span className={close > ma ? "text-up" : "text-down"}>{close > ma ? "Above" : "Below"}</span>;
                return (
                  <tr key={r.symbol} className="border-b border-line/60 hover:bg-raised">
                    <td className="td"><Link href={`/charts?symbol=${r.symbol}`} className="font-mono font-semibold text-brass hover:underline" title={r.name}>{r.symbol}</Link></td>
                    <td className="td num text-right">{price(close)}</td>
                    <td className={`td num text-right ${tone(close != null && prev ? close / prev - 1 : null)}`}>{pct(close != null && prev ? (close / prev - 1) * 100 : null)}</td>
                    <td className="td num text-right">{num(v["rsi(14) 1D"], 1)}</td>
                    <td className="td">{side(v["sma(50) 1D"])}</td>
                    <td className="td">{side(v["sma(200) 1D"])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ScanPulse({ presets, universe }: { presets: Preset[]; universe: Universe }) {
  const [results, setResults] = useState<Record<string, ScanResult | "error">>({});
  const key = JSON.stringify(universe);
  useEffect(() => {
    setResults({});
    for (const p of presets) {
      api.runScan({ ...p.definition, limit: 5 }, JSON.parse(key) as Universe)
        .then((r) => setResults((x) => ({ ...x, [p.id]: r })))
        .catch(() => setResults((x) => ({ ...x, [p.id]: "error" })));
    }
  }, [presets, key]);

  return (
    <section className="panel" aria-label="Scan pulse" data-testid="scan-pulse">
      <div className="panel-title">Scan pulse · latest completed session</div>
      <ul>
        {presets.map((p) => {
          const r = results[p.id];
          return (
            <li key={p.id} className="flex items-center gap-3 border-b border-line px-3 py-2 last:border-0">
              <Link href={`/scanner?preset=${p.id}`} className="min-w-0 flex-1 hover:text-brass" title={p.description}>
                <div className="truncate text-xs font-semibold">{p.name}</div>
                <div className="truncate font-mono text-[11px] text-dim">
                  {r === undefined ? "Scanning…" : r === "error" ? "Scan failed" : r.rows.map((x) => x.symbol).join("  ") || "No matches"}
                </div>
              </Link>
              <span className="num w-10 text-right text-sm font-semibold">{r && r !== "error" ? r.matched : "—"}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function CommandCenter() {
  const { session, provider } = useSession();
  const [lists, setLists] = useState<Watchlist[] | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selected, setSelected] = useState("");

  useEffect(() => {
    api.watchlists().then((w) => { setLists(w); setSelected(w.find((x) => x.symbols.length)?.id ?? ""); }).catch(() => setLists([]));
    api.presets().then(setPresets).catch(() => {});
  }, []);

  const list = lists?.find((w) => w.id === selected);
  const scanUniverse: Universe | null = provider.can_enumerate_universe ? { type: "provider" }
    : list ? { type: "watchlist", watchlist_id: list.id } : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold">Command Center</h1>
          <p className="text-xs text-dim">{session.organization.name}</p>
        </div>
        {lists && lists.length > 0 && (
          <label className="flex items-center gap-2 text-xs text-dim">Watchlist
            <select aria-label="Monitored watchlist" className="input" value={selected} onChange={(e) => setSelected(e.target.value)}>
              {lists.map((w) => <option key={w.id} value={w.id}>{w.name} ({w.symbols.length})</option>)}
            </select>
          </label>
        )}
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        <div className="space-y-3">
          {list && list.symbols.length > 0
            ? <Monitor universe={{ type: "watchlist", watchlist_id: list.id }} title={`Watchlist · ${list.name}`} />
            : (
              <section className="panel p-5 text-sm" data-testid="empty-watchlists">
                <h2 className="mb-1 font-semibold">{lists === null ? "Loading watchlists…" : "Start with a watchlist"}</h2>
                {lists !== null && <p className="text-xs text-dim">Create a list and add symbols to monitor them here. <Link className="text-brass" href="/watchlists">Open Watchlists</Link></p>}
              </section>
            )}
          {provider.can_enumerate_universe && <Monitor universe={{ type: "provider", asset_types: ["etf"] }} title="Market and sector ETFs" />}
        </div>
        <div className="space-y-3">
          {scanUniverse && presets.length > 0 && <ScanPulse presets={presets} universe={scanUniverse} />}
          <section className="panel" aria-label="Data source">
            <div className="panel-title flex items-center gap-2">Data source <StatusBadge status={provider.data_status} /></div>
            <dl className="grid grid-cols-[7rem_1fr] gap-y-1 p-3 text-xs">
              <dt className="text-dim">Provider</dt><dd>{provider.name}</dd>
              <dt className="text-dim">Timeframes</dt><dd>{provider.timeframes.join(", ")} (intraday not yet supported)</dd>
              <dt className="text-dim">Adjustment</dt><dd>{provider.adjustment}</dd>
              <dt className="text-dim">Licensing</dt><dd>{provider.license_note}</dd>
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}

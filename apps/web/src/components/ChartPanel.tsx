"use client";

import type { Vela } from "@luxalgo/vela";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { num, pct, price, tone } from "@/lib/format";
import type { BarsResponse, IndicatorSpec, Timeframe } from "@/lib/types";

import { StatusBadge, VerificationBadge } from "./badges";

const TIMEFRAMES: { id: Timeframe; vela: string; label: string }[] = [
  { id: "1D", vela: "D", label: "Daily" },
  { id: "1W", vela: "W", label: "Weekly" },
  { id: "1M", vela: "M", label: "Monthly" },
];
const STYLES = [["candles", "Candles"], ["bars", "Bars"], ["heikinashi", "Heikin-Ashi"], ["line", "Line"], ["area", "Area"]] as const;
const DEFAULT_INDICATORS = ["sma", "rsi"];
const STORE = "legion.chart.v1";

interface Active {
  key: number;
  spec: IndicatorSpec;
  remove: () => void;
}

interface Saved {
  timeframe?: Timeframe;
  style?: string;
  log?: boolean;
  indicators?: string[];
}

function loadSaved(): Saved {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? "{}") as Saved;
  } catch {
    return {};
  }
}

export default function ChartPanel({ symbol }: { symbol: string }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<Vela | null>(null);
  const seq = useRef(0);
  const [catalog, setCatalog] = useState<IndicatorSpec[]>([]);
  const [active, setActive] = useState<Active[]>([]);
  const [timeframe, setTimeframe] = useState<Timeframe>("1D");
  const [style, setStyle] = useState<string>("candles");
  const [log, setLog] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<BarsResponse | null>(null);

  const addIndicator = (spec: IndicatorSpec) => {
    const c = chart.current;
    if (!c) return;
    const handle = c.addNativeIndicator(`legion.${spec.id}`);
    const key = ++seq.current;
    setActive((list) => [...list, { key, spec, remove: () => handle.remove() }]);
  };

  // Build the chart once. Vela is browser-only, so it is imported here rather than at module scope.
  useEffect(() => {
    let disposed = false;
    const saved = loadSaved();
    const tf = TIMEFRAMES.find((t) => t.id === saved.timeframe) ?? TIMEFRAMES[0]!;
    (async () => {
      try {
        const [{ Vela }, bridge, specs] = await Promise.all([import("@luxalgo/vela"), import("@/lib/vela"), api.indicators()]);
        if (disposed || !host.current) return;
        bridge.registerLegionIndicators(specs);
        const c = new Vela(host.current, {
          symbol: `${bridge.PROVIDER_ID}:${symbol}`, timeframe: tf.vela, theme: "dark", live: false,
          priceStyle: saved.style ?? "candles", logScale: saved.log ?? false, upColor: "#3fb68b", downColor: "#e5646e",
        });
        // Bars are completed sessions served on request, not a stream: no bar-close countdown.
        c.renderer.set("countdown", false);
        c.data.registerProvider(bridge.PROVIDER_ID, bridge.legionProvider);
        chart.current = c;
        setCatalog(specs);
        setTimeframe(tf.id);
        setStyle(saved.style ?? "candles");
        setLog(saved.log ?? false);
        await c.ready();
        if (disposed) return;
        setReady(true);
        for (const id of saved.indicators ?? DEFAULT_INDICATORS) {
          const spec = specs.find((s) => s.id === id);
          if (spec) addIndicator(spec);
        }
      } catch (e) {
        if (!disposed) setError(e instanceof Error ? e.message : "The chart could not be created.");
      }
    })();
    return () => {
      disposed = true;
      chart.current?.destroy();
      chart.current = null;
    };
    // The chart is created once; symbol and timeframe changes go through setMarket below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || !chart.current) return;
    const tf = TIMEFRAMES.find((t) => t.id === timeframe)!;
    void chart.current.setMarket({ symbol: `legion:${symbol}`, timeframe: tf.vela });
  }, [symbol, timeframe, ready]);

  useEffect(() => {
    let live = true;
    setMeta(null);
    api.bars(symbol, timeframe).then((m) => live && setMeta(m)).catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [symbol, timeframe]);

  useEffect(() => {
    if (!ready) return;
    const saved: Saved = { timeframe, style, log, indicators: active.map((a) => a.spec.id) };
    localStorage.setItem(STORE, JSON.stringify(saved));
  }, [timeframe, style, log, active, ready]);

  const last = meta?.bars.at(-1);
  const prev = meta?.bars.at(-2);
  const change = last && prev ? (last.c / prev.c - 1) * 100 : null;
  const categories = [...new Set(catalog.map((s) => s.category))];

  return (
    <section className="panel flex h-full min-h-[480px] flex-col" aria-label={`${symbol} chart`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <h1 className="font-mono text-base font-semibold text-brass" data-testid="chart-symbol">{symbol}</h1>
        {last && (
          <span className="num text-xs" data-testid="chart-quote">
            O {price(last.o)} H {price(last.h)} L {price(last.l)} C <b>{price(last.c)}</b>{" "}
            <span className={tone(change)}>{pct(change)}</span> <span className="text-dim">Vol {num(last.v, 0)}</span>
          </span>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <div role="group" aria-label="Timeframe" className="flex gap-1">
            {TIMEFRAMES.map((t) => (
              <button key={t.id} className={`btn ${timeframe === t.id ? "btn-on" : ""}`} aria-pressed={timeframe === t.id}
                onClick={() => setTimeframe(t.id)}>{t.label}</button>
            ))}
          </div>
          <select aria-label="Chart style" className="input" value={style}
            onChange={(e) => { setStyle(e.target.value); chart.current?.renderer.set("priceStyle", e.target.value); }}>
            {STYLES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
          <button className={`btn ${log ? "btn-on" : ""}`} aria-pressed={log}
            onClick={() => { chart.current?.renderer.set("logScale", !log); setLog(!log); }}>Log</button>
          <select aria-label="Add indicator" className="input" value="" disabled={!ready}
            onChange={(e) => { const s = catalog.find((x) => x.id === e.target.value); if (s) addIndicator(s); }}>
            <option value="">+ Indicator</option>
            {categories.map((cat) => (
              <optgroup key={cat} label={cat[0]!.toUpperCase() + cat.slice(1)}>
                {catalog.filter((s) => s.category === cat).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
      </div>
      {active.length > 0 && (
        <ul aria-label="Active indicators" className="flex flex-wrap gap-1.5 border-b border-line px-3 py-1.5">
          {active.map((a) => (
            <li key={a.key} className="flex items-center gap-1 rounded border border-line bg-raised pl-2 text-[11px]" title={a.spec.reference}>
              {a.spec.name}
              <button aria-label={`Remove ${a.spec.name}`} className="px-1.5 py-0.5 text-dim hover:text-down"
                onClick={() => { a.remove(); setActive((l) => l.filter((x) => x.key !== a.key)); }}>×</button>
            </li>
          ))}
        </ul>
      )}
      <div className="relative min-h-0 flex-1">
        <div ref={host} data-testid="chart-host" className="absolute inset-0" />
        {!ready && !error && <div className="absolute inset-0 grid place-items-center text-xs text-dim">Loading chart…</div>}
        {error && <div role="alert" className="absolute inset-0 grid place-items-center p-6 text-center text-xs text-down">{error}</div>}
      </div>
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-1.5 text-[11px] text-dim" data-testid="chart-provenance">
        {meta ? (
          <>
            <span className="flex items-center gap-1">Data <StatusBadge status={meta.data_status} /></span>
            <span className="flex items-center gap-1">Validation <VerificationBadge state={meta.verification} /></span>
            <span>Provider {meta.provider}</span>
            <span>Exchange {meta.exchange || "—"}</span>
            <span>Adjustment {meta.adjustment}</span>
            <span>{meta.bars.length.toLocaleString()} bars · {meta.first_bar} → {meta.last_bar}</span>
            {meta.last_bar_forming && <span className="text-brass">Last bar still forming</span>}
            {meta.warnings.map((w) => <span key={w} className="text-brass">⚠ {w}</span>)}
          </>
        ) : <span>Loading data provenance…</span>}
        <a className="ml-auto hover:text-text" href="https://velacharts.dev" target="_blank" rel="noreferrer">Charts by Vela</a>
      </footer>
    </section>
  );
}

/**
 * Bridges the Vela chart (Apache-2.0, © LuxAlgo — see /NOTICE) to the Legion API.
 *
 *  - `legionProvider` serves bars from GET /api/v1/bars.
 *  - Every indicator in the API catalog is registered as a Vela native indicator whose values are
 *    computed by the API, so the chart, the scanner and (later) backtests share one implementation.
 */
import { DataUnavailableError, type DataProvider, type OHLCV, type SymbolDescriptor } from "@luxalgo/vela";
import {
  registerNativeIndicator, stableSeriesId, type InputValue, type NativeIndicator, type NativeIndicatorContext,
} from "@luxalgo/vela/plugin";

import { api } from "./api";
import type { IndicatorSpec, Timeframe } from "./types";

export const PROVIDER_ID = "legion";

const TIMEFRAME: Record<string, Timeframe> = {
  D: "1D", "1D": "1D", "1d": "1D", W: "1W", "1W": "1W", "1w": "1W", M: "1M", "1M": "1M",
};

export function toTimeframe(tf: string): Timeframe | undefined {
  return TIMEFRAME[tf];
}

/** `LEGION:ALFA` / `legion:alfa` / `ALFA` -> `ALFA` */
export function bareSymbol(symbol: string): string {
  return symbol.slice(symbol.indexOf(":") + 1).toUpperCase();
}

export const legionProvider: DataProvider = {
  async getBars(ticker, timeframe, range) {
    const tf = toTimeframe(timeframe);
    if (!tf) throw new DataUnavailableError({ reason: "timeframe", finest: "1D", default: "1D" });
    const { bars } = await api.bars(bareSymbol(ticker), tf);
    let out: OHLCV[] = bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c, volume: b.v }));
    if (range.to != null) out = out.filter((b) => b.time <= range.to!);
    if (range.from != null) out = out.filter((b) => b.time >= range.from!);
    if (range.limit != null && out.length > range.limit) out = out.slice(-range.limit);
    return out;
  },
  async listSymbols(): Promise<SymbolDescriptor[]> {
    const results = await api.search("", 100);
    return results.map((s) => ({ ticker: s.symbol, description: s.name, type: s.asset_type, prefix: s.exchange || undefined }));
  },
  async getSymbolInfo(ticker) {
    const s = await api.symbol(bareSymbol(ticker));
    return {
      ticker: s.symbol, description: s.name, type: s.asset_type, timezone: "America/New_York", session: "0930-1600",
      timeframes: { finest: "1D", default: "1D", list: ["1D", "W", "1M"] },
    };
  },
};

const PALETTE = ["#e3b04b", "#5aa9e6", "#c084fc", "#3fb68b", "#e5646e", "#94a3b8"];
const registered = new Set<string>();

export const nativeType = (id: string) => `legion.${id}`;

function register(spec: IndicatorSpec) {
  const type = nativeType(spec.id);
  if (registered.has(type)) return;
  registered.add(type);
  const defaults = Object.fromEntries(spec.params.map((p) => [p.name, p.default])) as Record<string, InputValue>;

  registerNativeIndicator({
    type,
    title: spec.name,
    paneHint: spec.overlay ? "price" : "new",
    overlay: spec.overlay,
    multiInstance: true,
    waitsForHistory: true,
    inputsSchema: () =>
      spec.params.map((p) => ({
        key: p.name, title: p.title, type: p.kind, defval: p.default as InputValue,
        ...(p.min != null ? { min: p.min } : {}), ...(p.max != null ? { max: p.max } : {}),
        ...(p.kind === "float" ? { step: 0.1 } : {}),
      })),
    defaultInputs: () => ({ ...defaults }),
    create: (): NativeIndicator => {
      let ctx: NativeIndicatorContext | null = null;
      let inputs: Record<string, InputValue> = { ...defaults };
      let run = 0;

      const compute = async () => {
        if (!ctx) return;
        const tf = toTimeframe(ctx.timeframe);
        const bars = ctx.bars();
        if (!tf || bars.length === 0) return;
        const mine = ++run;
        ctx.setStatus("loading");
        try {
          const result = await api.compute(bareSymbol(ctx.symbol), tf, spec.id, inputs);
          if (!ctx || mine !== run) return; // superseded by a newer run or stopped
          const index = new Map(result.t.map((t, i) => [t, i]));
          const current = ctx.bars();
          ctx.emit({
            series: spec.outputs
              .filter((o) => !(spec.id === "supertrend" && o.name === "direction"))
              .map((o, n) => ({
                id: stableSeriesId({ instanceId: type, kind: "line", title: o.name, ordinal: n }),
                title: o.title,
                paneId: "",
                kind: o.style === "histogram" ? ("histogram" as const) : o.style === "dots" ? ("circles" as const) : ("line" as const),
                points: current.map((b) => {
                  const i = index.get(b.time);
                  return { time: b.time, value: i == null ? null : (result.outputs[o.name]?.[i] ?? null) };
                }),
                style: { color: PALETTE[n % PALETTE.length]!, width: o.style === "dots" ? 2 : 1.5, lineStyle: "solid" as const },
              })),
            priceLines: spec.overlay
              ? []
              : spec.levels.map((level, n) => ({
                  id: stableSeriesId({ instanceId: type, kind: "hline", title: `level-${level}`, ordinal: n }),
                  paneId: "", price: level, lineStyle: "dashed" as const, width: 1,
                })),
          });
          ctx.setStatus("idle");
        } catch (e) {
          console.warn(`[legion] ${spec.id} failed`, e);
          ctx?.setStatus("idle");
        }
      };

      return {
        start: (c, initial) => { ctx = c; inputs = { ...defaults, ...initial }; void compute(); },
        onBars: () => void compute(),
        onViewport: () => {},
        setInputs: (next) => { inputs = { ...defaults, ...next }; void compute(); },
        suspend: () => {},
        resume: () => void compute(),
        stop: () => { ctx = null; },
      };
    },
  });
}

/** Register every catalog indicator with Vela. Must run before a chart is constructed. */
export function registerLegionIndicators(specs: IndicatorSpec[]) {
  specs.forEach(register);
}

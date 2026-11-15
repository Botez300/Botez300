"use client";

import { defaultOperand } from "@/lib/scan";
import type { IndicatorSpec, Operand, Timeframe } from "@/lib/types";

const FIELDS = ["close", "open", "high", "low", "volume"] as const;

interface Props {
  value: Operand;
  onChange: (o: Operand) => void;
  catalog: IndicatorSpec[];
  label: string;
}

/** Edits one side of a scan rule: a number, a price field, or an indicator output. */
export function OperandEditor({ value, onChange, catalog, label }: Props) {
  const kind = value.value !== undefined ? "value" : value.field ? "field" : "indicator";
  const spec = catalog.find((s) => s.id === value.indicator);
  const series = kind !== "value";

  const setKind = (k: string) => {
    if (k === "value") onChange({ value: 0 });
    else if (k === "field") onChange({ field: "close", timeframe: value.timeframe, offset: value.offset });
    else if (catalog[0]) onChange({ ...defaultOperand(catalog.find((s) => s.id === "sma") ?? catalog[0]), timeframe: value.timeframe, offset: value.offset });
  };
  const number = (raw: string, fallback: number) => (raw.trim() === "" || Number.isNaN(Number(raw)) ? fallback : Number(raw));

  return (
    <fieldset className="flex flex-wrap items-center gap-1.5" aria-label={label}>
      <select aria-label={`${label} type`} className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
        <option value="field">Price</option>
        <option value="indicator">Indicator</option>
        <option value="value">Number</option>
      </select>
      {kind === "value" && (
        <input aria-label={`${label} number`} type="number" step="any" className="input w-24" value={value.value}
          onChange={(e) => onChange({ value: number(e.target.value, 0) })} />
      )}
      {kind === "field" && (
        <select aria-label={`${label} field`} className="input" value={value.field}
          onChange={(e) => onChange({ ...value, field: e.target.value as Operand["field"] })}>
          {FIELDS.map((f) => <option key={f}>{f}</option>)}
        </select>
      )}
      {kind === "indicator" && (
        <>
          <select aria-label={`${label} indicator`} className="input max-w-44" value={value.indicator}
            onChange={(e) => { const s = catalog.find((x) => x.id === e.target.value); if (s) onChange({ ...defaultOperand(s), timeframe: value.timeframe, offset: value.offset }); }}>
            {catalog.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {spec && spec.outputs.length > 1 && (
            <select aria-label={`${label} output`} className="input" value={value.output ?? spec.outputs[0]!.name}
              onChange={(e) => onChange({ ...value, output: e.target.value })}>
              {spec.outputs.map((o) => <option key={o.name} value={o.name}>{o.title}</option>)}
            </select>
          )}
          {spec?.params.filter((p) => p.kind !== "source").map((p) => (
            <label key={p.name} className="flex items-center gap-1 text-[10px] uppercase text-dim">{p.title}
              <input type="number" className="input w-16" step={p.kind === "int" ? 1 : "any"} min={p.min ?? undefined} max={p.max ?? undefined}
                value={String(value.params?.[p.name] ?? p.default)}
                onChange={(e) => onChange({ ...value, params: { ...value.params, [p.name]: number(e.target.value, Number(p.default)) } })} />
            </label>
          ))}
        </>
      )}
      {series && (
        <>
          <select aria-label={`${label} timeframe`} className="input" value={value.timeframe ?? "1D"}
            onChange={(e) => onChange({ ...value, timeframe: e.target.value as Timeframe })}>
            <option value="1D">Daily</option><option value="1W">Weekly</option><option value="1M">Monthly</option>
          </select>
          <label className="flex items-center gap-1 text-[10px] uppercase text-dim" title="Read the value this many completed bars back">Bars ago
            <input type="number" min={0} max={500} className="input w-14" value={value.offset ?? 0}
              onChange={(e) => onChange({ ...value, offset: Math.max(0, Math.min(500, Math.trunc(number(e.target.value, 0)))) })} />
          </label>
          <label className="flex items-center gap-1 text-[10px] uppercase text-dim" title="Multiply the value, e.g. 1.5 × average volume">×
            <input type="number" min={0.01} step="any" className="input w-14" value={value.multiplier ?? 1}
              onChange={(e) => onChange({ ...value, multiplier: Math.max(0.0001, number(e.target.value, 1)) })} />
          </label>
        </>
      )}
    </fieldset>
  );
}

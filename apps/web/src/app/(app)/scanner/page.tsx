"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { StatusBadge, VerificationBadge } from "@/components/badges";
import { OperandEditor } from "@/components/OperandEditor";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { num, price } from "@/lib/format";
import { conditionLabel, exportCsv, exportJson, operandLabel } from "@/lib/scan";
import type { Comparator, Condition, IndicatorSpec, Preset, SavedScan, ScanDefinition, ScanResult, Universe, Watchlist } from "@/lib/types";

const OPS: [Comparator, string][] = [[">", ">"], [">=", "≥"], ["<", "<"], ["<=", "≤"], ["crosses_above", "crosses above"], ["crosses_below", "crosses below"]];
const BLANK: Condition = { left: { field: "close" }, op: ">", right: { indicator: "sma", params: { length: 50 } } };

const isFlat = (d: ScanDefinition) => d.filter.rules.every((r) => "left" in r);

function Scanner() {
  const { provider } = useSession();
  const params = useSearchParams();
  const [catalog, setCatalog] = useState<IndicatorSpec[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [saved, setSaved] = useState<SavedScan[]>([]);
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [rules, setRules] = useState<Condition[]>([BLANK]);
  const [logic, setLogic] = useState<"and" | "or">("and");
  const [sortIndex, setSortIndex] = useState(-1);
  const [sortDesc, setSortDesc] = useState(true);
  const [scope, setScope] = useState(provider.can_enumerate_universe ? "provider:all" : "");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [loadedName, setLoadedName] = useState<string | null>(null);

  const operands = useMemo(() => {
    const seen = new Map<string, Condition["left"]>();
    for (const r of rules) for (const o of [r.left, r.right]) if (o.value === undefined) seen.set(operandLabel(o), o);
    return [...seen.entries()];
  }, [rules]);

  const definition: ScanDefinition = useMemo(() => ({
    filter: { logic, rules },
    ...(operands[sortIndex] ? { sort_by: operands[sortIndex][1], sort_desc: sortDesc } : {}),
    limit: 200,
  }), [logic, rules, operands, sortIndex, sortDesc]);

  const universe: Universe | null = useMemo(() => {
    if (scope.startsWith("provider:")) {
      const kind = scope.slice(9);
      return { type: "provider", ...(kind !== "all" ? { asset_types: [kind] } : {}) };
    }
    return scope.startsWith("watchlist:") ? { type: "watchlist", watchlist_id: scope.slice(10) } : null;
  }, [scope]);

  const load = (d: ScanDefinition, label: string, u?: Universe) => {
    if (!isFlat(d)) { setError("This scan uses nested groups, which the builder cannot edit yet. Run it from the saved list instead."); return; }
    const flat = d.filter.rules as Condition[];
    setRules(flat);
    setLogic(d.filter.logic);
    const labels = [...new Set(flat.flatMap((r) => [r.left, r.right]).filter((o) => o.value === undefined).map(operandLabel))];
    setSortIndex(d.sort_by ? labels.indexOf(operandLabel(d.sort_by)) : -1);
    setSortDesc(d.sort_desc ?? true);
    if (u) setScope(u.type === "watchlist" ? `watchlist:${u.watchlist_id}` : `provider:${u.asset_types?.[0] ?? "all"}`);
    setLoadedName(label);
    setResult(null);
    setError(null);
  };

  useEffect(() => {
    api.indicators().then(setCatalog).catch((e) => setError(e.message));
    api.savedScans().then(setSaved).catch(() => {});
    api.watchlists().then((w) => { setLists(w); setScope((s) => s || (w[0] ? `watchlist:${w[0].id}` : "")); }).catch(() => {});
    api.presets().then((p) => {
      setPresets(p);
      const wanted = p.find((x) => x.id === params.get("preset"));
      if (wanted) load(wanted.definition, wanted.name);
    }).catch(() => {});
    // Runs once; `load` only touches state setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (i: number, patch: Partial<Condition>) => setRules((rs) => rs.map((r, n) => (n === i ? { ...r, ...patch } : r)));

  async function run() {
    if (!universe) { setError("Choose what to scan."); return; }
    setBusy(true);
    setError(null);
    try {
      setResult(await api.runScan(definition, universe));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!universe || !name.trim()) return;
    try {
      const s = await api.saveScan(name.trim(), definition, universe);
      setSaved((l) => [...l, s].sort((a, b) => a.name.localeCompare(b.name)));
      setName("");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_17rem]">
      <div className="min-w-0 space-y-3">
        <section className="panel" aria-label="Scan builder">
          <div className="panel-title flex flex-wrap items-center justify-between gap-2">
            <span>Scan builder{loadedName ? ` · ${loadedName}` : ""}</span>
            <span className="font-normal normal-case tracking-normal">Rules are evaluated on completed bars only.</span>
          </div>
          <div className="space-y-2 p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <label className="flex items-center gap-1.5">Scan
                <select aria-label="Universe" className="input" value={scope} onChange={(e) => setScope(e.target.value)}>
                  {!scope && <option value="">Choose…</option>}
                  {provider.can_enumerate_universe && (
                    <optgroup label={`${provider.name} universe`}>
                      <option value="provider:all">All symbols</option>
                      <option value="provider:stock">Stocks</option>
                      <option value="provider:etf">ETFs</option>
                    </optgroup>
                  )}
                  {lists.length > 0 && (
                    <optgroup label="Watchlists">
                      {lists.map((w) => <option key={w.id} value={`watchlist:${w.id}`}>{w.name} ({w.symbols.length})</option>)}
                    </optgroup>
                  )}
                </select>
              </label>
              <label className="flex items-center gap-1.5">matching
                <select aria-label="Rule logic" className="input" value={logic} onChange={(e) => setLogic(e.target.value as "and" | "or")}>
                  <option value="and">all rules (AND)</option>
                  <option value="or">any rule (OR)</option>
                </select>
              </label>
            </div>
            {rules.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded border border-line bg-ink/40 p-2" data-testid="rule">
                <OperandEditor label={`Rule ${i + 1} left`} catalog={catalog} value={r.left} onChange={(left) => update(i, { left })} />
                <select aria-label={`Rule ${i + 1} comparison`} className="input font-semibold text-brass" value={r.op}
                  onChange={(e) => update(i, { op: e.target.value as Comparator })}>
                  {OPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
                <OperandEditor label={`Rule ${i + 1} right`} catalog={catalog} value={r.right} onChange={(right) => update(i, { right })} />
                <button className="ml-auto text-xs text-dim hover:text-down disabled:opacity-30" disabled={rules.length === 1}
                  aria-label={`Remove rule ${i + 1}`} onClick={() => setRules((rs) => rs.filter((_, n) => n !== i))}>Remove</button>
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn" disabled={rules.length >= 25} onClick={() => setRules((rs) => [...rs, BLANK])}>+ Add rule</button>
              <label className="flex items-center gap-1.5 text-xs">Rank by
                <select aria-label="Rank by" className="input" value={sortIndex} onChange={(e) => setSortIndex(Number(e.target.value))}>
                  <option value={-1}>Symbol (A–Z)</option>
                  {operands.map(([label], i) => <option key={label} value={i}>{label}</option>)}
                </select>
              </label>
              {sortIndex >= 0 && <button className="btn" onClick={() => setSortDesc((d) => !d)}>{sortDesc ? "High → low" : "Low → high"}</button>}
              <button className="btn btn-primary ml-auto px-4" onClick={run} disabled={busy || !universe}>{busy ? "Scanning…" : "Run scan"}</button>
            </div>
            <div className="rounded border border-line p-2 text-xs" aria-label="Conditions to be evaluated" data-testid="conditions-preview">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-dim">Conditions that will run</div>
              <ol className="list-inside list-decimal space-y-0.5 font-mono">
                {rules.map((r, i) => <li key={i}>{conditionLabel(r)}{i < rules.length - 1 && <span className="text-brass"> {logic.toUpperCase()}</span>}</li>)}
              </ol>
            </div>
            {error && <p role="alert" className="text-xs text-down">{error}</p>}
          </div>
        </section>

        {result && (
          <section className="panel" aria-label="Scan results" data-testid="scan-results">
            <div className="panel-title flex flex-wrap items-center gap-2">
              <span data-testid="scan-summary">{result.matched} of {result.scanned} matched</span>
              <StatusBadge status={result.data_status} />
              <span className="font-normal normal-case tracking-normal">
                {result.provider} · as of {new Date(result.as_of).toLocaleString()} · {result.duration_ms} ms · {result.engine_version}
              </span>
              <span className="ml-auto flex gap-1.5">
                <button className="btn" onClick={() => exportCsv(result)} disabled={!result.rows.length}>CSV</button>
                <button className="btn" onClick={() => exportJson(result)}>JSON</button>
              </span>
            </div>
            {(result.insufficient.length > 0 || result.errors.length > 0) && (
              <p className="border-b border-line px-3 py-1.5 text-[11px] text-brass">
                {result.insufficient.length > 0 && <>Not enough history to evaluate: {result.insufficient.join(", ")}. </>}
                {result.errors.length > 0 && <>Data errors: {result.errors.map((e) => `${e.symbol} (${e.error})`).join("; ")}.</>}
              </p>
            )}
            {result.rows.length === 0 ? (
              <p className="p-6 text-center text-sm text-dim">No symbols match these rules on the latest completed bar.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-line">
                      <th className="th">Symbol</th><th className="th">Name</th><th className="th">Sector</th>
                      <th className="th text-right">Close</th>
                      {result.columns.filter((c) => c !== "close 1D").map((c) => <th key={c} className="th text-right normal-case">{c}</th>)}
                      <th className="th">Bar</th><th className="th">Signal state</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r) => (
                      <tr key={r.symbol} className="border-b border-line/60 hover:bg-raised">
                        <td className="td"><Link className="font-mono font-semibold text-brass hover:underline" href={`/charts?symbol=${r.symbol}`}>{r.symbol}</Link></td>
                        <td className="td max-w-56 truncate">{r.name}</td>
                        <td className="td text-dim">{r.sector ?? "—"}</td>
                        <td className="td num text-right">{price(r.price)}</td>
                        {result.columns.filter((c) => c !== "close 1D").map((c) => <td key={c} className="td num text-right">{num(r.values[c])}</td>)}
                        <td className="td num whitespace-nowrap text-dim">{r.bar_date}</td>
                        <td className="td"><VerificationBadge state={r.verification} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 border-t border-line p-2">
              <input aria-label="Saved scan name" className="input w-56" placeholder="Name this scan to save it" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
              <button className="btn" onClick={save} disabled={!name.trim()}>Save scan</button>
              <span className="ml-auto text-[11px] text-dim">A match is a rule outcome on historical bars, not a recommendation.</span>
            </div>
          </section>
        )}
      </div>

      <aside className="space-y-3">
        <section className="panel" aria-label="Scan templates">
          <div className="panel-title">Templates</div>
          <ul>
            {presets.map((p) => (
              <li key={p.id} className="border-b border-line last:border-0">
                <button className="w-full px-3 py-2 text-left hover:bg-raised" onClick={() => load(p.definition, p.name)}>
                  <div className="text-xs font-semibold">{p.name}</div>
                  <div className="text-[11px] leading-snug text-dim">{p.description}</div>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel" aria-label="Saved scans">
          <div className="panel-title">Saved scans</div>
          {saved.length === 0 && <p className="p-3 text-xs text-dim">Run a scan, then name it to save it here.</p>}
          <ul>
            {saved.map((s) => (
              <li key={s.id} className="flex items-center justify-between border-b border-line px-3 py-1.5 last:border-0">
                <button className="truncate text-left text-xs font-semibold hover:text-brass" onClick={() => load(s.definition, s.name, s.universe)}>{s.name}</button>
                <button aria-label={`Delete saved scan ${s.name}`} className="text-xs text-dim hover:text-down"
                  onClick={() => api.deleteScan(s.id).then(() => setSaved((l) => l.filter((x) => x.id !== s.id))).catch((e) => setError(e.message))}>Delete</button>
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  );
}

export default function Page() {
  return <Suspense><Scanner /></Suspense>;
}

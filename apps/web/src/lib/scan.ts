import type { Condition, IndicatorSpec, Operand, ScanResult } from "./types";

const g = (v: number) => String(Number(v.toPrecision(12)));

/** Mirrors `Operand.label()` in services/market-scanner so UI previews match the result columns. */
export function operandLabel(o: Operand): string {
  if (o.value !== undefined) return g(o.value);
  let base: string;
  if (o.field) base = o.field;
  else {
    const args = Object.values(o.params ?? {}).map((v) => (typeof v === "number" ? g(v) : String(v))).join(",");
    base = `${o.indicator}(${args})${o.output ? `.${o.output}` : ""}`;
  }
  if (o.multiplier && o.multiplier !== 1) base = `${g(o.multiplier)}×${base}`;
  if (o.offset) base += `[${o.offset}]`;
  return `${base} ${o.timeframe ?? "1D"}`;
}

export const conditionLabel = (c: Condition) => `${operandLabel(c.left)} ${c.op.replace("_", " ")} ${operandLabel(c.right)}`;

export function defaultOperand(spec: IndicatorSpec): Operand {
  return {
    indicator: spec.id,
    params: Object.fromEntries(spec.params.filter((p) => p.kind !== "source").map((p) => [p.name, p.default])),
    ...(spec.outputs.length > 1 ? { output: spec.outputs[0]!.name } : {}),
  };
}

function download(name: string, mime: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

const cell = (v: unknown) => {
  const s = v == null ? "" : String(v);
  // Quote when needed, and neutralise spreadsheet formula injection.
  const safe = /^[=+\-@\t\r]/.test(s) && typeof v !== "number" ? `'${s}` : s;
  return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
};

export function exportCsv(result: ScanResult) {
  const head = ["symbol", "name", "sector", "industry", "price", "bar_date", ...result.columns, "verification", "data_status"];
  const rows = result.rows.map((r) =>
    [r.symbol, r.name, r.sector, r.industry, r.price, r.bar_date, ...result.columns.map((c) => r.values[c]), r.verification, r.data_status]
      .map(cell).join(","));
  const note = `# Legion scan · provider=${result.provider} · data=${result.data_status} · as_of=${result.as_of} · ${result.conditions.join(" AND/OR ")}`;
  download("legion-scan.csv", "text/csv", [note, head.join(","), ...rows].join("\n"));
}

export function exportJson(result: ScanResult) {
  download("legion-scan.json", "application/json", JSON.stringify(result, null, 2));
}

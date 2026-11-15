export const price = (x: number | null | undefined) =>
  x == null ? "—" : x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const num = (x: number | null | undefined, digits = 2) =>
  x == null
    ? "—"
    : Math.abs(x) >= 1e6
      ? x.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 })
      : x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const pct = (x: number | null | undefined) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(2)}%`);

export const tone = (x: number | null | undefined) => (x == null || x === 0 ? "text-dim" : x > 0 ? "text-up" : "text-down");

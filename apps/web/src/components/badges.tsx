import type { DataStatus, Verification } from "@/lib/types";

const STATUS: Record<DataStatus, { cls: string; title: string }> = {
  LIVE: { cls: "border-up/50 text-up", title: "Real-time market data" },
  DELAYED: { cls: "border-brass/50 text-brass", title: "Delayed market data" },
  HISTORICAL: { cls: "border-dim/50 text-dim", title: "Completed sessions only" },
  SIMULATED: { cls: "border-sim/60 text-sim", title: "Synthetic demo data — not real market prices" },
};

const VERIFY: Record<Verification, { cls: string; title: string }> = {
  VERIFIED: { cls: "border-up/50 text-up", title: "Required data present and validated" },
  PROVISIONAL: { cls: "border-brass/50 text-brass", title: "Latest inputs incomplete or still forming" },
  UNVERIFIED: { cls: "border-down/50 text-down", title: "Required data or validation missing" },
  SIMULATED: { cls: "border-sim/60 text-sim", title: "Derived from synthetic demo data" },
};

const base = "inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide";

export function StatusBadge({ status }: { status: DataStatus }) {
  const s = STATUS[status];
  return <span className={`${base} ${s.cls}`} title={s.title} data-testid="data-status">{status}</span>;
}

export function VerificationBadge({ state }: { state: Verification }) {
  const s = VERIFY[state];
  return <span className={`${base} ${s.cls}`} title={s.title}>{state}</span>;
}

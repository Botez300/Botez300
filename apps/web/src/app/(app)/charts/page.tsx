"use client";

import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import type { Watchlist } from "@/lib/types";

const ChartPanel = dynamic(() => import("@/components/ChartPanel"), { ssr: false });

function Charts() {
  const params = useSearchParams();
  const router = useRouter();
  const { provider } = useSession();
  const [fallback, setFallback] = useState<string | null>(null);
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const symbol = params.get("symbol")?.toUpperCase() ?? fallback;

  useEffect(() => {
    api.watchlists().then(setLists).catch(() => {});
    if (!params.get("symbol")) api.search("", 1).then((r) => setFallback(r[0]?.symbol ?? null)).catch(() => {});
  }, [params]);

  if (!symbol) {
    return <p className="p-6 text-sm text-dim">
      {provider.can_enumerate_universe ? "Loading…" : "Search for a symbol above to open a chart."}</p>;
  }

  return (
    <div className="flex h-full flex-col gap-3 lg:flex-row">
      <div className="min-h-[520px] min-w-0 flex-1"><ChartPanel symbol={symbol} /></div>
      <aside className="panel w-full shrink-0 lg:w-60" aria-label="Watchlists">
        <div className="panel-title">Watchlists</div>
        {lists.length === 0 && <p className="p-3 text-xs text-dim">No watchlists yet. Create one on the Watchlists page.</p>}
        {lists.map((w) => (
          <div key={w.id} className="border-b border-line p-2 last:border-0">
            <div className="flex items-center justify-between px-1 pb-1 text-xs font-semibold">
              {w.name}
              {!w.symbols.includes(symbol) && (
                <button className="btn px-1.5 py-0.5 text-[10px]" onClick={() =>
                  api.addSymbol(w.id, symbol).then((u) => { setLists((l) => l.map((x) => (x.id === u.id ? u : x))); setNote(null); })
                    .catch((e) => setNote(e.message))}>+ {symbol}</button>
              )}
            </div>
            <ul>
              {w.symbols.map((s) => (
                <li key={s}>
                  <button onClick={() => router.push(`/charts?symbol=${s}`)}
                    className={`w-full rounded px-2 py-1 text-left font-mono text-xs hover:bg-raised ${s === symbol ? "text-brass" : ""}`}>{s}</button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {note && <p role="alert" className="p-3 text-xs text-down">{note}</p>}
      </aside>
    </div>
  );
}

export default function Page() {
  return <Suspense><Charts /></Suspense>;
}

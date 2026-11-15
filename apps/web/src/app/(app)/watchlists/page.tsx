"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { useSession } from "@/components/session";
import { SymbolSearch } from "@/components/SymbolSearch";
import { api } from "@/lib/api";
import type { Watchlist } from "@/lib/types";

export default function WatchlistsPage() {
  const { session } = useSession();
  const [lists, setLists] = useState<Watchlist[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const caps = session.organization.entitlements;

  useEffect(() => { api.watchlists().then(setLists).catch((e) => setError(e.message)); }, []);

  const run = <T,>(p: Promise<T>, then: (v: T) => void) => p.then((v) => { setError(null); then(v); }).catch((e) => setError(e.message));
  const replace = (u: Watchlist) => setLists((l) => (l ?? []).map((x) => (x.id === u.id ? u : x)));

  function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    run(api.createWatchlist(name.trim()), (w) => { setLists((l) => [...(l ?? []), w]); setName(""); });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Watchlists</h1>
          <p className="text-xs text-dim">Saved to your workspace. {lists?.length ?? 0} of {caps.max_watchlists} lists · up to {caps.max_symbols_per_watchlist} symbols each on your plan.</p>
        </div>
        <form onSubmit={create} className="flex gap-2">
          <input aria-label="New watchlist name" className="input w-52" placeholder="New watchlist name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          <button className="btn btn-primary">Create</button>
        </form>
      </div>
      {error && <p role="alert" className="text-xs text-down">{error}</p>}
      {lists === null && !error && <p className="text-xs text-dim">Loading…</p>}
      {lists?.length === 0 && <p className="panel p-6 text-center text-sm text-dim">No watchlists yet. Name one above to get started.</p>}
      <div className="grid gap-3 md:grid-cols-2">
        {lists?.map((w) => (
          <section key={w.id} className="panel" aria-label={`Watchlist ${w.name}`} data-testid="watchlist">
            <div className="panel-title flex items-center justify-between">
              <span>{w.name} · {w.symbols.length}</span>
              <button className="text-dim hover:text-down" onClick={() => {
                if (confirm(`Delete watchlist "${w.name}"?`)) run(api.deleteWatchlist(w.id), () => setLists((l) => (l ?? []).filter((x) => x.id !== w.id)));
              }}>Delete</button>
            </div>
            <div className="p-2">
              <SymbolSearch label={`Add symbol to ${w.name}`} placeholder="Add a symbol" onSelect={(s) => run(api.addSymbol(w.id, s.symbol), replace)} />
            </div>
            {w.symbols.length === 0 && <p className="px-3 pb-3 text-xs text-dim">Empty. Search above to add symbols.</p>}
            <ul>
              {w.symbols.map((s) => (
                <li key={s} className="flex items-center justify-between border-t border-line px-3 py-1.5">
                  <Link href={`/charts?symbol=${s}`} className="font-mono text-xs font-semibold hover:text-brass">{s}</Link>
                  <button aria-label={`Remove ${s} from ${w.name}`} className="text-xs text-dim hover:text-down" onClick={() => run(api.removeSymbol(w.id, s), replace)}>Remove</button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

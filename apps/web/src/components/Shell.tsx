"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { api } from "@/lib/api";

import { StatusBadge } from "./badges";
import { useSession } from "./session";
import { SymbolSearch } from "./SymbolSearch";

const NAV = [
  { href: "/", label: "Command Center" },
  { href: "/charts", label: "Advanced Charts" },
  { href: "/scanner", label: "Market Scanner" },
  { href: "/watchlists", label: "Watchlists" },
];

// Modules on the roadmap. Listed so the product's scope is visible; they are not links because nothing is built yet.
const PLANNED = [
  ["Strategy Lab", "M4"], ["Backtesting", "M4"], ["AI Quant Council", "M5"], ["Paper Trading", "M6"],
  ["Alerts", "M8"], ["Portfolio Analytics", "M6"], ["Subscription", "M7"],
] as const;

export function Shell({ children }: { children: ReactNode }) {
  const { session, provider } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="flex h-full flex-col">
      {provider.data_status === "SIMULATED" && (
        <div role="status" data-testid="demo-banner" className="border-b border-sim/40 bg-sim/10 px-4 py-1 text-center text-[11px] text-sim">
          Demo mode — all symbols, prices and scan results are synthetic. No real market data is shown.
        </div>
      )}
      <header className="flex items-center gap-3 border-b border-line bg-panel px-4 py-2">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-[0.2em]">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M3 2v13h14" fill="none" stroke="#e3b04b" strokeWidth="2.2" strokeLinecap="square" />
            <path d="M7 11l3-4 3 2 4-6" fill="none" stroke="#d9dee7" strokeWidth="1.6" />
          </svg>
          <span>LEGION<span className="text-brass"> QUANT</span></span>
        </Link>
        <div className="mx-auto w-full max-w-md">
          <SymbolSearch globalShortcut onSelect={(s) => router.push(`/charts?symbol=${s.symbol}`)} />
        </div>
        <span className="hidden text-[11px] text-dim sm:inline">Data: {provider.name}</span>
        <StatusBadge status={provider.data_status} />
        <span className="hidden text-xs text-dim md:inline" title={session.user.email}>{session.user.display_name}</span>
        <button className="btn" onClick={() => api.logout().finally(() => router.replace("/login"))}>Sign out</button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <nav aria-label="Primary" className="flex shrink-0 gap-1 overflow-x-auto border-b border-line bg-panel p-2 md:w-52 md:flex-col md:border-b-0 md:border-r">
          {NAV.map((n) => {
            const on = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} aria-current={on ? "page" : undefined}
                className={`whitespace-nowrap rounded px-3 py-2 text-xs font-medium ${on ? "bg-raised text-brass" : "text-text hover:bg-raised"}`}>
                {n.label}
              </Link>
            );
          })}
          <div className="mt-4 hidden md:block">
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-dim">On the roadmap</div>
            <ul>
              {PLANNED.map(([label, milestone]) => (
                <li key={label} className="flex justify-between px-3 py-1 text-[11px] text-dim">
                  <span>{label}</span><span className="font-mono">{milestone}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-auto hidden px-3 pt-4 text-[10px] leading-relaxed text-dim md:block">
            {session.organization.name}<br />Plan: {session.organization.plan.toUpperCase()}<br />
            Research tool. Not investment advice.
          </div>
        </nav>
        <main className="min-h-0 min-w-0 flex-1 overflow-auto p-3 md:p-4">{children}</main>
      </div>
    </div>
  );
}

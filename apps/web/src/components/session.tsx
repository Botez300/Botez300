"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ApiError } from "@/lib/api";
import type { ProviderInfo, Session } from "@/lib/types";

interface Ctx {
  session: Session;
  provider: ProviderInfo;
}

const SessionContext = createContext<Ctx | null>(null);

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ctx, setCtx] = useState<Ctx | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let live = true;
    Promise.all([api.me(), api.provider()])
      .then(([session, provider]) => live && setCtx({ session, provider }))
      .catch((e) => {
        if (!live) return;
        if (e instanceof ApiError && e.status === 401) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        else setError("The Legion API is not reachable. Check that it is running, then reload.");
      });
    return () => { live = false; };
  }, [router, pathname]);

  if (error) return <div role="alert" className="grid h-full place-items-center p-8 text-sm text-down">{error}</div>;
  if (!ctx) return <div className="grid h-full place-items-center text-xs text-dim">Loading workspace…</div>;
  return <SessionContext.Provider value={ctx}>{children}</SessionContext.Provider>;
}

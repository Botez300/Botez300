"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const register = mode === "register";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (register) await api.register(email, password, name);
      else await api.login(email, password);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-full place-items-center p-4">
      <form onSubmit={submit} className="panel w-full max-w-sm p-6" aria-labelledby="auth-title">
        <div className="mb-1 text-sm font-semibold tracking-[0.2em]">LEGION<span className="text-brass"> QUANT</span></div>
        <h1 id="auth-title" className="mb-5 text-lg font-semibold">{register ? "Create your workspace" : "Sign in"}</h1>
        {register && (
          <label className="mb-3 block text-xs text-dim">Name
            <input className="input mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoComplete="name" />
          </label>
        )}
        <label className="mb-3 block text-xs text-dim">Email
          <input className="input mt-1 w-full" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label className="mb-4 block text-xs text-dim">Password{register && " (at least 10 characters)"}
          <input className="input mt-1 w-full" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            required minLength={register ? 10 : 1} autoComplete={register ? "new-password" : "current-password"} />
        </label>
        {error && <p role="alert" className="mb-3 text-xs text-down">{error}</p>}
        <button className="btn btn-primary w-full py-2" disabled={busy}>{busy ? "Working…" : register ? "Create account" : "Sign in"}</button>
        <p className="mt-4 text-center text-xs text-dim">
          {register ? <>Already have an account? <Link className="text-brass" href="/login">Sign in</Link></>
            : <>New here? <Link className="text-brass" href="/register">Create an account</Link></>}
        </p>
      </form>
    </main>
  );
}

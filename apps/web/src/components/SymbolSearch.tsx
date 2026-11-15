"use client";

import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { SymbolInfo } from "@/lib/types";

interface Props {
  onSelect: (symbol: SymbolInfo) => void;
  placeholder?: string;
  /** Focus this input when the user presses "/" anywhere outside a text field. */
  globalShortcut?: boolean;
  label?: string;
}

/** Debounced symbol lookup with a keyboard-navigable listbox (ARIA combobox pattern). */
export function SymbolSearch({ onSelect, placeholder = "Search symbol or company", globalShortcut, label = "Symbol search" }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SymbolInfo[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const closing = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    let live = true;
    setLoading(true);
    const timer = setTimeout(() => {
      api.search(query.trim())
        .then((r) => { if (live) { setResults(r); setActive(0); setFailed(false); } })
        .catch(() => live && setFailed(true))
        .finally(() => live && setLoading(false));
    }, 120);
    return () => { live = false; clearTimeout(timer); };
  }, [query, open]);

  useEffect(() => {
    if (!globalShortcut) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if ((e.key === "/" && !typing) || (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey))) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [globalShortcut]);

  const choose = (s: SymbolInfo | undefined) => {
    if (!s) return;
    onSelect(s);
    setQuery("");
    setResults([]);
    setOpen(false);
    input.current?.blur();
  };

  return (
    <div className="relative">
      <input
        ref={input}
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
        className="input w-full"
        placeholder={globalShortcut ? `${placeholder}  ( / )` : placeholder}
        value={query}
        onChange={(e) => { clearTimeout(closing.current); setQuery(e.target.value); setOpen(true); }}
        onFocus={() => { clearTimeout(closing.current); setOpen(true); }}
        onBlur={() => { closing.current = setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter") { e.preventDefault(); choose(results[active]); }
          else if (e.key === "Escape") { setOpen(false); input.current?.blur(); }
        }}
      />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-30 mt-1 max-h-80 w-full min-w-72 overflow-auto rounded-md border border-line bg-raised py-1 shadow-xl">
          {failed && <li className="px-3 py-2 text-xs text-down">Search failed. Try again.</li>}
          {!failed && results.length === 0 && <li className="px-3 py-2 text-xs text-dim">{loading ? "Searching…" : "No matching symbols"}</li>}
          {results.map((s, i) => (
            <li
              key={s.symbol}
              role="option"
              aria-selected={i === active}
              className={`flex cursor-pointer items-baseline gap-2 px-3 py-1.5 text-xs ${i === active ? "bg-line" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => { e.preventDefault(); choose(s); }}
            >
              <span className="w-14 shrink-0 font-mono font-semibold text-brass">{s.symbol}</span>
              <span className="truncate">{s.name}</span>
              <span className="ml-auto shrink-0 text-[10px] uppercase text-dim">{s.exchange} · {s.asset_type}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

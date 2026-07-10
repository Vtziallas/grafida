"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

const KIND: Record<string, string> = {
  document: "Έγγραφο", evidence: "Σχετικό", sample: "Δείγμα ύφους" };

type R = { kind: string; ref_id: number; case_id: number | null;
           snippet: string; score: number };

export default function Search() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<R[]>([]);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  return (
    <div>
      <form className="mb-4 flex gap-2" onSubmit={async e => { e.preventDefault();
        setErr("");
        try {
          setRows(await (await api(
            `/api/search?q=${encodeURIComponent(q)}`)).json());
          setDone(true);
        } catch (x) { setErr((x as Error).message); } }}>
        <input className="flex-1 rounded border border-gray-300 p-2"
          placeholder="Αναζήτηση σε υποθέσεις, έγγραφα, δείγματα…"
          value={q} onChange={e => setQ(e.target.value)} />
        <button className="rounded bg-indigo-600 px-4 text-white">Αναζήτηση</button>
      </form>
      {err && <p className="mb-2 text-sm text-red-600">{err}</p>}
      {done && rows.length === 0 &&
        <p className="text-gray-500">Δεν βρέθηκε σχετικό υλικό στο αρχείο σας.</p>}
      {rows.map((r, i) => (
        <div key={i} className="mb-2 rounded border border-gray-200 bg-white p-3 text-sm">
          <span className="mr-2 rounded bg-gray-100 px-2 py-0.5 text-xs">
            {KIND[r.kind] ?? r.kind}</span>
          {r.case_id &&
            <Link className="text-indigo-700 underline"
                  href={`/cases/${r.case_id}`}>Υπόθεση #{r.case_id}</Link>}
          <p className="mt-1 text-gray-600">…{r.snippet}…</p>
        </div>))}
    </div>
  );
}

"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { Btn, Card, ErrorNote, Input, PageTitle } from "@/components/ui";

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
      <PageTitle>Αναζήτηση</PageTitle>
      <form className="mb-4 flex gap-3" onSubmit={async e => { e.preventDefault();
        setErr("");
        try {
          setRows(await (await api(
            `/api/search?q=${encodeURIComponent(q)}`)).json());
          setDone(true);
        } catch (x) { setErr((x as Error).message); } }}>
        <Input className="flex-1" value={q} onChange={e => setQ(e.target.value)}
          placeholder="Αναζήτηση σε υποθέσεις, έγγραφα, δείγματα…" />
        <Btn>Αναζήτηση</Btn>
      </form>
      <div className="mb-3"><ErrorNote>{err}</ErrorNote></div>
      {done && rows.length === 0 &&
        <p className="text-sm text-ink-2">Δεν βρέθηκε σχετικό υλικό στο αρχείο σας.</p>}
      <div className="space-y-2">
        {rows.map((r, i) => (
          <Card key={i} className="!p-4 text-sm">
            <span className="mr-2 rounded-full bg-canvas px-2.5 py-0.5 text-xs text-ink-2">
              {KIND[r.kind] ?? r.kind}</span>
            {r.case_id &&
              <Link className="text-accent hover:underline"
                    href={`/cases/${r.case_id}`}>Υπόθεση #{r.case_id}</Link>}
            <p className="mt-2 text-ink-2">…{r.snippet}…</p>
          </Card>))}
      </div>
    </div>
  );
}

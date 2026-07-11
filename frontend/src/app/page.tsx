"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BtnGhost, Card, PageTitle, SectionTitle } from "@/components/ui";

type Dash = {
  open_cases: { id: number; title: string; next_action: string }[];
  pending_drafts: { document_id: number; title: string; status: string }[];
};
type Dl = { id: number; case_id: number; case_title: string; title: string;
            due_date: string; days_left: number; completed: boolean };

function urgency(d: Dl) {
  if (d.completed) return { label: "ολοκληρώθηκε", cls: "text-ink-2", dot: "bg-hairline" };
  if (d.days_left < 0) return { label: "εκπρόθεσμη", cls: "text-danger", dot: "bg-danger" };
  if (d.days_left <= 3) return { label: `σε ${d.days_left} ημ.`, cls: "text-danger", dot: "bg-danger" };
  if (d.days_left <= 7) return { label: `σε ${d.days_left} ημ.`, cls: "text-warn", dot: "bg-warn" };
  return { label: `σε ${d.days_left} ημ.`, cls: "text-ink-2", dot: "bg-ok" };
}

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  const [dls, setDls] = useState<Dl[]>([]);
  const load = useCallback(() => {
    api("/api/dashboard").then(r => r.json()).then(setD);
    api("/api/deadlines").then(r => r.json()).then(setDls);
  }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <p className="text-ink-2">Φόρτωση…</p>;
  const open = dls.filter(x => !x.completed);
  const done = dls.filter(x => x.completed);
  return (
    <div>
      <PageTitle sub="Οι προθεσμίες σας με μια ματιά — καταχωρισμένες και επιβεβαιωμένες από εσάς.">
        Η μέρα μου</PageTitle>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle>Όλες οι προθεσμίες</SectionTitle>
          {open.length === 0 &&
            <p className="text-sm text-ink-2">Καμία εκκρεμής προθεσμία. Προσθέστε
              προθεσμίες μέσα από κάθε υπόθεση.</p>}
          <ul>
            {open.map(x => { const u = urgency(x); return (
              <li key={x.id}
                  className="flex items-center gap-3 border-b border-hairline/50 py-3 last:border-0">
                <span className={`h-2 w-2 shrink-0 rounded-full ${u.dot}`} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{x.title}</p>
                  <p className="truncate text-xs text-ink-2">
                    {x.due_date} ·{" "}
                    <Link className="text-accent hover:underline"
                          href={`/cases/${x.case_id}`}>{x.case_title}</Link>
                  </p>
                </div>
                <span className={`text-xs font-medium ${u.cls}`}>{u.label}</span>
                <BtnGhost className="!px-3 !py-1 text-xs" onClick={() =>
                  api(`/api/deadlines/${x.id}/complete`, { method: "POST" })
                    .then(load)}>Ολοκληρώθηκε</BtnGhost>
              </li>); })}
          </ul>
          {done.length > 0 &&
            <p className="mt-3 text-xs text-ink-2">
              {done.length} ολοκληρωμένες προθεσμίες</p>}
        </Card>
        <div className="space-y-4">
          <Card>
            <SectionTitle>Ανοιχτές υποθέσεις</SectionTitle>
            <ul className="space-y-2 text-sm">
              {d.open_cases.map(c => (
                <li key={c.id}>
                  <Link className="font-medium text-accent hover:underline"
                        href={`/cases/${c.id}`}>{c.title}</Link>
                  {c.next_action &&
                    <p className="text-xs text-ink-2">{c.next_action}</p>}
                </li>))}
              {d.open_cases.length === 0 &&
                <li className="text-ink-2">Καμία ανοιχτή υπόθεση.</li>}
            </ul>
          </Card>
          <Card>
            <SectionTitle>Προσχέδια σε εκκρεμότητα</SectionTitle>
            <ul className="space-y-2 text-sm">
              {d.pending_drafts.map(p => (
                <li key={p.document_id}>
                  <Link className="text-accent hover:underline"
                        href={`/drafts/${p.document_id}`}>{p.title}</Link>
                </li>))}
              {d.pending_drafts.length === 0 &&
                <li className="text-ink-2">Κανένα προσχέδιο σε εκκρεμότητα.</li>}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

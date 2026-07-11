"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, PageTitle, SectionTitle } from "@/components/ui";

type Detail = {
  id: number; name: string; afm?: string; id_number?: string; email?: string;
  phone?: string; notes: string;
  cases: { id: number; title: string; status: string; court_name: string;
           next_action: string }[];
};

export default function ClientPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [d, setD] = useState<Detail | null>(null);
  useEffect(() => {
    api(`/api/clients/${id}`).then(r => r.json()).then(setD);
  }, [id]);
  if (!d) return <p className="text-ink-2">Φόρτωση…</p>;
  const fields: [string, string | undefined][] = [
    ["Τηλέφωνο", d.phone], ["Email", d.email], ["ΑΔΤ", d.id_number],
    ["ΑΦΜ", d.afm]];
  return (
    <div>
      <PageTitle sub={d.notes || undefined}>{d.name}</PageTitle>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <SectionTitle>Στοιχεία</SectionTitle>
          <dl className="space-y-2 text-sm">
            {fields.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4">
                <dt className="text-ink-2">{k}</dt>
                <dd className="font-medium text-ink">{v || "—"}</dd>
              </div>))}
          </dl>
        </Card>
        <Card className="lg:col-span-2">
          <SectionTitle>Υποθέσεις ({d.cases.length})</SectionTitle>
          <ul>
            {d.cases.map(k => (
              <li key={k.id} className="border-b border-hairline/50 last:border-0">
                <Link href={`/cases/${k.id}`}
                  className="flex items-center gap-4 py-3 transition-colors hover:bg-canvas/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{k.title}</p>
                    <p className="truncate text-xs text-ink-2">
                      {k.court_name || "χωρίς δικαστήριο"}
                      {k.next_action && ` · ${k.next_action}`}</p>
                  </div>
                  <span className="text-xs text-ink-2">
                    {k.status === "open" ? "ανοιχτή" : "κλειστή"}</span>
                  <span className="text-xs text-accent">›</span>
                </Link>
              </li>))}
          </ul>
          {d.cases.length === 0 &&
            <p className="text-sm text-ink-2">Καμία υπόθεση για αυτόν τον πελάτη —
              δημιουργήστε μία από τις «Υποθέσεις».</p>}
        </Card>
      </div>
    </div>
  );
}

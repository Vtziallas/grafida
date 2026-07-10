"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Dash = {
  open_cases: { id: number; title: string; next_action: string }[];
  deadlines: { id: number; case_id: number; case_title: string; title: string;
               due_date: string }[];
  pending_drafts: { document_id: number; title: string; status: string }[];
};

function daysUntil(iso: string) {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
}

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  useEffect(() => { api("/api/dashboard").then(r => r.json()).then(setD); }, []);
  if (!d) return <p>Φόρτωση…</p>;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Ανοιχτές υποθέσεις</h2>
        <ul className="space-y-1 text-sm">
          {d.open_cases.map(c => (
            <li key={c.id}>
              <Link className="text-indigo-700 underline"
                    href={`/cases/${c.id}`}>{c.title}</Link>
              {c.next_action &&
                <span className="text-gray-500"> — {c.next_action}</span>}
            </li>))}
          {d.open_cases.length === 0 &&
            <li className="text-gray-500">Καμία ανοιχτή υπόθεση.</li>}
        </ul>
      </section>
      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Προθεσμίες 14 ημερών</h2>
        <ul className="space-y-1 text-sm">
          {d.deadlines.map(dl => (
            <li key={dl.id}
                className={daysUntil(dl.due_date) <= 3 ? "text-red-600" : ""}>
              {dl.due_date} — {dl.title}{" "}
              <Link className="text-indigo-700 underline"
                    href={`/cases/${dl.case_id}`}>{dl.case_title}</Link>
            </li>))}
          {d.deadlines.length === 0 &&
            <li className="text-gray-500">Καμία προθεσμία στο διάστημα.</li>}
        </ul>
      </section>
      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Προσχέδια σε εκκρεμότητα</h2>
        <ul className="space-y-1 text-sm">
          {d.pending_drafts.map(p => (
            <li key={p.document_id}>
              <Link className="text-indigo-700 underline"
                    href={`/drafts/${p.document_id}`}>{p.title}</Link>
            </li>))}
          {d.pending_drafts.length === 0 &&
            <li className="text-gray-500">Κανένα προσχέδιο σε εκκρεμότητα.</li>}
        </ul>
      </section>
    </div>
  );
}

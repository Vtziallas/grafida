"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Btn, Card, Input, PageTitle, SectionTitle } from "@/components/ui";

type K = { id: number; title: string; status: string; court_name: string;
           next_action: string };
type C = { id: number; name: string };

export default function Cases() {
  const [rows, setRows] = useState<K[]>([]);
  const [clients, setClients] = useState<C[]>([]);
  const [title, setTitle] = useState("");
  const [clientId, setClientId] = useState("");
  const load = () => api("/api/cases").then(r => r.json()).then(setRows);
  useEffect(() => { load();
    api("/api/clients").then(r => r.json()).then(setClients); }, []);
  return (
    <div>
      <PageTitle>Υποθέσεις</PageTitle>
      <Card className="mb-4">
        <SectionTitle>Νέα υπόθεση</SectionTitle>
        <form className="flex flex-wrap gap-3" onSubmit={async e => {
          e.preventDefault();
          if (!title.trim() || !clientId) return;
          await api("/api/cases", { method: "POST",
            body: JSON.stringify({ client_id: Number(clientId), title }) });
          setTitle(""); load(); }}>
          <select className="rounded-xl border border-hairline bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
                  value={clientId} onChange={e => setClientId(e.target.value)}>
            <option value="">Πελάτης…</option>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Input className="flex-1" placeholder="Τίτλος υπόθεσης" value={title}
                 onChange={e => setTitle(e.target.value)} />
          <Btn>Δημιουργία</Btn>
        </form>
      </Card>
      <Card>
        <ul>
          {rows.map(k => (
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
        {rows.length === 0 &&
          <p className="text-sm text-ink-2">Δεν υπάρχουν υποθέσεις ακόμη.</p>}
      </Card>
    </div>
  );
}

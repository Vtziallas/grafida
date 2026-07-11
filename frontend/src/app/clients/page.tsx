"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Btn, Card, Input, PageTitle, SectionTitle } from "@/components/ui";

type C = { id: number; name: string; afm?: string; phone?: string; email?: string };

const EMPTY = { name: "", phone: "", id_number: "", email: "", afm: "", notes: "" };

export default function Clients() {
  const [rows, setRows] = useState<C[]>([]);
  const [f, setF] = useState({ ...EMPTY });
  const load = () => api("/api/clients").then(r => r.json()).then(setRows);
  useEffect(() => { load(); }, []);
  const set = (k: keyof typeof EMPTY) =>
    (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div>
      <PageTitle>Πελάτες</PageTitle>
      <Card className="mb-4">
        <SectionTitle>Νέος πελάτης</SectionTitle>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={async e => {
          e.preventDefault();
          if (!f.name.trim()) return;
          await api("/api/clients", { method: "POST", body: JSON.stringify({
            name: f.name, phone: f.phone || null, id_number: f.id_number || null,
            email: f.email || null, afm: f.afm || null, notes: f.notes }) });
          setF({ ...EMPTY }); load(); }}>
          <Input placeholder="Ονοματεπώνυμο *" value={f.name} onChange={set("name")} />
          <Input placeholder="Τηλέφωνο" value={f.phone} onChange={set("phone")} />
          <Input placeholder="ΑΔΤ (ταυτότητα)" value={f.id_number}
                 onChange={set("id_number")} />
          <Input placeholder="Email" value={f.email} onChange={set("email")} />
          <Input placeholder="ΑΦΜ" value={f.afm} onChange={set("afm")} />
          <Input placeholder="Σημειώσεις" value={f.notes} onChange={set("notes")} />
          <div className="sm:col-span-2">
            <Btn>Προσθήκη πελάτη</Btn>
          </div>
        </form>
      </Card>
      <Card>
        <ul>
          {rows.map(c => (
            <li key={c.id} className="border-b border-hairline/50 last:border-0">
              <Link href={`/clients/${c.id}`}
                className="flex items-center gap-4 py-3 transition-colors hover:bg-canvas/60">
                <span className="flex-1 text-sm font-medium text-ink">{c.name}</span>
                <span className="text-xs text-ink-2">{c.phone ?? ""}</span>
                <span className="text-xs text-ink-2">{c.email ?? ""}</span>
                <span className="text-xs text-accent">Προβολή ›</span>
              </Link>
            </li>))}
        </ul>
        {rows.length === 0 &&
          <p className="text-sm text-ink-2">Δεν υπάρχουν πελάτες ακόμη —
            προσθέστε τον πρώτο από τη φόρμα.</p>}
      </Card>
    </div>
  );
}

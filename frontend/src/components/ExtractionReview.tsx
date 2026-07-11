"use client";
import { api } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";

const KIND: Record<string, string> = {
  date: "Ημερομηνία", amount: "Ποσό", claim: "Αίτημα", other: "Άλλο" };

type Party = { id: number; name: string; role: string; source_quote: string;
               confidence: number; confirmed: boolean };
type Fact = { id: number; kind: string; value: string | null; description: string;
              source_quote: string; confidence: number; confirmed: boolean;
              conflict_group: number | null };

function Row({ label, quote, conf, confirmed, warn, onOk }: {
  label: string; quote: string; conf: number; confirmed: boolean;
  warn: boolean; onOk: () => void }) {
  return (
    <div className={`flex items-center gap-3 rounded-xl px-2 py-2.5 text-sm
        ${warn ? "bg-warn/10" : ""}`}>
      <div className="min-w-0 flex-1">
        <p className="text-ink">{label}</p>
        <p className="truncate text-xs text-ink-2">
          πηγή: «{quote || "—"}» · βεβαιότητα {(conf * 100).toFixed(0)}%</p>
      </div>
      {confirmed
        ? <span className="shrink-0 text-xs font-medium text-ok">✓ Επιβεβαιώθηκε</span>
        : <button onClick={onOk}
            className="shrink-0 rounded-full bg-ok px-3 py-1 text-xs font-medium text-white hover:opacity-90">
            Επιβεβαίωση</button>}
    </div>);
}

export default function ExtractionReview({ d, onChange }:
    { d: { parties: Party[]; facts: Fact[] }; onChange: () => void }) {
  const confirm = (kind: "parties" | "facts", id: number) =>
    api(`/api/${kind === "parties" ? "parties" : "facts"}/${id}`, {
      method: "PATCH", body: JSON.stringify({ confirmed_by_lawyer: true }),
    }).then(onChange);
  return (
    <Card>
      <SectionTitle>Έλεγχος εξαγωγής</SectionTitle>
      <p className="mb-3 text-xs text-ink-2">
        Επιβεβαιώστε κάθε στοιχείο — μόνο επιβεβαιωμένα στοιχεία
        χρησιμοποιούνται στη σύνταξη.</p>
      <div className="divide-y divide-hairline/50">
        {d.parties.map(p => (
          <Row key={`p${p.id}`} label={`Διάδικος: ${p.name} (${p.role})`}
               quote={p.source_quote} conf={p.confidence} confirmed={p.confirmed}
               warn={p.confidence < 0.8} onOk={() => confirm("parties", p.id)} />))}
        {d.facts.map(f => (
          <Row key={`f${f.id}`}
               label={`${KIND[f.kind] ?? f.kind}: ${f.value ?? "—"} · ${f.description}`
                      + (f.conflict_group != null ? " ⚠ ΣΥΓΚΡΟΥΣΗ" : "")}
               quote={f.source_quote} conf={f.confidence} confirmed={f.confirmed}
               warn={f.confidence < 0.8 || f.conflict_group != null}
               onOk={() => confirm("facts", f.id)} />))}
      </div>
    </Card>
  );
}

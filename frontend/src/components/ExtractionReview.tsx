"use client";
import { api } from "@/lib/api";

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
    <div className={`flex items-center gap-3 border-b border-gray-100 py-2 text-sm
        ${warn ? "bg-amber-50" : ""}`}>
      <div className="flex-1">
        <div>{label}</div>
        <div className="text-xs text-gray-500">
          πηγή: «{quote || "—"}» · βεβαιότητα {(conf * 100).toFixed(0)}%</div>
      </div>
      {confirmed
        ? <span className="text-green-700">✓ Επιβεβαιώθηκε</span>
        : <button className="rounded bg-green-600 px-3 py-1 text-white"
                  onClick={onOk}>Επιβεβαίωση</button>}
    </div>);
}

export default function ExtractionReview({ d, onChange }:
    { d: { parties: Party[]; facts: Fact[] }; onChange: () => void }) {
  const confirm = (kind: "parties" | "facts", id: number) =>
    api(`/api/${kind === "parties" ? "parties" : "facts"}/${id}`, {
      method: "PATCH", body: JSON.stringify({ confirmed_by_lawyer: true }),
    }).then(onChange);
  return (
    <section className="rounded border border-gray-200 bg-white p-4">
      <h2 className="mb-1 font-semibold">Έλεγχος εξαγωγής</h2>
      <p className="mb-3 text-xs text-gray-500">
        Επιβεβαιώστε κάθε στοιχείο — μόνο επιβεβαιωμένα στοιχεία
        χρησιμοποιούνται στη σύνταξη.</p>
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
    </section>
  );
}

"use client";
import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiForm } from "@/lib/api";
import ExtractionReview from "@/components/ExtractionReview";

type CaseDetail = {
  id: number; title: string; court_name: string; facts_text: string;
  client: { id: number; name: string };
  parties: { id: number; name: string; role: string; source_quote: string;
             confidence: number; confirmed: boolean }[];
  facts: { id: number; kind: string; value: string | null; description: string;
           source_quote: string; confidence: number; confirmed: boolean;
           conflict_group: number | null }[];
  deadlines: { id: number; title: string; due_date: string; completed: boolean }[];
  documents: { id: number; title: string; status: string; type: string }[];
  evidence: { id: number; exhibit_number: number; description: string;
              ocr_pending: boolean }[];
  document_types: { id: number; name: string }[];
};

const STATUS: Record<string, string> = {
  draft: "προσχέδιο", approved: "εγκεκριμένο", exported: "εξήχθη" };

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [d, setD] = useState<CaseDetail | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [typeId, setTypeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [dlTitle, setDlTitle] = useState("");
  const [dlDate, setDlDate] = useState("");
  const reload = () => api(`/api/cases/${id}`).then(r => r.json()).then(setD);
  useEffect(() => { reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);
  if (!d) return <p>Φόρτωση…</p>;
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold">{d.title}
        <span className="ml-2 text-sm font-normal text-gray-500">
          {d.client.name} · {d.court_name || "χωρίς δικαστήριο"}</span></h1>
      {err && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}

      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Γεγονότα υπόθεσης</h2>
        <textarea className="w-full rounded border border-gray-300 p-2" rows={5}
          defaultValue={d.facts_text}
          onBlur={e => api(`/api/cases/${id}`, { method: "PATCH",
            body: JSON.stringify({ facts_text: e.target.value }) })} />
        <button className="mt-2 rounded bg-indigo-600 px-4 py-1 text-white disabled:opacity-40"
          disabled={busy}
          onClick={async () => { setBusy(true); setErr("");
            try { await api(`/api/cases/${id}/extract`, { method: "POST" });
                  await reload(); }
            catch (x) { setErr((x as Error).message); }
            finally { setBusy(false); } }}>
          {busy ? "Εξαγωγή…" : "Εξαγωγή στοιχείων με AI"}</button>
      </section>

      {(d.parties.length > 0 || d.facts.length > 0) &&
        <ExtractionReview d={d} onChange={reload} />}

      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Σχετικά</h2>
        <ul className="mb-3 text-sm">{d.evidence.map(ev => (
          <li key={ev.id}>Σχετικό {ev.exhibit_number}: {ev.description}
            {ev.ocr_pending && <span className="ml-2 text-amber-600">
              OCR εκκρεμεί — δεν αναγνώστηκε κείμενο</span>}</li>))}</ul>
        <form className="flex items-center gap-2" onSubmit={async e => { e.preventDefault();
          if (!file) return;
          const f = new FormData(); f.append("file", file);
          f.append("description", file.name);
          setErr("");
          try { await apiForm(`/api/cases/${id}/evidence`, f); }
          catch (x) { setErr((x as Error).message); }
          setFile(null); (e.target as HTMLFormElement).reset(); reload(); }}>
          <input type="file" accept=".pdf,.docx,.txt" className="text-sm"
                 onChange={e => setFile(e.target.files?.[0] ?? null)} />
          <button className="rounded bg-gray-800 px-3 py-1 text-sm text-white">
            Μεταφόρτωση</button>
        </form>
      </section>

      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Προθεσμίες</h2>
        <ul className="mb-3 text-sm">{d.deadlines.map(dl => (
          <li key={dl.id}>{dl.due_date} — {dl.title}
            {dl.completed && " ✓"}</li>))}</ul>
        <form className="flex gap-2" onSubmit={async e => { e.preventDefault();
          if (!dlTitle.trim() || !dlDate) return;
          await api(`/api/cases/${id}/deadlines`, { method: "POST",
            body: JSON.stringify({ title: dlTitle, due_date: dlDate }) });
          setDlTitle(""); setDlDate(""); reload(); }}>
          <input type="date" className="rounded border border-gray-300 p-1 text-sm"
                 value={dlDate} onChange={e => setDlDate(e.target.value)} />
          <input className="flex-1 rounded border border-gray-300 p-1 text-sm"
                 placeholder="Περιγραφή (η προθεσμία επιβεβαιώνεται από εσάς)"
                 value={dlTitle} onChange={e => setDlTitle(e.target.value)} />
          <button className="rounded bg-gray-800 px-3 py-1 text-sm text-white">
            Προσθήκη</button>
        </form>
      </section>

      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Έγγραφα</h2>
        <ul className="mb-3 text-sm">{d.documents.map(doc => (
          <li key={doc.id}>
            <a className="text-indigo-700 underline" href={`/drafts/${doc.id}`}>
              {doc.title}</a> — {doc.type} ({STATUS[doc.status] ?? doc.status})</li>))}</ul>
        <div className="flex gap-2">
          <select className="rounded border border-gray-300 p-2" value={typeId}
                  onChange={e => setTypeId(e.target.value)}>
            <option value="">Τύπος εγγράφου…</option>
            {d.document_types.map(t =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button className="rounded bg-indigo-600 px-4 py-1 text-white"
            onClick={async () => {
              if (!typeId) return;
              setErr("");
              const tname = d.document_types.find(t => String(t.id) === typeId)?.name;
              try {
                const r = await api(`/api/cases/${id}/documents`, { method: "POST",
                  body: JSON.stringify({ type_id: Number(typeId),
                    title: `${tname} — ${d.title}` }) });
                router.push(`/drafts/${(await r.json()).id}`);
              } catch (x) { setErr((x as Error).message); } }}>
            Νέο έγγραφο με AI</button>
        </div>
      </section>
    </div>
  );
}

"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, apiForm } from "@/lib/api";
import ExtractionReview from "@/components/ExtractionReview";
import { Btn, BtnGhost, Card, ErrorNote, Input, PageTitle, SectionTitle } from "@/components/ui";

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
  if (!d) return <p className="text-ink-2">Φόρτωση…</p>;
  return (
    <div className="space-y-4">
      <PageTitle sub={<>
        <Link className="text-accent hover:underline"
              href={`/clients/${d.client.id}`}>{d.client.name}</Link>
        {" · "}{d.court_name || "χωρίς δικαστήριο"}</>}>
        {d.title}</PageTitle>
      <ErrorNote>{err}</ErrorNote>

      <Card>
        <SectionTitle>Γεγονότα υπόθεσης</SectionTitle>
        <textarea rows={5}
          className="w-full rounded-xl border border-hairline bg-surface p-3 text-sm text-ink focus:border-accent focus:outline-none"
          defaultValue={d.facts_text}
          onBlur={e => api(`/api/cases/${id}`, { method: "PATCH",
            body: JSON.stringify({ facts_text: e.target.value }) })} />
        <Btn className="mt-3" disabled={busy}
          onClick={async () => { setBusy(true); setErr("");
            try { await api(`/api/cases/${id}/extract`, { method: "POST" });
                  await reload(); }
            catch (x) { setErr((x as Error).message); }
            finally { setBusy(false); } }}>
          {busy ? "Εξαγωγή…" : "Εξαγωγή στοιχείων με AI"}</Btn>
      </Card>

      {(d.parties.length > 0 || d.facts.length > 0) &&
        <ExtractionReview d={d} onChange={reload} />}

      <Card>
        <SectionTitle>Σχετικά</SectionTitle>
        <ul className="mb-3 space-y-1 text-sm text-ink">
          {d.evidence.map(ev => (
            <li key={ev.id}>Σχετικό {ev.exhibit_number}: {ev.description}
              {ev.ocr_pending && <span className="ml-2 text-xs text-warn">
                OCR εκκρεμεί — δεν αναγνώστηκε κείμενο</span>}</li>))}
          {d.evidence.length === 0 &&
            <li className="text-ink-2">Κανένα σχετικό ακόμη.</li>}
        </ul>
        <form className="flex items-center gap-3" onSubmit={async e => {
          e.preventDefault();
          if (!file) return;
          const f = new FormData(); f.append("file", file);
          f.append("description", file.name);
          setErr("");
          try { await apiForm(`/api/cases/${id}/evidence`, f); }
          catch (x) { setErr((x as Error).message); }
          setFile(null); (e.target as HTMLFormElement).reset(); reload(); }}>
          <input type="file" accept=".pdf,.docx,.txt" className="text-sm text-ink-2"
                 onChange={e => setFile(e.target.files?.[0] ?? null)} />
          <BtnGhost>Μεταφόρτωση</BtnGhost>
        </form>
      </Card>

      <Card>
        <SectionTitle>Προθεσμίες</SectionTitle>
        <ul className="mb-3 space-y-1 text-sm text-ink">
          {d.deadlines.map(dl => (
            <li key={dl.id}>{dl.due_date} — {dl.title}{dl.completed && " ✓"}</li>))}
          {d.deadlines.length === 0 &&
            <li className="text-ink-2">Καμία προθεσμία — καταχωρίστε και
              επιβεβαιώστε εσείς κάθε προθεσμία.</li>}
        </ul>
        <form className="flex flex-wrap gap-3" onSubmit={async e => {
          e.preventDefault();
          if (!dlTitle.trim() || !dlDate) return;
          await api(`/api/cases/${id}/deadlines`, { method: "POST",
            body: JSON.stringify({ title: dlTitle, due_date: dlDate }) });
          setDlTitle(""); setDlDate(""); reload(); }}>
          <Input type="date" value={dlDate}
                 onChange={e => setDlDate(e.target.value)} />
          <Input className="flex-1" placeholder="Περιγραφή προθεσμίας"
                 value={dlTitle} onChange={e => setDlTitle(e.target.value)} />
          <BtnGhost>Προσθήκη</BtnGhost>
        </form>
      </Card>

      <Card>
        <SectionTitle>Έγγραφα</SectionTitle>
        <ul className="mb-3 space-y-1 text-sm">
          {d.documents.map(doc => (
            <li key={doc.id}>
              <Link className="text-accent hover:underline"
                    href={`/drafts/${doc.id}`}>{doc.title}</Link>
              <span className="text-ink-2"> — {doc.type} ({STATUS[doc.status] ?? doc.status})</span>
            </li>))}
          {d.documents.length === 0 &&
            <li className="text-ink-2">Κανένα έγγραφο ακόμη.</li>}
        </ul>
        <div className="flex flex-wrap gap-3">
          <select className="rounded-xl border border-hairline bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
                  value={typeId} onChange={e => setTypeId(e.target.value)}>
            <option value="">Τύπος εγγράφου…</option>
            {d.document_types.map(t =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <Btn onClick={async () => {
              if (!typeId) return;
              setErr("");
              const tname = d.document_types.find(t => String(t.id) === typeId)?.name;
              try {
                const r = await api(`/api/cases/${id}/documents`, { method: "POST",
                  body: JSON.stringify({ type_id: Number(typeId),
                    title: `${tname} — ${d.title}` }) });
                router.push(`/drafts/${(await r.json()).id}`);
              } catch (x) { setErr((x as Error).message); } }}>
            Νέο έγγραφο με AI</Btn>
        </div>
      </Card>
    </div>
  );
}

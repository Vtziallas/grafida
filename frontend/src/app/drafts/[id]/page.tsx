"use client";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { API, api } from "@/lib/api";

type Item = { id: number; severity: string; text: string; source_agent: string;
              status: string; anchor_quote: string; override_note: string };
type Doc = {
  id: number; title: string; status: string; case_id: number; type: string;
  draft: { status: string; error: string;
           uncertainty_report: Record<string, number>;
           inputs_manifest: Record<string, unknown> };
  content: string; version_no: number; checklist: Item[];
};

export default function DraftPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [d, setD] = useState<Doc | null>(null);
  const [content, setContent] = useState("");
  const [attest, setAttest] = useState(false);
  const [note, setNote] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    const j: Doc = await (await api(`/api/documents/${id}`)).json();
    setD(j); setContent(j.content);
    if (j.draft.status === "running")
      timer.current = setTimeout(load, 2000);
  }, [id]);
  useEffect(() => { load();
    return () => { if (timer.current) clearTimeout(timer.current); }; }, [load]);

  if (!d) return <p>Φόρτωση…</p>;
  if (d.draft.status === "running")
    return <p className="animate-pulse">Το AI συντάσσει το προσχέδιο…
      (τοπικό μοντέλο — μπορεί να διαρκέσει λίγα λεπτά)</p>;
  if (d.draft.status === "failed")
    return <p className="rounded bg-red-50 p-3 text-red-700">{d.draft.error}</p>;

  const reds = d.checklist.filter(i =>
    i.severity === "red" && i.status === "open" && i.source_agent !== "attestation");
  const rep = d.draft.uncertainty_report;
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2">
        {d.status === "draft" &&
          <div className="mb-2 rounded bg-amber-100 p-2 text-sm">
            Προσχέδιο AI — απαιτείται έλεγχος δικηγόρου</div>}
        <h1 className="mb-2 font-bold">{d.title}</h1>
        {msg && <p className="mb-2 rounded bg-red-50 p-2 text-sm text-red-700">{msg}</p>}
        <textarea className="h-[60vh] w-full rounded border border-gray-300 p-3 font-serif"
          value={content} onChange={e => setContent(e.target.value)}
          disabled={d.status !== "draft"} />
        <div className="mt-2 flex gap-2">
          {d.status === "draft" && <>
            <button className="rounded bg-gray-800 px-4 py-1 text-white"
              onClick={() => api(`/api/documents/${id}/versions`, {
                method: "POST", body: JSON.stringify({ content }) }).then(load)}>
              Αποθήκευση</button>
            <button className="rounded bg-green-700 px-4 py-1 text-white disabled:opacity-40"
              disabled={reds.length > 0 || !attest}
              onClick={async () => { setMsg("");
                try {
                  await api(`/api/documents/${id}/approve`, { method: "POST",
                    body: JSON.stringify({ attestation: true }) });
                  load();
                } catch (x) { setMsg((x as Error).message); } }}>
              Έγκριση</button></>}
          {d.status !== "draft" &&
            <button className="rounded bg-indigo-600 px-4 py-1 text-white"
              onClick={() => window.open(`${API}/api/documents/${id}/export`)}>
              Εξαγωγή σε Word</button>}
        </div>
        {d.status === "draft" &&
          <label className="mt-2 block text-sm">
            <input type="checkbox" checked={attest}
                   onChange={e => setAttest(e.target.checked)} className="mr-2" />
            Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος. Το AI βοηθά — ο
            δικηγόρος αποφασίζει.</label>}
        <div className="mt-4 rounded border border-gray-200 bg-white p-3 text-xs text-gray-600">
          Τι χρησιμοποίησα: {rep.exemplar_count ?? 0} δείγματα,
          {" "}{rep.confirmed_fact_count ?? 0} επιβεβαιωμένα στοιχεία ·
          Αβεβαιότητες: {rep.unverified_refs ?? 0} αναφορές προς επαλήθευση,
          {" "}{rep.gaps ?? 0} κενά ·
          Μοντέλο: {String(d.draft.inputs_manifest.model ?? "—")}
        </div>
      </div>
      <aside className="space-y-2">
        <h2 className="font-semibold">Λίστα ελέγχου</h2>
        {d.checklist.map(i => (
          <div key={i.id} className={`rounded border p-2 text-sm ${
              i.severity === "red" ? "border-red-300 bg-red-50"
                                   : "border-amber-300 bg-amber-50"}`}>
            <p>{i.text}</p>
            {i.status === "open" && i.source_agent !== "attestation" &&
             d.status === "draft" && (
              <div className="mt-1 flex flex-wrap gap-1">
                <button className="rounded bg-green-600 px-2 text-xs text-white"
                  onClick={() => api(`/api/checklist-items/${i.id}/resolve`,
                    { method: "POST" }).then(load)}>Επιλύθηκε</button>
                {i.severity === "red" && <>
                  <input className="w-24 rounded border border-gray-300 px-1 text-xs"
                    placeholder="αιτιολόγηση" value={note[i.id] ?? ""}
                    onChange={e => setNote({ ...note, [i.id]: e.target.value })} />
                  <button className="rounded bg-gray-600 px-2 text-xs text-white"
                    onClick={() => api(`/api/checklist-items/${i.id}/override`,
                      { method: "POST",
                        body: JSON.stringify({ note: note[i.id] ?? "" }) })
                      .then(load).catch(e => setMsg((e as Error).message))}>
                    Παράκαμψη</button></>}
              </div>)}
            {i.status !== "open" &&
              <p className="text-xs text-gray-500">
                {i.status === "resolved" ? "✓ Επιλύθηκε"
                  : `Παρακάμφθηκε: ${i.override_note}`}</p>}
          </div>))}
      </aside>
    </div>
  );
}

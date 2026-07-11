"use client";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { API, api } from "@/lib/api";
import { Btn, BtnGhost, Card, ErrorNote, Input } from "@/components/ui";

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

  if (!d) return <p className="text-ink-2">Φόρτωση…</p>;
  if (d.draft.status === "running")
    return <p className="animate-pulse text-ink-2">Το AI συντάσσει το προσχέδιο…
      (τοπικό μοντέλο — μπορεί να διαρκέσει λίγα λεπτά)</p>;
  if (d.draft.status === "failed")
    return <ErrorNote>{d.draft.error}</ErrorNote>;

  const reds = d.checklist.filter(i =>
    i.severity === "red" && i.status === "open" && i.source_agent !== "attestation");
  const rep = d.draft.uncertainty_report;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2">
        {d.status === "draft" &&
          <div className="mb-3 rounded-xl bg-warn/15 px-4 py-2 text-sm text-ink">
            Προσχέδιο AI — απαιτείται έλεγχος δικηγόρου</div>}
        <h1 className="mb-3 text-xl font-semibold tracking-tight text-ink">{d.title}</h1>
        <div className="mb-3"><ErrorNote>{msg}</ErrorNote></div>
        <textarea
          className="h-[60vh] w-full rounded-2xl border border-hairline bg-surface p-4 font-serif text-[15px] leading-relaxed text-ink focus:border-accent focus:outline-none"
          value={content} onChange={e => setContent(e.target.value)}
          disabled={d.status !== "draft"} />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {d.status === "draft" && <>
            <BtnGhost onClick={() => api(`/api/documents/${id}/versions`, {
                method: "POST", body: JSON.stringify({ content }) }).then(load)}>
              Αποθήκευση</BtnGhost>
            <Btn className="!bg-ok hover:!bg-ok/85"
              disabled={reds.length > 0 || !attest}
              onClick={async () => { setMsg("");
                try {
                  await api(`/api/documents/${id}/approve`, { method: "POST",
                    body: JSON.stringify({ attestation: true }) });
                  load();
                } catch (x) { setMsg((x as Error).message); } }}>
              Έγκριση</Btn></>}
          {d.status !== "draft" &&
            <Btn onClick={() => window.open(`${API}/api/documents/${id}/export`)}>
              Εξαγωγή σε Word</Btn>}
        </div>
        {d.status === "draft" &&
          <label className="mt-3 flex items-start gap-2 text-sm text-ink">
            <input type="checkbox" checked={attest} className="mt-0.5 accent-accent"
                   onChange={e => setAttest(e.target.checked)} />
            <span>Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος.
              Το AI βοηθά — ο δικηγόρος αποφασίζει.</span></label>}
        <div className="mt-4 rounded-2xl border border-hairline/70 bg-surface px-4 py-3 text-xs text-ink-2">
          Τι χρησιμοποίησα: {rep.exemplar_count ?? 0} δείγματα,
          {" "}{rep.confirmed_fact_count ?? 0} επιβεβαιωμένα στοιχεία ·
          Αβεβαιότητες: {rep.unverified_refs ?? 0} αναφορές προς επαλήθευση,
          {" "}{rep.gaps ?? 0} κενά ·
          Μοντέλο: {String(d.draft.inputs_manifest.model ?? "—")}
        </div>
      </div>
      <aside className="space-y-2">
        <h2 className="text-[15px] font-semibold text-ink">Λίστα ελέγχου</h2>
        {d.checklist.map(i => (
          <Card key={i.id} className={`!p-3 text-sm ${
              i.severity === "red" ? "!border-danger/40 !bg-danger/5"
                                   : "!border-warn/40 !bg-warn/5"}`}>
            <p className="text-ink">{i.text}</p>
            {i.status === "open" && i.source_agent !== "attestation" &&
             d.status === "draft" && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <button
                  className="rounded-full bg-ok px-3 py-1 text-xs font-medium text-white hover:opacity-90"
                  onClick={() => api(`/api/checklist-items/${i.id}/resolve`,
                    { method: "POST" }).then(load)}>Επιλύθηκε</button>
                {i.severity === "red" && <>
                  <Input className="w-28 !px-2 !py-1 text-xs"
                    placeholder="αιτιολόγηση" value={note[i.id] ?? ""}
                    onChange={e => setNote({ ...note, [i.id]: e.target.value })} />
                  <button
                    className="rounded-full border border-hairline px-3 py-1 text-xs font-medium text-ink hover:border-ink-2"
                    onClick={() => api(`/api/checklist-items/${i.id}/override`,
                      { method: "POST",
                        body: JSON.stringify({ note: note[i.id] ?? "" }) })
                      .then(load).catch(e => setMsg((e as Error).message))}>
                    Παράκαμψη</button></>}
              </div>)}
            {i.status !== "open" &&
              <p className="mt-1 text-xs text-ink-2">
                {i.status === "resolved" ? "✓ Επιλύθηκε"
                  : `Παρακάμφθηκε: ${i.override_note}`}</p>}
          </Card>))}
      </aside>
    </div>
  );
}

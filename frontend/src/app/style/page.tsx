"use client";
import { useCallback, useEffect, useState } from "react";
import { API, api, apiForm } from "@/lib/api";
import { Btn, BtnGhost, Card, ErrorNote, PageTitle, SectionTitle } from "@/components/ui";

type T = { id: number; name: string };
type Sample = { id: number; status: string; chars: number };
type Profile = { id: number; version: number; approved_by_lawyer: boolean;
  spec: { structure?: { section: string; order: number; share: number }[];
          phrase_bank?: Record<string, string[]>;
          tone?: Record<string, number | string> } };

const BANK_LABEL: Record<string, string> = {
  openings: "Εναρκτήριες", transitions: "Μεταβατικές", closers: "Καταληκτικές",
  favorite_expressions: "Αγαπημένες εκφράσεις" };

export default function StylePage() {
  const [types, setTypes] = useState<T[]>([]);
  const [typeId, setTypeId] = useState("");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => { api("/api/document-types").then(r => r.json()).then(setTypes); }, []);

  const loadSamples = useCallback(() => {
    if (!typeId) return;
    api(`/api/style/samples?document_type_id=${typeId}`)
      .then(r => r.json()).then(setSamples);
  }, [typeId]);

  const loadProfile = useCallback(async () => {
    if (!typeId) return;
    try {
      const r = await fetch(`${API}/api/style/profiles/${typeId}`,
                            { credentials: "include" });
      setProfile(r.ok ? await r.json() : null);
    } catch { setProfile(null); }
  }, [typeId]);

  useEffect(() => { loadSamples(); loadProfile(); setMsg(""); },
            [typeId, loadSamples, loadProfile]);

  const ok = samples.filter(s => s.status === "ok").length;
  return (
    <div>
      <PageTitle sub="Ανεβάστε παλαιά έγγραφά σας ανά τύπο — το Grafida μαθαίνει τη δομή και τη φρασεολογία σας, ποτέ τα πραγματικά περιστατικά.">
        Το ύφος μου</PageTitle>
      <select className="mb-4 rounded-xl border border-hairline bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
              value={typeId} onChange={e => setTypeId(e.target.value)}>
        <option value="">Τύπος εγγράφου…</option>
        {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>

      {typeId && (
        <Card className="mb-4">
          <SectionTitle>Δείγματα {samples.length}/10</SectionTitle>
          {ok < 3 && <p className="mb-2 text-sm text-danger">
            Χρειάζονται τουλάχιστον 3 αναγνώσιμα δείγματα ({ok}/3).</p>}
          {ok >= 3 && ok < 10 && <p className="mb-2 text-sm text-warn">
            Συνιστώνται 10 δείγματα — με λιγότερα, το προσχέδιο δεν θα είναι
            πλήρως στο ύφος σας.</p>}
          <ul className="mb-3 space-y-1 text-sm text-ink-2">
            {samples.map(s => (
              <li key={s.id} className="flex items-center gap-3">
                <span>Δείγμα #{s.id} · {s.chars} χαρακτήρες ·
                  {s.status === "ok" ? " ✓" : " OCR εκκρεμεί"}</span>
                <button className="text-danger hover:underline" onClick={async () => {
                  await api(`/api/style/samples/${s.id}`, { method: "DELETE" });
                  loadSamples(); }}>διαγραφή</button>
              </li>))}
          </ul>
          <form className="flex items-center gap-3" onSubmit={async e => {
            e.preventDefault();
            if (!file) return;
            const f = new FormData(); f.append("file", file);
            f.append("document_type_id", typeId);
            setMsg("");
            try { await apiForm("/api/style/samples", f); }
            catch (x) { setMsg((x as Error).message); }
            setFile(null); (e.target as HTMLFormElement).reset(); loadSamples(); }}>
            <input type="file" accept=".pdf,.docx,.txt" className="text-sm text-ink-2"
                   onChange={e => setFile(e.target.files?.[0] ?? null)} />
            <BtnGhost>Μεταφόρτωση δείγματος</BtnGhost>
          </form>
          <div className="mt-4">
            <Btn onClick={async () => { setMsg("");
                try { await api(`/api/style/profiles/${typeId}/rebuild`,
                                { method: "POST" }); loadProfile(); }
                catch (x) { setMsg((x as Error).message); } }}>
              {profile ? "Ανανέωση προφίλ" : "Δημιουργία προφίλ"}</Btn>
          </div>
          <div className="mt-2"><ErrorNote>{msg}</ErrorNote></div>
        </Card>
      )}

      {profile && (
        <Card>
          <SectionTitle>
            Προφίλ ύφους v{profile.version}
            {profile.approved_by_lawyer && " · εγκεκριμένο από εσάς"}</SectionTitle>
          {profile.spec.structure && (
            <dl className="mb-4 space-y-1 text-sm">
              {profile.spec.structure.map(s => (
                <div key={s.section} className="flex justify-between gap-4">
                  <dt className="text-ink">{s.order}. {s.section}</dt>
                  <dd className="text-ink-2">{Math.round(s.share * 100)}%</dd>
                </div>))}
            </dl>)}
          {Object.entries(profile.spec.phrase_bank ?? {}).map(([k, arr]) => (
            <div key={k} className="mb-3">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-2">
                {BANK_LABEL[k] ?? k}</p>
              <div className="flex flex-wrap gap-1.5">{(arr ?? []).map(ph => (
                <span key={ph}
                  className="rounded-full bg-accent/10 px-3 py-1 text-sm text-ink">
                  {ph}
                  <button className="ml-1.5 text-ink-2 hover:text-danger"
                    aria-label={`Διαγραφή φράσης ${ph}`} onClick={async () => {
                    const spec = structuredClone(profile.spec);
                    spec.phrase_bank![k] =
                      spec.phrase_bank![k].filter(x => x !== ph);
                    await api(`/api/style/profiles/${profile.id}`, {
                      method: "PATCH", body: JSON.stringify({ spec }) });
                    loadProfile(); }}>×</button>
                </span>))}</div>
            </div>))}
          {profile.spec.tone && (
            <p className="text-sm text-ink-2">
              Τόνος: επισημότητα {String(profile.spec.tone.formality ?? "—")}/5 ·
              μέση πρόταση {String(profile.spec.tone.avg_sentence_length ?? "—")} λέξεις
            </p>)}
        </Card>
      )}
    </div>
  );
}

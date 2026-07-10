"use client";
import { useCallback, useEffect, useState } from "react";
import { API, api, apiForm } from "@/lib/api";

type T = { id: number; name: string };
type Sample = { id: number; status: string; chars: number };
type Profile = { id: number; version: number; approved_by_lawyer: boolean;
  spec: { structure?: { section: string; order: number; share: number }[];
          phrase_bank?: Record<string, string[]>;
          tone?: Record<string, number | string> } };

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
    <div className="space-y-6">
      <h1 className="text-lg font-bold">Το ύφος μου</h1>
      <select className="rounded border border-gray-300 p-2" value={typeId}
              onChange={e => setTypeId(e.target.value)}>
        <option value="">Τύπος εγγράφου…</option>
        {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>

      {typeId && (
        <section className="rounded border border-gray-200 bg-white p-4">
          <h2 className="mb-1 font-semibold">Δείγματα {samples.length}/10</h2>
          {ok < 3 && <p className="mb-2 text-sm text-red-600">
            Χρειάζονται τουλάχιστον 3 αναγνώσιμα δείγματα ({ok}/3).</p>}
          {ok >= 3 && ok < 10 && <p className="mb-2 text-sm text-amber-600">
            Συνιστώνται 10 δείγματα για καλύτερη ποιότητα — το προσχέδιο ΔΕΝ θα
            είναι πλήρως στο ύφος σας.</p>}
          <ul className="mb-3 text-sm text-gray-600">{samples.map(s => (
            <li key={s.id} className="flex items-center gap-2">
              Δείγμα #{s.id} · {s.chars} χαρακτήρες ·
              {s.status === "ok" ? " ✓" : " OCR εκκρεμεί"}
              <button className="text-red-500" onClick={async () => {
                await api(`/api/style/samples/${s.id}`, { method: "DELETE" });
                loadSamples(); }}>διαγραφή</button>
            </li>))}</ul>
          <form className="flex items-center gap-2" onSubmit={async e => {
            e.preventDefault();
            if (!file) return;
            const f = new FormData(); f.append("file", file);
            f.append("document_type_id", typeId);
            setMsg("");
            try { await apiForm("/api/style/samples", f); }
            catch (x) { setMsg((x as Error).message); }
            setFile(null); (e.target as HTMLFormElement).reset(); loadSamples(); }}>
            <input type="file" accept=".pdf,.docx,.txt" className="text-sm"
                   onChange={e => setFile(e.target.files?.[0] ?? null)} />
            <button className="rounded bg-gray-800 px-3 py-1 text-sm text-white">
              Μεταφόρτωση δείγματος</button>
          </form>
          <button className="mt-3 rounded bg-indigo-600 px-4 py-1 text-white"
            onClick={async () => { setMsg("");
              try { await api(`/api/style/profiles/${typeId}/rebuild`,
                              { method: "POST" }); loadProfile(); }
              catch (x) { setMsg((x as Error).message); } }}>
            {profile ? "Ανανέωση προφίλ" : "Δημιουργία προφίλ"}</button>
          {msg && <p className="mt-2 text-sm text-red-600">{msg}</p>}
        </section>
      )}

      {profile && (
        <section className="rounded border border-gray-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">
            Προφίλ ύφους v{profile.version}
            {profile.approved_by_lawyer && " · εγκεκριμένο"}</h2>
          {profile.spec.structure && (
            <table className="mb-3 text-sm">
              <tbody>{profile.spec.structure.map(s => (
                <tr key={s.section}>
                  <td className="pr-4">{s.order}. {s.section}</td>
                  <td className="text-gray-500">{Math.round(s.share * 100)}%</td>
                </tr>))}</tbody>
            </table>)}
          {Object.entries(profile.spec.phrase_bank ?? {}).map(([k, arr]) => (
            <div key={k} className="mb-2">
              <span className="text-xs uppercase text-gray-500">{k}</span>
              <div className="flex flex-wrap gap-1">{(arr ?? []).map(ph => (
                <span key={ph} className="rounded bg-indigo-50 px-2 py-0.5 text-sm">
                  {ph}
                  <button className="ml-1 text-gray-400" onClick={async () => {
                    const spec = structuredClone(profile.spec);
                    spec.phrase_bank![k] =
                      spec.phrase_bank![k].filter(x => x !== ph);
                    await api(`/api/style/profiles/${profile.id}`, {
                      method: "PATCH", body: JSON.stringify({ spec }) });
                    loadProfile(); }}>×</button>
                </span>))}</div>
            </div>))}
          {profile.spec.tone && (
            <p className="text-sm text-gray-600">
              Τόνος: επισημότητα {String(profile.spec.tone.formality ?? "—")}/5 ·
              μέση πρόταση {String(profile.spec.tone.avg_sentence_length ?? "—")} λέξεις
            </p>)}
        </section>
      )}
    </div>
  );
}

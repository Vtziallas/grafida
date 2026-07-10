"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type C = { id: number; name: string; afm?: string; phone?: string };

export default function Clients() {
  const [rows, setRows] = useState<C[]>([]);
  const [name, setName] = useState("");
  const [afm, setAfm] = useState("");
  const load = () => api("/api/clients").then(r => r.json()).then(setRows);
  useEffect(() => { load(); }, []);
  return (
    <div>
      <h1 className="mb-4 text-lg font-bold">Πελάτες</h1>
      <form className="mb-4 flex gap-2" onSubmit={async e => { e.preventDefault();
        if (!name.trim()) return;
        await api("/api/clients", { method: "POST",
          body: JSON.stringify({ name, afm: afm || null }) });
        setName(""); setAfm(""); load(); }}>
        <input className="rounded border border-gray-300 p-2" placeholder="Ονοματεπώνυμο"
               value={name} onChange={e => setName(e.target.value)} />
        <input className="w-32 rounded border border-gray-300 p-2" placeholder="ΑΦΜ"
               value={afm} onChange={e => setAfm(e.target.value)} />
        <button className="rounded bg-indigo-600 px-4 text-white">Προσθήκη</button>
      </form>
      <table className="w-full rounded border border-gray-200 bg-white text-sm">
        <tbody>{rows.map(c => (
          <tr key={c.id} className="border-b border-gray-100">
            <td className="p-2 font-medium">{c.name}</td>
            <td className="p-2 text-gray-500">{c.afm ?? "—"}</td>
            <td className="p-2 text-gray-500">{c.phone ?? "—"}</td>
          </tr>))}</tbody>
      </table>
      {rows.length === 0 && <p className="mt-2 text-sm text-gray-500">Δεν υπάρχουν πελάτες.</p>}
    </div>
  );
}

"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type K = { id: number; title: string; status: string; court_name: string;
           next_action: string };
type C = { id: number; name: string };

export default function Cases() {
  const [rows, setRows] = useState<K[]>([]);
  const [clients, setClients] = useState<C[]>([]);
  const [title, setTitle] = useState("");
  const [clientId, setClientId] = useState("");
  const load = () => api("/api/cases").then(r => r.json()).then(setRows);
  useEffect(() => { load();
    api("/api/clients").then(r => r.json()).then(setClients); }, []);
  return (
    <div>
      <h1 className="mb-4 text-lg font-bold">Υποθέσεις</h1>
      <form className="mb-4 flex gap-2" onSubmit={async e => { e.preventDefault();
        if (!title.trim() || !clientId) return;
        await api("/api/cases", { method: "POST",
          body: JSON.stringify({ client_id: Number(clientId), title }) });
        setTitle(""); load(); }}>
        <select className="rounded border border-gray-300 p-2" value={clientId}
                onChange={e => setClientId(e.target.value)}>
          <option value="">Πελάτης…</option>
          {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input className="flex-1 rounded border border-gray-300 p-2"
               placeholder="Τίτλος υπόθεσης" value={title}
               onChange={e => setTitle(e.target.value)} />
        <button className="rounded bg-indigo-600 px-4 text-white">Νέα υπόθεση</button>
      </form>
      <table className="w-full rounded border border-gray-200 bg-white text-sm">
        <tbody>{rows.map(k => (
          <tr key={k.id} className="border-b border-gray-100">
            <td className="p-2">
              <Link className="font-medium text-indigo-700 underline"
                    href={`/cases/${k.id}`}>{k.title}</Link></td>
            <td className="p-2 text-gray-500">{k.court_name || "—"}</td>
            <td className="p-2 text-gray-500">{k.status === "open" ? "ανοιχτή" : "κλειστή"}</td>
            <td className="p-2 text-gray-500">{k.next_action || ""}</td>
          </tr>))}</tbody>
      </table>
      {rows.length === 0 && <p className="mt-2 text-sm text-gray-500">Δεν υπάρχουν υποθέσεις.</p>}
    </div>
  );
}

"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  return (
    <div className="mx-auto mt-24 max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
      <h1 className="mb-1 text-xl font-bold text-indigo-700">Grafida</h1>
      <p className="mb-6 text-sm text-gray-500">
        Το AI βοηθά — ο δικηγόρος αποφασίζει.</p>
      <form onSubmit={async (e) => { e.preventDefault(); setErr("");
        try {
          await api("/api/auth/login", { method: "POST",
            body: JSON.stringify({ email, password: pw }) });
          location.href = "/";
        } catch (x) { setErr((x as Error).message); } }}>
        <input className="mb-3 w-full rounded border border-gray-300 p-2"
               placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} />
        <input className="mb-3 w-full rounded border border-gray-300 p-2"
               type="password" placeholder="Κωδικός" value={pw}
               onChange={(e) => setPw(e.target.value)} />
        {err && <p className="mb-3 text-sm text-red-600">{err}</p>}
        <button className="w-full rounded bg-indigo-600 p-2 text-white">
          Σύνδεση</button>
      </form>
    </div>
  );
}

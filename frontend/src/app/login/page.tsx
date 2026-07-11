"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Btn, ErrorNote, Input } from "@/components/ui";

export default function Login() {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  return (
    <div className="mx-auto mt-28 max-w-sm">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">Grafida</h1>
        <p className="mt-2 text-sm text-ink-2">Το AI βοηθά — ο δικηγόρος αποφασίζει.</p>
      </div>
      <div className="rounded-2xl border border-hairline/70 bg-surface p-8">
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault(); setErr("");
          try {
            await api("/api/auth/login", { method: "POST",
              body: JSON.stringify({ email, password: pw }) });
            location.href = "/";
          } catch (x) { setErr((x as Error).message); } }}>
          <Input className="w-full" placeholder="Email" value={email}
                 onChange={(e) => setEmail(e.target.value)} />
          <Input className="w-full" type="password" placeholder="Κωδικός"
                 value={pw} onChange={(e) => setPw(e.target.value)} />
          <ErrorNote>{err}</ErrorNote>
          <Btn className="w-full">Σύνδεση</Btn>
        </form>
      </div>
    </div>
  );
}

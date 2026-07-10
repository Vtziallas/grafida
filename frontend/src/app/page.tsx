"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [d, setD] = useState<{ open_cases: unknown[] } | null>(null);
  useEffect(() => { api("/api/dashboard").then(r => r.json()).then(setD); }, []);
  if (!d) return <p>Φόρτωση…</p>;
  return <p>Ανοιχτές υποθέσεις: {d.open_cases.length}</p>;
}

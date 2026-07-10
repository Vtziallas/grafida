"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

export default function Nav() {
  const path = usePathname();
  if (path === "/login") return null;
  return (
    <nav className="flex items-center gap-6 border-b border-gray-200 bg-white px-6 py-3 text-sm">
      <span className="font-bold text-indigo-700">Grafida</span>
      <Link href="/">Αρχική</Link>
      <Link href="/cases">Υποθέσεις</Link>
      <Link href="/clients">Πελάτες</Link>
      <Link href="/style">Το ύφος μου</Link>
      <Link href="/search">Αναζήτηση</Link>
      <button className="ml-auto text-gray-500"
        onClick={async () => { await api("/api/auth/logout", { method: "POST" });
                               location.href = "/login"; }}>
        Αποσύνδεση
      </button>
    </nav>
  );
}

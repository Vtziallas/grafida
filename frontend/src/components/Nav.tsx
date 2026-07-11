"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

const LINKS = [
  ["/", "Αρχική"],
  ["/cases", "Υποθέσεις"],
  ["/clients", "Πελάτες"],
  ["/style", "Το ύφος μου"],
  ["/search", "Αναζήτηση"],
] as const;

export default function Nav() {
  const path = usePathname();
  if (path === "/login") return null;
  return (
    <nav className="sticky top-0 z-10 border-b border-hairline/70 bg-surface/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center gap-7 px-6 py-3 text-[13px]">
        <Link href="/" className="text-[15px] font-semibold tracking-tight text-ink">
          Grafida</Link>
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href}
            className={path === href
              ? "font-medium text-ink"
              : "text-ink-2 transition-colors hover:text-ink"}>
            {label}
          </Link>))}
        <button className="ml-auto text-ink-2 transition-colors hover:text-ink"
          onClick={async () => { await api("/api/auth/logout", { method: "POST" });
                                 location.href = "/login"; }}>
          Αποσύνδεση
        </button>
      </div>
    </nav>
  );
}

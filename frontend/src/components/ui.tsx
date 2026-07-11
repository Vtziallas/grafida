import { ReactNode } from "react";

export function Card({ children, className = "" }:
    { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-hairline/70 bg-surface p-6 ${className}`}>
      {children}
    </section>
  );
}

export function PageTitle({ children, sub }:
    { children: ReactNode; sub?: ReactNode }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">{children}</h1>
      {sub && <p className="mt-1 text-sm text-ink-2">{sub}</p>}
    </header>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-[15px] font-semibold text-ink">{children}</h2>;
}

export function Btn({ children, className = "", ...props }:
    React.ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button {...props}
      className={`rounded-full bg-accent px-5 py-1.5 text-sm font-medium text-white
        transition-colors hover:bg-accent-deep disabled:opacity-40
        focus-visible:outline-2 focus-visible:outline-offset-2
        focus-visible:outline-accent ${className}`}>
      {children}
    </button>
  );
}

export function BtnGhost({ children, className = "", ...props }:
    React.ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button {...props}
      className={`rounded-full border border-hairline bg-surface px-4 py-1.5
        text-sm font-medium text-ink transition-colors hover:border-ink-2
        disabled:opacity-40 focus-visible:outline-2
        focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}>
      {children}
    </button>
  );
}

export function Input({ className = "", ...props }:
    React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input {...props}
      className={`rounded-xl border border-hairline bg-surface px-3 py-2 text-sm
        text-ink placeholder:text-ink-2/70 focus:border-accent focus:outline-none
        ${className}`} />
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">{children}</p>;
}

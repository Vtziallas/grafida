export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handle(res: Response) {
  if (res.status === 401 && typeof window !== "undefined"
      && !location.pathname.startsWith("/login")) {
    location.href = "/login";
  }
  if (!res.ok) {
    let msg = "Σφάλμα";
    try { msg = (await res.json()).detail ?? msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

export async function api(path: string, init?: RequestInit) {
  return handle(await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  }));
}

export async function apiForm(path: string, form: FormData) {
  return handle(await fetch(`${API}${path}`, {
    method: "POST", credentials: "include", body: form,
  }));
}

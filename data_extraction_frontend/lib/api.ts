const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001/api";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string, org_name: string) =>
    req("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, org_name }),
    }),

  login: (email: string, password: string) =>
    req("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () => req("/auth/logout", { method: "POST" }),

  me: () => req("/auth/me"),

  sendMessage: (message: string, session_id?: string) =>
    req<{ reply: string; session_id: string }>("/chat/message", {
      method: "POST",
      body: JSON.stringify({ message, session_id }),
    }),
};

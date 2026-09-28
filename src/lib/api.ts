const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export class ApiError extends Error { constructor(message: string, public readonly status: number) { super(message); this.name = "ApiError"; } }
export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
 const headers = new Headers(init.headers);
 if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
 if (typeof window !== "undefined") { const token = window.sessionStorage.getItem("dermasphere_token"); if (token) headers.set("Authorization", `Bearer ${token}`); }
 let response: Response;
 try { response = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" }); }
 catch { throw new ApiError("Could not reach DermaSphere. Check that the API is running.", 0); }
 if (!response.ok) { const body = await response.json().catch(() => null); const message = typeof body?.detail === "string" ? body.detail : "The request could not be completed."; throw new ApiError(message, response.status); }
 if (response.status === 204) return undefined as T;
 return response.json() as Promise<T>;
}

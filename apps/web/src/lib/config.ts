export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

// Token baked in at build time (VITE_ADMIN_TOKEN env var).
// If present, auto-seeds localStorage so the Settings page is never needed
// in dev. In production, set VITE_ADMIN_TOKEN="" to require manual entry.
const _BUILD_TOKEN = (import.meta.env.VITE_ADMIN_TOKEN as string | undefined) ?? "";

export const ADMIN_TOKEN_KEY = "bd_legal_rag_admin_token";

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY) || _BUILD_TOKEN || null;
}

export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

// Auto-seed localStorage once from the build-time token so admin API calls
// work immediately without the user visiting Settings.
if (_BUILD_TOKEN && !localStorage.getItem(ADMIN_TOKEN_KEY)) {
  localStorage.setItem(ADMIN_TOKEN_KEY, _BUILD_TOKEN);
}

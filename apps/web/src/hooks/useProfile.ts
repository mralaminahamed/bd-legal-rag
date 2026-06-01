import { getAdminToken } from "@/lib/config";

export function useProfile(): { hasToken: boolean } {
  return { hasToken: Boolean(getAdminToken()) };
}

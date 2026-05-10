/**
 * Auth shim. Until Clerk env vars are populated we return a fake admin
 * session so the rest of the app boots. Wire to @clerk/nextjs once the
 * publishable key is set.
 */

export type Role = "admin" | "dispatcher" | "driver";

export interface SessionUser {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export async function currentUser(): Promise<SessionUser> {
  // TODO: replace with `auth()` from @clerk/nextjs/server once Clerk is provisioned.
  return {
    id: "dev-admin",
    name: "Will (dev)",
    email: "willstables.2k@gmail.com",
    role: "admin",
  };
}

export function canSee(role: Role, page: string): boolean {
  if (role === "admin") return true;
  if (role === "dispatcher") return page !== "/admin/users";
  if (role === "driver") return page === "/drive";
  return false;
}

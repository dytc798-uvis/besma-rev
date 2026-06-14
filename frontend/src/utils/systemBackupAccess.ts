import type { AuthUser } from "@/stores/auth";

export const SYSTEM_BACKUP_LOGIN_ID = "안전보건-정상익";

export function canSystemBackup(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  if (user.can_system_backup === true) return true;
  return user.login_id?.trim() === SYSTEM_BACKUP_LOGIN_ID;
}

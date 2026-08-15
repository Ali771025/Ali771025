export type UserSession = {
  userId: string;
  tenantId?: string;
  roles: string[];
  permissions: string[];
  scopes: string[];
  token?: string;
};

export function hasPermission(session: UserSession | undefined, required: string[]): boolean {
  if (!required.length || required.includes('public')) return true;
  if (!session) return false;
  if (session.scopes.includes('*') || session.permissions.includes('*')) return true;
  return required.every((permission) => session.permissions.includes(permission) || session.scopes.includes(permission));
}

export function effectivePermissionSummary(session: UserSession | undefined): string {
  if (!session) return 'کاربر احراز هویت نشده است.';
  if (session.scopes.includes('*')) return 'دسترسی کامل مالک سامانه';
  return [...new Set([...session.permissions, ...session.scopes])].slice(0, 8).join('، ');
}

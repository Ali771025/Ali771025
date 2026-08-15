import { describe, expect, it } from 'vitest';
import { hasPermission } from './accessControl';

describe('hasPermission', () => {
  it('allows public pages without session', () => {
    expect(hasPermission(undefined, ['public'])).toBe(true);
  });

  it('allows wildcard scope', () => {
    expect(hasPermission({ userId: 'owner', roles: ['system_owner'], scopes: ['*'], permissions: [] }, ['owner.audit.read'])).toBe(true);
  });

  it('rejects missing permission', () => {
    expect(hasPermission({ userId: 'u1', roles: [], scopes: [], permissions: ['software.read'] }, ['owner.audit.read'])).toBe(false);
  });
});

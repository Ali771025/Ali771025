import { create } from 'zustand';
import type { UserSession } from '../model/accessControl';

const ownerDemoSession: UserSession = {
  userId: 'owner',
  tenantId: 'municipality-01',
  roles: ['system_owner'],
  scopes: ['*'],
  permissions: ['*'],
  token: localStorage.getItem('access_token') ?? undefined
};

type SessionStore = {
  session?: UserSession;
  setSession: (session?: UserSession) => void;
};

export const useSessionStore = create<SessionStore>((set) => ({
  session: ownerDemoSession,
  setSession: (session) => set({ session })
}));

import { httpClient } from '../../../shared/api/httpClient';
import type { AdminRow, Dashboard } from '../model/types';

export const ownerApi = {
  dashboard(token: string) {
    return httpClient<Dashboard>('/owner/dashboard', { token });
  },
  tenants(token: string) {
    return httpClient<AdminRow[]>('/owner/tenants', { token });
  },
  models(token: string) {
    return httpClient<AdminRow[]>('/owner/models', { token });
  },
  auditLogs(token: string, limit = 20) {
    return httpClient<AdminRow[]>(`/owner/audit-logs?limit=${limit}`, { token });
  },
  createManager(token: string, payload: Record<string, unknown>) {
    return httpClient<AdminRow>('/owner/managers', { method: 'POST', body: JSON.stringify(payload), token });
  },
  createTenant(token: string, payload: Record<string, unknown>) {
    return httpClient<AdminRow>('/owner/tenants', { method: 'POST', body: JSON.stringify(payload), token });
  },
  testModel(token: string, modelId: string) {
    return httpClient<Record<string, unknown>>(`/owner/models/${modelId}/test`, { method: 'POST', body: JSON.stringify({}), token });
  }
};

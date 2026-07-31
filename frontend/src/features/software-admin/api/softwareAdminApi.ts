import { httpClient } from '../../../shared/api/httpClient';
import type { Row, SoftwareDashboard } from '../model/types';

export const softwareAdminApi = {
  dashboard(token: string) {
    return httpClient<SoftwareDashboard>('/software-admin/dashboard', { token });
  },
  listSoftware(token: string) {
    return httpClient<Row[]>('/software-admin/software', { token });
  },
  createSoftware(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/software', { method: 'POST', body: JSON.stringify(payload), token });
  },
  listVersions(token: string, softwareId: string) {
    return httpClient<Row[]>(`/software-admin/software/${softwareId}/versions`, { token });
  },
  createVersion(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/versions', { method: 'POST', body: JSON.stringify(payload), token });
  },
  listKnowledge(token: string, softwareId: string, versionId?: string) {
    return httpClient<Row[]>(`/software-admin/knowledge?software_id=${softwareId}${versionId ? `&version_id=${versionId}` : ''}`, { token });
  },
  uploadKnowledge(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/knowledge', { method: 'POST', body: JSON.stringify(payload), token });
  },
  standardizeKnowledge(token: string, payload: Record<string, unknown>) {
    return httpClient<Record<string, unknown>>('/software-admin/knowledge/standardize', { method: 'POST', body: JSON.stringify(payload), token });
  },
  publishSnapshot(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/snapshots/publish', { method: 'POST', body: JSON.stringify(payload), token });
  },
  createUser(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/users', { method: 'POST', body: JSON.stringify(payload), token });
  },
  listApiKeys(token: string) {
    return httpClient<Row[]>('/software-admin/api-keys', { token });
  },
  issueApiKey(token: string, payload: Record<string, unknown>) {
    return httpClient<{ secret: string; prefix: string }>('/software-admin/api-keys', { method: 'POST', body: JSON.stringify(payload), token });
  },
  listRequests(token: string, softwareId: string, limit = 20) {
    return httpClient<Row[]>(`/software-admin/requests?software_id=${softwareId}&limit=${limit}`, { token });
  },
  createGoldTest(token: string, payload: Record<string, unknown>) {
    return httpClient<Row>('/software-admin/gold-tests', { method: 'POST', body: JSON.stringify(payload), token });
  },
  listGoldTests(token: string, softwareId: string, versionId: string) {
    return httpClient<Row[]>(`/software-admin/gold-tests?software_id=${softwareId}&version_id=${versionId}`, { token });
  },
  rotateApiKey(token: string, keyId: string, overlapHours = 24) {
    return httpClient<Record<string, unknown>>(`/software-admin/api-keys/${keyId}/rotate`, { method: 'POST', body: JSON.stringify({ overlap_hours: overlapHours }), token });
  },
  runGoldRegression(token: string, softwareId: string, versionId: string) {
    return httpClient<Record<string, unknown>>('/software-admin/gold-tests/regression/run', { method: 'POST', body: JSON.stringify({ software_id: softwareId, version_id: versionId }), token });
  }
};

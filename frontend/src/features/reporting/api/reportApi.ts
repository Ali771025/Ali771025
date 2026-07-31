import { httpClient } from '../../../shared/api/httpClient';
import type { ReportRequestPayload, ReportResponse } from '../model/types';

export const reportApi = {
  generate(payload: ReportRequestPayload) {
    return httpClient<ReportResponse>('/reports/generate', { method: 'POST', body: JSON.stringify(payload) });
  },
  sendExecutionMetadata(payload: { audit_id: string; execution_time_ms: number; row_count: number; display_type: string }) {
    return httpClient<Record<string, unknown>>('/reports/execution-result', { method: 'POST', body: JSON.stringify(payload) });
  },
  sendFeedback(payload: Record<string, unknown>) {
    return httpClient<Record<string, unknown>>('/reports/feedback', { method: 'POST', body: JSON.stringify(payload) });
  }
};

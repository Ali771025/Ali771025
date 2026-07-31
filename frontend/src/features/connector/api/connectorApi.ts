import { httpClient } from '../../../shared/api/httpClient';
import type { Connector, Row } from '../model/types';

export const connectorApi = {
  register(token: string, payload: Record<string, unknown>) {
    return httpClient<Connector>('/connectors/register', { method: 'POST', body: JSON.stringify(payload), token });
  },
  health(token: string, connectorId: string) {
    return httpClient<Connector>(`/connectors/${connectorId}/health`, { token });
  },
  execute(token: string, connectorId: string, payload: Record<string, unknown>) {
    return httpClient<Row>(`/connectors/${connectorId}/execute`, { method: 'POST', body: JSON.stringify(payload), token });
  }
};

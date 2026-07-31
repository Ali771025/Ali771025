export type Connector = {
  id: string;
  software_id: string;
  version_id?: string | null;
  registration_status: string;
  policy_hash: string;
  central_connection_status: Record<string, unknown>;
  database_connection_status: Record<string, unknown>;
  last_heartbeat_at?: string | null;
};

export type Row = Record<string, unknown>;

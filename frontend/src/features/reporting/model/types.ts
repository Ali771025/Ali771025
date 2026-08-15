export type ReportRequestPayload = {
  request_id: string;
  software_id: string;
  software_version: string;
  user_id: string;
  question: string;
  access_context: {
    organization: string;
    region: string[];
    roles: string[];
    scopes: string[];
  };
  locale: string;
  timezone: string;
};

export type ReportResponse =
  | { status: 'success'; sql: string; parameters: Record<string, unknown>; display: { type: string; title: string; columns: { name: string; title: string }[]; formats: Record<string, unknown> }; confidence: { score: number; level: string }; audit_id: string; policy: Record<string, unknown> }
  | { status: 'needs_clarification'; audit_id: string; question: string; options: string[] }
  | { status: 'rejected'; sql: null; audit_id: string; reason_code: string; message: string };

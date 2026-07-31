export type Row = Record<string, unknown>;
export type SoftwareDashboard = {
  metrics: { label: string; value: string | number }[];
  alerts: { message: string }[];
};

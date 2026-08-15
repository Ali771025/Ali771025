export type DashboardMetric = { label: string; value: string | number };
export type Dashboard = {
  metrics: DashboardMetric[];
  charts: Record<string, unknown>;
  alerts: { severity: string; message: string }[];
};
export type AdminRow = Record<string, unknown>;

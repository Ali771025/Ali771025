export type Role = 'FLIGHT_EXPERT' | 'FLIGHT_MANAGER'
export type TopicName = 'telemetry' | 'flight_assessment' | 'vision' | 'route_candidates' | 'module_health' | 'alert' | 'scenario_report'

export interface User { username: string; display_name: string; role: Role }
export interface TopicEvent<T = Record<string, unknown>> {
  type: 'topic_update'; topic: TopicName; source: string; sequence_no: number
  sent_at_ms: number; received_at_ms: number; latency_ms: number; transport: 'udp' | 'tcp'; payload: T
}
export interface Telemetry {
  latitude?: number; longitude?: number; altitude_m?: number; relative_altitude_m?: number
  groundspeed_mps?: number; vertical_speed_mps?: number; heading_deg?: number
  roll_deg?: number; pitch_deg?: number; yaw_deg?: number
  battery_percent?: number; battery_voltage_v?: number; gps_fix?: number; satellites?: number
  link_quality?: number; ekf_healthy?: boolean; armed?: boolean; flight_mode?: string; mission_progress?: number
}
export interface AlertRecord {
  id: string; severity: 'INFO' | 'WARNING' | 'CRITICAL'; code: string; title: string; detail: string
  source: string; created_at_ms: number; acknowledged_at_ms?: number; acknowledged_by?: string
}
export interface ControlIntent {
  id: string; action: string; reason: string; status: string; requested_by: string; approved_by?: string
  created_at_ms: number; expires_at_ms: number; result_json?: string
}
export interface TransportStats { received: number; invalid: number; sequence_gaps: number; out_of_order: number; subscribers: number; uptime_ms: number }
export interface LiveSnapshot { topics: Partial<Record<TopicName, TopicEvent>>; transport: TransportStats }
export interface Bootstrap {
  user: User; live: LiveSnapshot; alerts: AlertRecord[]; control_intents: ControlIntent[]
  capabilities: { control_mode: string; dual_approval: boolean; allowed_actions: string[]; model_control_authority: false }
  server_time_ms: number
}


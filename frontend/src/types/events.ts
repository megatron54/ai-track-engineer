/**
 * TypeScript mirror of the dashboard WebSocket contract.
 *
 * Source of truth: ../../../docs/WEBSOCKET-CONTRACT.md (kept in sync with
 * src/dashboard/serialization.py and src/dashboard/pump.py on the Python
 * side). Update both together when the wire format changes.
 */

export interface CornerSummary {
  index: number
  name: string
  entry: number
  exit: number
}

export interface MapProjection {
  width: number
  height: number
  x_offset: number
  z_offset: number
  scale_factor: number
  margin: number
}

export interface SessionEvent {
  type: 'session'
  track: string
  track_id: string
  car: string
  length_m: number
  best_ever_ms: number | null
  corners: CornerSummary[]
  map: MapProjection | null
}

export interface TelemetryEvent {
  type: 'telemetry'
  t: number
  speed_kmh: number
  rpm: number
  gear: string
  gas: number
  brake: number
  fuel: number
  lap_pos: number
  coords: [number, number]
  position: number
  sector: number
  current_time: string
  last_time: string
  best_time: string
  completed_laps: number
  tyre_temp: [number, number, number, number]
  tyre_wear: [number, number, number, number]
  steer_angle: number
  g_lat: number
  g_lon: number
  delta: number | null
  status: string
  session: string
}

export interface CornerLoss {
  corner: string
  delta_s: number
}

export interface LapEvent {
  type: 'lap'
  number: number
  time_ms: number
  valid: boolean
  is_personal_best: boolean
  sectors_ms: number[]
  corner_losses: CornerLoss[]
  advice: string[]
}

export interface AdviceEvent {
  type: 'advice'
  lap: number
  messages: string[]
}

export type CoachingPriority = 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW'

export interface CoachingEvent {
  type: 'coaching'
  priority: CoachingPriority
  text: string
  corner: string | null
}

export type FuelStatus = 'ok' | 'low' | 'critical'
export type TyreAdvice = 'stay_out' | 'consider_pit' | 'pit_now'
export type PitAdvice = 'no_stop' | 'plan_stop' | 'box_now'

export interface StrategyEvent {
  type: 'strategy'
  lap: number
  fuel: {
    remaining: number
    per_lap: number
    laps_left: number
    status: FuelStatus
    message: string
  }
  tyres: {
    wear_pct: number
    rate: number
    advice: TyreAdvice
    message: string
  }
  pit: {
    advice: PitAdvice
    trigger: string | null
    lap: number | null
    message: string
  }
}

export interface ModeEvent {
  type: 'mode'
  mode: string
  priority: string
  personality: string
  max_messages_per_lap: number
}

export type Trend = 'improving' | 'stable' | 'regressing'

export interface CornerPattern {
  corner: string
  occurrences: number
  avg_delta_s: number
  trend: Trend
}

export interface PatternEvent {
  type: 'pattern'
  worst_corners: CornerPattern[]
  consistency_trend: Trend
  lap_time_trend: Trend
}

export interface SessionReportEvent {
  type: 'session_report'
  total_laps: number
  valid_laps: number
  best_lap_ms: number | null
  average_lap_ms: number | null
  consistency_stdev_ms: number | null
  improvement_ms: number | null
  theoretical_best_ms: number | null
}

export type DashboardEvent =
  | SessionEvent
  | TelemetryEvent
  | LapEvent
  | AdviceEvent
  | CoachingEvent
  | StrategyEvent
  | ModeEvent
  | PatternEvent
  | SessionReportEvent

import type { SessionReportEvent } from '../types/events'
import { formatLapTime } from '../lib/format'

export interface SessionReportPanelProps {
  report: SessionReportEvent | null
}

/**
 * Cumulative session summary (Fase 0's `session_report` event), migrated
 * from the plain text line the legacy dashboard renders under the lap
 * history table (`onSessionReport` in src/dashboard/static/index.html).
 */
export function SessionReportPanel({ report }: SessionReportPanelProps) {
  if (report == null) return null

  const separator = '\u00b7'

  return (
    <p className="session-report" data-testid="session-report">
      {report.valid_laps}/{report.total_laps} valid {separator} best{' '}
      {formatLapTime(report.best_lap_ms)} {separator} avg{' '}
      {formatLapTime(report.average_lap_ms)}
    </p>
  )
}

import type { LapEvent } from '../types/events'
import { formatLapTime, formatSignedSeconds } from '../lib/format'

export interface LapHistoryTableProps {
  laps: LapEvent[]
}

/** The best (lowest) time among valid laps, or null if there is none yet. */
function bestValidLapMs(laps: LapEvent[]): number | null {
  const validTimes = laps.filter((lap) => lap.valid && lap.time_ms > 0).map((lap) => lap.time_ms)
  return validTimes.length ? Math.min(...validTimes) : null
}

/**
 * Lap-by-lap history table, most recent lap first.
 *
 * Migrated from the legacy `#laprows` table in
 * src/dashboard/static/index.html - same columns, same "PB" row highlight,
 * same gap-to-best computation - so behaviour stays identical during the
 * Fase 3 frontend migration.
 */
export function LapHistoryTable({ laps }: LapHistoryTableProps) {
  if (laps.length === 0) {
    return <p className="muted">No completed laps yet</p>
  }

  const best = bestValidLapMs(laps)
  const rows = [...laps].reverse()

  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Time</th>
          <th>Gap</th>
          <th>S1</th>
          <th>S2</th>
          <th>S3</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((lap) => {
          const gap =
            best != null && lap.valid ? (lap.time_ms - best) / 1000 : null
          return (
            <tr key={lap.number} className={lap.is_personal_best ? 'pb' : undefined}>
              <td>{lap.number}</td>
              <td className={lap.valid ? undefined : 'inv'}>{formatLapTime(lap.time_ms)}</td>
              <td>{gap == null ? '\u2014' : gap === 0 ? 'PB' : formatSignedSeconds(gap, 2)}</td>
              {[0, 1, 2].map((i) => (
                <td key={i}>
                  {lap.sectors_ms[i] ? (lap.sectors_ms[i] / 1000).toFixed(2) : '\u2014'}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

import type { PatternEvent } from '../types/events'

export interface PatternPanelProps {
  pattern: PatternEvent | null
}

/**
 * Multi-lap pattern detection (Fase 0's `pattern` event): recurring
 * worst-corner losses plus overall pace/consistency trend. Migrated from the
 * `onPattern` card in src/dashboard/static/index.html.
 */
export function PatternPanel({ pattern }: PatternPanelProps) {
  if (pattern == null || pattern.worst_corners.length === 0) return null

  const separator = '\u00b7'

  return (
    <div className="card ai" data-testid="pattern-panel">
      <div className="hd">
        <b>Patterns</b>
        <span>
          pace {pattern.lap_time_trend} {separator} consistency {pattern.consistency_trend}
        </span>
      </div>
      <div className="body">
        {pattern.worst_corners.map((corner) => (
          <div key={corner.corner}>
            {corner.corner} +{corner.avg_delta_s.toFixed(2)}s ({corner.trend}, x
            {corner.occurrences})
          </div>
        ))}
      </div>
    </div>
  )
}

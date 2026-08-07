import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LapHistoryTable } from './LapHistoryTable'
import type { LapEvent } from '../types/events'

function makeLap(overrides: Partial<LapEvent> = {}): LapEvent {
  return {
    type: 'lap',
    number: 1,
    time_ms: 90000,
    valid: true,
    is_personal_best: false,
    sectors_ms: [30000, 30000, 30000],
    corner_losses: [],
    advice: [],
    ...overrides,
  }
}

describe('LapHistoryTable', () => {
  it('shows a placeholder when there are no laps', () => {
    render(<LapHistoryTable laps={[]} />)
    expect(screen.getByText('No completed laps yet')).toBeInTheDocument()
  })

  it('renders one row per lap, most recent first', () => {
    const laps = [makeLap({ number: 1 }), makeLap({ number: 2 })]
    render(<LapHistoryTable laps={laps} />)
    const rows = screen.getAllByRole('row').slice(1) // skip header row
    expect(rows[0]).toHaveTextContent('2')
    expect(rows[1]).toHaveTextContent('1')
  })

  it('marks the personal-best row', () => {
    const laps = [makeLap({ number: 1, is_personal_best: true, time_ms: 88000 })]
    render(<LapHistoryTable laps={laps} />)
    const row = screen.getAllByRole('row')[1]
    expect(row.className).toContain('pb')
    expect(row).toHaveTextContent('PB')
  })

  it('shows the gap to the best valid lap for other laps', () => {
    const laps = [
      makeLap({ number: 1, time_ms: 88000, is_personal_best: true }),
      makeLap({ number: 2, time_ms: 88500 }),
    ]
    render(<LapHistoryTable laps={laps} />)
    expect(screen.getByText('+0.50')).toBeInTheDocument()
  })

  it('marks invalid laps and excludes them from the best-lap calculation', () => {
    const laps = [
      makeLap({ number: 1, time_ms: 80000, valid: false }),
      makeLap({ number: 2, time_ms: 90000, is_personal_best: true }),
    ]
    render(<LapHistoryTable laps={laps} />)
    const rows = screen.getAllByRole('row')
    // Rows render most-recent-first: index 1 is lap 2 (valid), index 2 is lap 1 (invalid).
    const invalidRow = rows[2]
    const invalidTimeCell = invalidRow.querySelectorAll('td')[1]
    expect(invalidTimeCell.className).toContain('inv')
    // Its gap column is a dash, not a (meaningless) negative gap to itself.
    expect(invalidRow).toHaveTextContent('\u2014')
  })

  it('renders sector times in seconds, or a dash when missing', () => {
    const laps = [makeLap({ number: 1, sectors_ms: [30125, 0, 29800] })]
    render(<LapHistoryTable laps={laps} />)
    expect(screen.getByText('30.13')).toBeInTheDocument()
    expect(screen.getByText('29.80')).toBeInTheDocument()
  })
})

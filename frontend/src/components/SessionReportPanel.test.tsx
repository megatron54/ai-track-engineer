import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SessionReportPanel } from './SessionReportPanel'
import type { SessionReportEvent } from '../types/events'

function makeReport(overrides: Partial<SessionReportEvent> = {}): SessionReportEvent {
  return {
    type: 'session_report',
    total_laps: 8,
    valid_laps: 6,
    best_lap_ms: 88512,
    average_lap_ms: 89430.2,
    consistency_stdev_ms: 612.4,
    improvement_ms: 1340,
    theoretical_best_ms: 88010,
    ...overrides,
  }
}

describe('SessionReportPanel', () => {
  it('renders nothing before the first report arrives', () => {
    const { container } = render(<SessionReportPanel report={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders valid/total laps and formatted best/average times', () => {
    render(<SessionReportPanel report={makeReport()} />)
    const el = screen.getByTestId('session-report')
    expect(el).toHaveTextContent('6/8 valid')
    expect(el).toHaveTextContent('best 1:28.512')
    expect(el).toHaveTextContent('avg 1:29.430')
  })

  it('shows a placeholder time when no valid lap exists yet', () => {
    render(<SessionReportPanel report={makeReport({ best_lap_ms: null, average_lap_ms: null })} />)
    const el = screen.getByTestId('session-report')
    expect(el).toHaveTextContent('best -:--.---')
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PatternPanel } from './PatternPanel'
import type { PatternEvent } from '../types/events'

function makePattern(overrides: Partial<PatternEvent> = {}): PatternEvent {
  return {
    type: 'pattern',
    worst_corners: [
      { corner: 'T1', occurrences: 5, avg_delta_s: 0.31, trend: 'regressing' },
    ],
    consistency_trend: 'stable',
    lap_time_trend: 'improving',
    ...overrides,
  }
}

describe('PatternPanel', () => {
  it('renders nothing before any pattern has been detected', () => {
    const { container } = render(<PatternPanel pattern={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when there are no worst corners yet', () => {
    const { container } = render(
      <PatternPanel pattern={makePattern({ worst_corners: [] })} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the pace/consistency trend and each worst corner', () => {
    render(<PatternPanel pattern={makePattern()} />)
    const panel = screen.getByTestId('pattern-panel')
    expect(panel).toHaveTextContent('pace improving')
    expect(panel).toHaveTextContent('consistency stable')
    expect(panel).toHaveTextContent('T1 +0.31s (regressing, x5)')
  })

  it('renders multiple worst corners', () => {
    const pattern = makePattern({
      worst_corners: [
        { corner: 'T1', occurrences: 5, avg_delta_s: 0.31, trend: 'regressing' },
        { corner: 'T4', occurrences: 3, avg_delta_s: 0.12, trend: 'improving' },
      ],
    })
    render(<PatternPanel pattern={pattern} />)
    expect(screen.getByText(/T1 \+0\.31s/)).toBeInTheDocument()
    expect(screen.getByText(/T4 \+0\.12s/)).toBeInTheDocument()
  })
})

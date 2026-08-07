import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import * as useDashboardEventsModule from './hooks/useDashboardEvents'

function mockDashboardState(
  overrides: Partial<ReturnType<typeof useDashboardEventsModule.useDashboardEvents>> = {},
) {
  vi.spyOn(useDashboardEventsModule, 'useDashboardEvents').mockReturnValue({
    connected: false,
    session: null,
    laps: [],
    pattern: null,
    sessionReport: null,
    ...overrides,
  })
}

describe('App', () => {
  it('shows OFFLINE and an empty lap history before connecting', () => {
    mockDashboardState()
    render(<App />)
    expect(screen.getByText('OFFLINE')).toBeInTheDocument()
    expect(screen.getByText('No completed laps yet')).toBeInTheDocument()
  })

  it('shows LIVE and the session track/car once connected', () => {
    mockDashboardState({
      connected: true,
      session: {
        type: 'session',
        track: 'Laguna Seca',
        track_id: 'ks_laguna_seca',
        car: 'ks_ferrari_488_gt3',
        length_m: 3602,
        best_ever_ms: null,
        corners: [],
        map: null,
      },
    })
    render(<App />)
    expect(screen.getByText('LIVE')).toBeInTheDocument()
    expect(screen.getByText('Laguna Seca')).toBeInTheDocument()
    expect(screen.getByText('ks_ferrari_488_gt3')).toBeInTheDocument()
  })
})

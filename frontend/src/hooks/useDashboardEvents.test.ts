import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dashboardReducer, useDashboardEvents, type DashboardState } from './useDashboardEvents'
import type { LapEvent, SessionEvent } from '../types/events'

const baseState: DashboardState = {
  connected: false,
  session: null,
  laps: [],
  pattern: null,
  sessionReport: null,
}

const session: SessionEvent = {
  type: 'session',
  track: 'Laguna Seca',
  track_id: 'ks_laguna_seca',
  car: 'ks_ferrari_488_gt3',
  length_m: 3602,
  best_ever_ms: null,
  corners: [],
  map: null,
}

function makeLap(number: number): LapEvent {
  return {
    type: 'lap',
    number,
    time_ms: 90000,
    valid: true,
    is_personal_best: false,
    sectors_ms: [],
    corner_losses: [],
    advice: [],
  }
}

describe('dashboardReducer', () => {
  it('marks the socket connected/disconnected', () => {
    const connected = dashboardReducer(baseState, { kind: 'connected' })
    expect(connected.connected).toBe(true)
    expect(dashboardReducer(connected, { kind: 'disconnected' }).connected).toBe(false)
  })

  it('stores the session event and resets laps for a new session', () => {
    const withLaps = { ...baseState, laps: [makeLap(1)] }
    const result = dashboardReducer(withLaps, { kind: 'event', event: session })
    expect(result.session).toBe(session)
    expect(result.laps).toEqual([])
  })

  it('appends lap events in arrival order', () => {
    let state = baseState
    state = dashboardReducer(state, { kind: 'event', event: makeLap(1) })
    state = dashboardReducer(state, { kind: 'event', event: makeLap(2) })
    expect(state.laps.map((l) => l.number)).toEqual([1, 2])
  })

  it('ignores event types not yet migrated to this frontend slice', () => {
    const telemetryLike = { type: 'telemetry' } as unknown as SessionEvent
    const result = dashboardReducer(baseState, { kind: 'event', event: telemetryLike })
    expect(result).toEqual(baseState)
  })
})

describe('useDashboardEvents', () => {
  class FakeWebSocket {
    static instances: FakeWebSocket[] = []
    onopen: (() => void) | null = null
    onclose: (() => void) | null = null
    onmessage: ((event: { data: string }) => void) | null = null
    closed = false
    url: string

    constructor(url: string) {
      this.url = url
      FakeWebSocket.instances.push(this)
    }

    close() {
      this.closed = true
    }

    emitOpen() {
      this.onopen?.()
    }

    emitMessage(data: unknown) {
      this.onmessage?.({ data: JSON.stringify(data) })
    }
  }

  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('connects and reflects incoming session/lap events in state', async () => {
    const { result } = renderHook(() => useDashboardEvents('ws://test/ws/telemetry'))
    const socket = FakeWebSocket.instances[0]
    expect(socket.url).toBe('ws://test/ws/telemetry')

    act(() => socket.emitOpen())
    await waitFor(() => expect(result.current.connected).toBe(true))

    act(() => socket.emitMessage(session))
    await waitFor(() => expect(result.current.session?.track).toBe('Laguna Seca'))

    act(() => socket.emitMessage(makeLap(1)))
    await waitFor(() => expect(result.current.laps).toHaveLength(1))
  })

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useDashboardEvents('ws://test/ws/telemetry'))
    const socket = FakeWebSocket.instances[0]
    unmount()
    expect(socket.closed).toBe(true)
  })
})

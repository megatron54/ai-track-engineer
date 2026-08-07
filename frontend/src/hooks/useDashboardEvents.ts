import { useEffect, useReducer } from 'react'
import type {
  DashboardEvent,
  LapEvent,
  PatternEvent,
  SessionEvent,
  SessionReportEvent,
} from '../types/events'

export interface DashboardState {
  connected: boolean
  session: SessionEvent | null
  laps: LapEvent[]
  pattern: PatternEvent | null
  sessionReport: SessionReportEvent | null
}

const initialState: DashboardState = {
  connected: false,
  session: null,
  laps: [],
  pattern: null,
  sessionReport: null,
}

type ReducerAction =
  | { kind: 'connected' }
  | { kind: 'disconnected' }
  | { kind: 'event'; event: DashboardEvent }

/**
 * Reduce incoming WebSocket events into dashboard state.
 *
 * Only the event types consumed by the components migrated so far (Fase 3,
 * first slice: lap history, session report, patterns) are handled here;
 * telemetry/advice/coaching/strategy/mode are left for the next slice of the
 * migration and are safely ignored for now (matching the legacy dashboard's
 * "unknown type -> no-op" dispatch behaviour).
 */
export function dashboardReducer(state: DashboardState, action: ReducerAction): DashboardState {
  switch (action.kind) {
    case 'connected':
      return { ...state, connected: true }
    case 'disconnected':
      return { ...state, connected: false }
    case 'event': {
      const event = action.event
      switch (event.type) {
        case 'session':
          return { ...state, session: event, laps: [] }
        case 'lap':
          return { ...state, laps: [...state.laps, event] }
        case 'pattern':
          return { ...state, pattern: event }
        case 'session_report':
          return { ...state, sessionReport: event }
        default:
          return state
      }
    }
    default:
      return state
  }
}

/**
 * Connect to the dashboard's telemetry WebSocket and expose the reduced
 * state described above. `wsUrl` defaults to the same-origin `/ws/telemetry`
 * endpoint the FastAPI backend serves (see docs/WEBSOCKET-CONTRACT.md).
 */
export function useDashboardEvents(
  wsUrl = `ws://${typeof location !== 'undefined' ? location.host : 'localhost'}/ws/telemetry`,
): DashboardState {
  const [state, dispatch] = useReducer(dashboardReducer, initialState)

  useEffect(() => {
    const socket = new WebSocket(wsUrl)
    socket.onopen = () => dispatch({ kind: 'connected' })
    socket.onclose = () => dispatch({ kind: 'disconnected' })
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data as string) as DashboardEvent
        dispatch({ kind: 'event', event })
      } catch {
        // Malformed frame: ignore rather than crash the dashboard.
      }
    }
    return () => socket.close()
  }, [wsUrl])

  return state
}

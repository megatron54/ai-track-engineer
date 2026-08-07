import { useDashboardEvents } from './hooks/useDashboardEvents'
import { LapHistoryTable } from './components/LapHistoryTable'
import { PatternPanel } from './components/PatternPanel'
import { SessionReportPanel } from './components/SessionReportPanel'
import './App.css'

/**
 * React dashboard shell (Fase 3 migration, first slice).
 *
 * Only the "Lap History" panel is fully migrated here: it and its
 * companions (session report, patterns) are read-only, data-table-like
 * views with no canvas/WebGL work, which is why they were picked as the
 * lowest-risk starting point per docs/DEEP-DIVE-ROADMAP.md, Fase 3.
 *
 * The live telemetry trace, track map, tyre/fuel panels and the
 * coaching/strategy feed remain on the legacy dashboard
 * (src/dashboard/static/index.html) until migrated in a follow-up slice.
 */
function App() {
  const { connected, session, laps, pattern, sessionReport } = useDashboardEvents()

  return (
    <main className="dashboard">
      <header>
        <h1>AI-TrackEngineer</h1>
        <span className={connected ? 'tag live' : 'tag off'}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
        {session && (
          <>
            <span className="tag">{session.track}</span>
            <span className="tag">{session.car}</span>
          </>
        )}
      </header>
      <section className="panel">
        <h2>Lap History</h2>
        <LapHistoryTable laps={laps} />
        <SessionReportPanel report={sessionReport} />
      </section>
      <section className="panel">
        <PatternPanel pattern={pattern} />
      </section>
    </main>
  )
}

export default App

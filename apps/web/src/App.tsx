import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import { useData } from './hooks'
import { ClaimPage, DatasetsPage, MeetingPage, PeoplePage, PersonaPage, SettingsPage, SimulationPage, TimelinePage } from './pages'
import './style.css'

export function AppRoutes() {
  const health = useData<{ status: string }>('/health')
  return <div className="shell">
    <aside className="sidebar">
      <Link className="brand" to="/datasets">PersonaForge</Link>
      <p className="tagline">Evidence-backed persona research</p>
      <nav>
        <NavLink to="/datasets">Datasets</NavLink>
        <NavLink to="/people">People</NavLink>
        <NavLink to="/timeline">Timeline</NavLink>
        <NavLink to="/meetings">Meetings</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <p className="api-status">API: {health.data?.status === 'ok' ? 'Healthy' : health.error ? 'Unavailable' : 'Checking…'}</p>
    </aside>
    <main className="content"><Routes>
      <Route path="/datasets" element={<DatasetsPage />} />
      <Route path="/people" element={<PeoplePage />} />
      <Route path="/people/:id/persona" element={<PersonaPage />} />
      <Route path="/claims/:id" element={<ClaimPage />} />
      <Route path="/timeline" element={<TimelinePage />} />
      <Route path="/meetings" element={<MeetingPage />} />
      <Route path="/meetings/:id" element={<MeetingPage />} />
      <Route path="/simulation/:personId" element={<SimulationPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<DatasetsPage />} />
    </Routes></main>
  </div>
}

export function App() { return <BrowserRouter><AppRoutes /></BrowserRouter> }

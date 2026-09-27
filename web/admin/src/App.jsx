import { useEffect, useState } from 'react'
import { apiFetch, login, logout, UnauthorizedError } from './api'
import Farmers from './tabs/Farmers'
import Fields from './tabs/Fields'
import BugReports from './tabs/BugReports'
import Feedback from './tabs/Feedback'
import AuditLog from './tabs/AuditLog'
import './theme.css'

const TABS = ['overview', 'farmers', 'fields', 'bug-reports', 'feedback', 'audit-log']

function LoginForm({ onLoggedIn }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    const res = await login(email, password)
    if (res.redirected || res.ok) onLoggedIn()
    else setError('Invalid email or password')
  }

  return (
    <form onSubmit={submit} className="glass-panel" style={{ maxWidth: 360, margin: '4rem auto' }}>
      <h2>Admin sign in</h2>
      {error && <p style={{ color: 'crimson' }}>{error}</p>}
      <div><input type="email" placeholder="Email" value={email} style={{ width: '100%' }}
             onChange={(e) => setEmail(e.target.value)} required /></div>
      <div><input type="password" placeholder="Password" value={password} style={{ width: '100%' }}
             onChange={(e) => setPassword(e.target.value)} required /></div>
      <button className="btn-primary" type="submit">Log in</button>
    </form>
  )
}

function Overview() {
  const [data, setData] = useState(null)
  useEffect(() => {
    Promise.all([apiFetch('/v2/admin/farmers'), apiFetch('/v2/admin/fields')])
      .then(([farmers, fields]) => setData({ farmers: farmers.items, fields: fields.items }))
  }, [])
  if (!data) return <p>Loading…</p>
  return (
    <div className="glass-panel">
      <h3>Overview</h3>
      <p>Farmers: {data.farmers.length} · Fields: {data.fields.length}</p>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(null)
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    apiFetch('/v2/admin/farmers').then(() => setAuthed(true))
      .catch((e) => setAuthed(e instanceof UnauthorizedError ? false : false))
  }, [])

  if (authed === null) return <p style={{ padding: '2rem' }}>Loading…</p>
  if (!authed) return <LoginForm onLoggedIn={() => setAuthed(true)} />

  return (
    <div style={{ padding: '2rem', maxWidth: 1100, margin: '0 auto' }}>
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
        <button onClick={() => logout().then(() => setAuthed(false))}>Log out</button>
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'farmers' && <Farmers />}
      {tab === 'fields' && <Fields />}
      {tab === 'bug-reports' && <BugReports />}
      {tab === 'feedback' && <Feedback />}
      {tab === 'audit-log' && <AuditLog />}
    </div>
  )
}

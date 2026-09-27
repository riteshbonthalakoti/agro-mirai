import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import ConfirmDeleteModal from '../ConfirmDeleteModal'

const STATUSES = ['open', 'triaged', 'in_progress', 'resolved']

export default function BugReports() {
  const [reports, setReports] = useState([])
  const [deleting, setDeleting] = useState(null)

  const load = () => apiFetch('/v2/admin/bug-reports').then((r) => setReports(r.items))
  useEffect(() => { load() }, [])

  useEffect(() => {
    const source = new EventSource('/v2/admin/stream/bug-reports')
    source.onmessage = (event) => {
      const report = JSON.parse(event.data)
      setReports((prev) => [report, ...prev.filter((r) => r.id !== report.id)])
    }
    return () => source.close()
  }, [])

  const setStatus = async (report, status) => {
    await apiFetch(`/v2/admin/bug-reports/${report.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    load()
  }

  const doDelete = async (report) => {
    await apiFetch(`/v2/admin/bug-reports/${report.id}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="glass-panel">
      <h3>Bug Reports ({reports.length})</h3>
      <table>
        <thead><tr><th>When</th><th>Category</th><th>Message</th><th>Status</th><th /></tr></thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.id}>
              <td>{r.created_at}</td><td>{r.category || '—'}</td><td>{r.message || '—'}</td>
              <td>
                <select value={r.status} onChange={(e) => setStatus(r, e.target.value)}>
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </td>
              <td><button className="btn-danger" onClick={() => setDeleting(r)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {deleting && (
        <ConfirmDeleteModal
          targetLabel={deleting.id}
          onConfirm={() => doDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}

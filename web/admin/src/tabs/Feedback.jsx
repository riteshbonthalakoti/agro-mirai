import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function Feedback() {
  const [report, setReport] = useState(null)
  useEffect(() => { apiFetch('/v2/admin/feedback').then(setReport) }, [])
  if (!report) return <div className="glass-panel">Loading…</div>

  return (
    <div className="glass-panel">
      <h3>System-wide Feedback</h3>
      <p>
        Total entries: {report.total_entries} · Mean rating: {report.mean_rating ?? '—'} ·
        Helpful rate: {report.helpful_rate ?? '—'}
      </p>
      <h4>By severity</h4>
      <table>
        <thead><tr><th>Severity</th><th>Count</th><th>Mean rating</th><th>Helpful rate</th></tr></thead>
        <tbody>
          {report.by_severity.map((b) => (
            <tr key={b.severity}>
              <td>{b.severity}</td><td>{b.count}</td><td>{b.mean_rating ?? '—'}</td><td>{b.helpful_rate ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

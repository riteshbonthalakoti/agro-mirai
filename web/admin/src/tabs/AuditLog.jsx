import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function AuditLog() {
  const [entries, setEntries] = useState([])
  useEffect(() => { apiFetch('/v2/admin/audit-log').then((r) => setEntries(r.items)) }, [])

  return (
    <div className="glass-panel">
      <h3>Audit Log ({entries.length})</h3>
      <table>
        <thead><tr><th>When</th><th>Action</th><th>Target</th></tr></thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td>{e.created_at}</td><td>{e.action}</td>
              <td>{e.target_type}:{e.target_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

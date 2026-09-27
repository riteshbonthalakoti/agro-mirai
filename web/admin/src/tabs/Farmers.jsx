import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import ConfirmDeleteModal from '../ConfirmDeleteModal'

export default function Farmers() {
  const [farmers, setFarmers] = useState([])
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = () => apiFetch('/v2/admin/farmers').then((r) => setFarmers(r.items))
  useEffect(() => { load() }, [])

  const save = async (farmer, patch) => {
    await apiFetch(`/v2/admin/farmers/${farmer.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    setEditing(null)
    load()
  }

  const doDelete = async (farmer) => {
    await apiFetch(`/v2/admin/farmers/${farmer.id}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="glass-panel">
      <h3>Farmers ({farmers.length})</h3>
      <table>
        <thead><tr><th>Name</th><th>Phone</th><th>District</th><th>Role</th><th /></tr></thead>
        <tbody>
          {farmers.map((f) => (
            <tr key={f.id}>
              <td>{f.name}</td><td>{f.phone || '—'}</td><td>{f.district || '—'}</td><td>{f.role}</td>
              <td>
                <button onClick={() => setEditing(f)}>Edit</button>{' '}
                <button className="btn-danger" onClick={() => setDeleting(f)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {editing && (
        <div className="glass-panel">
          <label>District: </label>
          <input defaultValue={editing.district || ''} placeholder="District"
                 onBlur={(e) => save(editing, { district: e.target.value })} />
          <button onClick={() => setEditing(null)}>Close</button>
        </div>
      )}

      {deleting && (
        <ConfirmDeleteModal
          targetLabel={deleting.name}
          onConfirm={() => doDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}

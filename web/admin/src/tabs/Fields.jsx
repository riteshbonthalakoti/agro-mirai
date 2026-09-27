import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import ConfirmDeleteModal from '../ConfirmDeleteModal'

export default function Fields() {
  const [fields, setFields] = useState([])
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = () => apiFetch('/v2/admin/fields').then((r) => setFields(r.items))
  useEffect(() => { load() }, [])

  const save = async (field, patch) => {
    await apiFetch(`/v2/admin/fields/${field.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    setEditing(null)
    load()
  }

  const doDelete = async (field) => {
    await apiFetch(`/v2/admin/fields/${field.id}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="glass-panel">
      <h3>Fields ({fields.length})</h3>
      <table>
        <thead><tr><th>Name</th><th>Farmer</th><th>Soil</th><th>Crop</th><th /></tr></thead>
        <tbody>
          {fields.map((f) => (
            <tr key={f.id}>
              <td>{f.name}</td><td>{f.farmer_id}</td><td>{f.soil_type || '—'}</td><td>{f.current_crop || '—'}</td>
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
          <label>Current crop: </label>
          <input defaultValue={editing.current_crop || ''} placeholder="Crop"
                 onBlur={(e) => save(editing, { current_crop: e.target.value })} />
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

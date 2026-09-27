import { useState } from 'react'

export default function ConfirmDeleteModal({ targetLabel, onConfirm, onCancel }) {
  const [typed, setTyped] = useState('')
  const matches = typed === targetLabel

  return (
    <div className="glass-panel" style={{
      position: 'fixed', top: '30%', left: '50%', transform: 'translateX(-50%)', zIndex: 10,
      minWidth: 320,
    }}>
      <p>Type <strong>{targetLabel}</strong> to confirm deletion. This cannot be undone.</p>
      <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus style={{ width: '100%' }} />
      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
        <button className="btn-danger" disabled={!matches} onClick={onConfirm}>Delete</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

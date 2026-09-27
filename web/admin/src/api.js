// Same-origin fetch helper, credentials included so the session cookie
// (set by the Flask backend via either public URL's rewrite) is sent.
export class UnauthorizedError extends Error {}

export async function apiFetch(path, opts = {}) {
  const res = await fetch(path, { ...opts, credentials: 'same-origin' })
  if (res.status === 401) throw new UnauthorizedError('unauthorized')
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.error?.message || `${path} returned ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const login = (email, password) =>
  fetch('/admin/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ email, password }),
  })

export const logout = () =>
  fetch('/admin/logout', { method: 'POST', credentials: 'same-origin' })

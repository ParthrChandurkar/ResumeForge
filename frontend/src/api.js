const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...options })
    if (!response.ok) {
      let message = `Request failed (${response.status})`
      try { message = (await response.json()).detail || message } catch { /* use fallback */ }
      throw new Error(message)
    }
    if (response.status === 204) return null
    return await response.json()
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot reach ResumeForge. Make sure the backend is running.')
    throw error
  }
}

export const api = {
  auth: {
    me: () => request('/auth/me'),
    login: (email, password) => request('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }),
    logout: () => request('/auth/logout', { method: 'POST' }),
  },
  templates: () => request('/templates'),
  uploadTemplate: (formData) => request('/templates', { method: 'POST', body: formData }),
  deleteTemplate: (id) => request(`/templates/${id}`, { method: 'DELETE' }),
  originalTemplate: (id) => `${API_BASE}/templates/${id}/original`,
  tailor: (payload) => request('/tailor', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }),
  history: () => request('/tailor/history'),
  run: (id) => request(`/tailor/${id}`),
  deleteRun: (id) => request(`/tailor/${id}`, { method: 'DELETE' }),
  resumeTex: (id) => `${API_BASE}/tailor/${id}/resume.tex`,
  coverLetterTex: (id) => `${API_BASE}/tailor/${id}/cover-letter.tex`,
}

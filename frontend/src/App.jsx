import React, { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api'

const CATEGORIES = [
  { value: 'billing', label: 'Billing' },
  { value: 'technical', label: 'Technical' },
  { value: 'account', label: 'Account' },
  { value: 'general', label: 'General' },
]
const PRIORITIES = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]
const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

function truncate(str, len = 120) {
  if (!str || str.length <= len) return str || ''
  return str.slice(0, len) + '...'
}

function TicketForm({ onSuccess }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [priority, setPriority] = useState('medium')
  const [classifyLoading, setClassifyLoading] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchClassify = useCallback(async () => {
    if (!description.trim()) return
    setClassifyLoading(true)
    try {
      const res = await fetch(`${API_BASE}/tickets/classify/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: description.trim() }),
      })
      const data = await res.json()
      if (data.suggested_category) setCategory(data.suggested_category)
      if (data.suggested_priority) setPriority(data.suggested_priority)
    } catch (_) {
      // Graceful: keep form usable without suggestions
    } finally {
      setClassifyLoading(false)
    }
  }, [description])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!title.trim() || !description.trim()) {
      setError('Title and description are required.')
      return
    }
    if (title.length > 200) {
      setError('Title must be at most 200 characters.')
      return
    }
    setSubmitLoading(true)
    try {
      const res = await fetch(`${API_BASE}/tickets/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          category,
          priority,
          status: 'open',
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setError(err.detail || JSON.stringify(err) || 'Failed to create ticket')
        return
      }
      const ticket = await res.json()
      setTitle('')
      setDescription('')
      setCategory('general')
      setPriority('medium')
      setSuccess('Ticket created.')
      onSuccess && onSuccess(ticket)
    } catch (err) {
      setError('Network error. Is the backend running?')
    } finally {
      setSubmitLoading(false)
    }
  }

  return (
    <div className="section">
      <h2>Submit a ticket</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>Title (max 200 characters)</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Brief title"
          />
        </div>
        <div className="form-row">
          <label>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={fetchClassify}
            placeholder="Describe your issue. Category and priority will be suggested."
          />
          {classifyLoading && <div className="loading">Suggesting category & priority…</div>}
        </div>
        <div className="form-row">
          <label>Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={submitLoading}>
            {submitLoading ? 'Submitting…' : 'Submit ticket'}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}
      </form>
    </div>
  )
}

function StatsDashboard({ refreshKey }) {
  const [stats, setStats] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/tickets/stats/`)
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setStats(data); setErr('') })
      .catch(() => { if (!cancelled) setErr('Failed to load stats') })
    return () => { cancelled = true }
  }, [refreshKey])

  if (err) return <div className="section"><p className="error">{err}</p></div>
  if (!stats) return <div className="section"><p className="loading">Loading stats…</p></div>

  return (
    <div className="section">
      <h2>Stats</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="value">{stats.total_tickets}</div>
          <div className="label">Total tickets</div>
        </div>
        <div className="stat-card">
          <div className="value">{stats.open_tickets}</div>
          <div className="label">Open</div>
        </div>
        <div className="stat-card">
          <div className="value">{stats.avg_tickets_per_day}</div>
          <div className="label">Avg per day</div>
        </div>
      </div>
      <div style={{ marginTop: '0.75rem' }}>
        <strong>Priority:</strong>
        <div className="breakdown">
          {Object.entries(stats.priority_breakdown || {}).map(([k, v]) => (
            <span key={k}>{k}: {v}</span>
          ))}
        </div>
      </div>
      <div style={{ marginTop: '0.5rem' }}>
        <strong>Category:</strong>
        <div className="breakdown">
          {Object.entries(stats.category_breakdown || {}).map(([k, v]) => (
            <span key={k}>{k}: {v}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function TicketList({ refreshKey, onRefresh }) {
  const [tickets, setTickets] = useState([])
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchTickets = useCallback(() => {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (priority) params.set('priority', priority)
    if (statusFilter) params.set('status', statusFilter)
    if (search.trim()) params.set('search', search.trim())
    setLoading(true)
    fetch(`${API_BASE}/tickets/?${params}`)
      .then((r) => r.json())
      .then(setTickets)
      .finally(() => setLoading(false))
  }, [category, priority, statusFilter, search])

  useEffect(() => {
    fetchTickets()
  }, [fetchTickets, refreshKey])

  const updateStatus = async (id, status) => {
    try {
      const res = await fetch(`${API_BASE}/tickets/${id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (res.ok) {
        fetchTickets()
        onRefresh && onRefresh()
        setSelected((s) => (s && s.id === id ? { ...s, status } : s))
      }
    } catch (_) {}
  }

  return (
    <div className="section">
      <h2>Tickets</h2>
      <div className="filters">
        <input
          type="text"
          placeholder="Search title & description"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>
      {loading ? (
        <p className="loading">Loading…</p>
      ) : (
        <ul className="ticket-list">
          {tickets.map((t) => (
            <li
              key={t.id}
              className="ticket-item"
              onClick={() => setSelected(t)}
            >
              <div className="ticket-meta">
                <span className={`badge badge-${t.priority}`}>{t.priority}</span>
                {t.category} · {t.status}
              </div>
              <h3>{t.title}</h3>
              <div className="ticket-desc">{truncate(t.description)}</div>
              <div className="ticket-meta">{new Date(t.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{selected.title}</h3>
            <p><strong>Category:</strong> {selected.category} · <strong>Priority:</strong> {selected.priority}</p>
            <p>{selected.description}</p>
            <p><strong>Status:</strong></p>
            <div className="modal-actions">
              {STATUSES.map((s) => (
                <button
                  key={s.value}
                  className="btn"
                  style={{ background: selected.status === s.value ? '#e0e7ff' : '#f1f5f9' }}
                  onClick={() => updateStatus(selected.id, s.value)}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <button className="btn" style={{ marginTop: '0.5rem' }} onClick={() => setSelected(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const onNewTicket = () => setRefreshKey((k) => k + 1)

  return (
    <div className="app">
      <h1>Support Ticket System</h1>
      <TicketForm onSuccess={onNewTicket} />
      <StatsDashboard refreshKey={refreshKey} />
      <TicketList refreshKey={refreshKey} onRefresh={() => setRefreshKey((k) => k + 1)} />
    </div>
  )
}

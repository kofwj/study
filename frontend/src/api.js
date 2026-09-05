export let selectedKid = ''
export function setSelectedKid(id) { selectedKid = id || '' }

const j = async (url, opts = {}) => {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  if (selectedKid) {
    url += (url.includes('?') ? '&' : '?') + 'selected_kid=' + encodeURIComponent(selectedKid)
  }
  const r = await fetch(url, { ...opts, headers, credentials: 'include' })
  if (!r.ok) {
    let msg = `请求失败 (${r.status})`
    try { msg = (await r.json()).detail || msg } catch {}
    const err = new Error(msg)
    err.status = r.status
    throw err
  }
  if (r.status === 204) return null
  return r.json()
}

const body = (o) => (o ? { body: JSON.stringify(o) } : {})

export const api = {
  login: (account, pin) => j('/api/auth/login', { method: 'POST', ...body({ account, pin }) }),
  register: (o) => j('/api/auth/register', { method: 'POST', ...body(o) }),
  join: (o) => j('/api/auth/join', { method: 'POST', ...body(o) }),
  logout: () => j('/api/auth/logout', { method: 'POST' }),
  me: () => j('/api/auth/me'),

  tasks: () => j('/api/tasks'),
  checkin: () => j('/api/checkin', { method: 'POST' }),
  complete: (task_id, metrics) => j('/api/complete', { method: 'POST', ...body({ task_id, metrics }) }),
  cancel: (task_id) => j('/api/cancel', { method: 'POST', ...body({ task_id }) }),
  rewards: () => j('/api/rewards'),
  redeem: (reward_id) => j('/api/rewards/redeem', { method: 'POST', ...body({ reward_id }) }),
  redemptions: () => j('/api/redemptions'),
  achievements: () => j('/api/achievements'),
  ranks: () => j('/api/ranks'),
  boxes: () => j('/api/boxes'),
  openBox: () => j('/api/open_box', { method: 'POST' }),
  ledger: () => j('/api/ledger?limit=15'),
  setKidName: (name) => j('/api/kid-name', { method: 'POST', ...body({ name }) }),
  dailyHistory: (id) => j(`/api/daily/${id}/history`),

  admin: {
    changePin: (pin) => j('/api/admin/pin', { method: 'POST', ...body({ pin }) }),
    ranks: () => j('/api/admin/ranks'),
    createReward: (o) => j('/api/admin/rewards', { method: 'POST', ...body(o) }),
    updateReward: (id, o) => j(`/api/admin/rewards/${id}`, { method: 'PUT', ...body(o) }),
    delReward: (id) => j(`/api/admin/rewards/${id}`, { method: 'DELETE' }),
    redemptions: () => j('/api/admin/redemptions'),
    weekly: () => j('/api/admin/weekly'),
    approveRedeem: (id) => j(`/api/admin/redemptions/${id}/approve`, { method: 'POST' }),
    rejectRedeem: (id) => j(`/api/admin/redemptions/${id}/reject`, { method: 'POST' }),
    deliverRedeem: (id) => j(`/api/admin/redemptions/${id}/deliver`, { method: 'POST' }),
    createRank: (o) => j('/api/admin/ranks', { method: 'POST', ...body(o) }),
    updateRank: (id, o) => j(`/api/admin/ranks/${id}`, { method: 'PUT', ...body(o) }),
    delRank: (id) => j(`/api/admin/ranks/${id}`, { method: 'DELETE' }),
    createTask: (o) => j('/api/admin/tasks', { method: 'POST', ...body(o) }),
    updateTask: (id, o) => j(`/api/admin/tasks/${id}`, { method: 'PUT', ...body(o) }),
    delTask: (id) => j(`/api/admin/tasks/${id}`, { method: 'DELETE' }),
    createDaily: (o) => j('/api/admin/daily', { method: 'POST', ...body(o) }),
    updateDaily: (id, o) => j(`/api/admin/daily/${id}`, { method: 'PUT', ...body(o) }),
    delDaily: (id) => j(`/api/admin/daily/${id}`, { method: 'DELETE' }),
    setCursor: (o) => j('/api/admin/cursor', { method: 'POST', ...body(o) }),

    setProgressLock: (on) => j('/api/admin/progress-lock', { method: 'POST', ...body({ on }) }),
    tests: () => j('/api/admin/tests'),
    createTest: (o) => j('/api/admin/tests', { method: 'POST', ...body(o) }),
    delTest: (id) => j(`/api/admin/tests/${id}`, { method: 'DELETE' }),
    invite: (role) => j('/api/admin/invite', { method: 'POST', ...body({ role: role || 'parent' }) }),
    members: () => j('/api/admin/members'),
    delMember: (id) => j(`/api/admin/members/${id}`, { method: 'DELETE' }),
    family: () => j('/api/admin/family'),
    setInviteProtect: (enabled) => j('/api/admin/family/invite_protect', { method: 'PUT', ...body({ enabled }) }),
    kids: () => j('/api/admin/kids'),
    createKid: (o) => j('/api/admin/kids', { method: 'POST', ...body(o) }),
    updateKid: (id, o) => j(`/api/admin/kids/${id}`, { method: 'PUT', ...body(o) }),
    delKid: (id) => j(`/api/admin/kids/${id}`, { method: 'DELETE' }),
  },
}

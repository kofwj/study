const j = async (url, opts = {}, admin = false) => {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  if (admin) headers['X-Admin-Pin'] = sessionStorage.getItem('admin_pin') || ''
  const r = await fetch(url, { ...opts, headers })
  if (!r.ok) {
    let msg = `请求失败 (${r.status})`
    try { msg = (await r.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return r.json()
}

const body = (o) => (o ? { body: JSON.stringify(o) } : {})

export const api = {
  // —— 娃端 ——
  tasks: () => j('/api/tasks'),
  checkin: () => j('/api/checkin', { method: 'POST' }),
  complete: (task_id, metrics) => j('/api/complete', { method: 'POST', ...body({ task_id, metrics }) }),
  cancel: (task_id) => j('/api/cancel', { method: 'POST', ...body({ task_id }) }),
  rewards: () => j('/api/rewards'),
  redeem: (reward_id) => j('/api/rewards/redeem', { method: 'POST', ...body({ reward_id }) }),
  ledger: () => j('/api/ledger?limit=15'),
  setKidName: (name) => j('/api/kid-name', { method: 'POST', ...body({ name }) }),
  customTask: (o) => j('/api/custom-task', { method: 'POST', ...body(o) }),
  delCustom: (id) => j(`/api/tasks/${id}`, { method: 'DELETE' }),

  // —— 家长端 ——
  admin: {
    verify: (pin) => j('/api/admin/verify', { method: 'POST', ...body({ pin }) }),
    changePin: (pin) => j('/api/admin/pin', { method: 'POST', ...body({ pin }) }, true),
    ranks: () => j('/api/admin/ranks'),
    createReward: (o) => j('/api/admin/rewards', { method: 'POST', ...body(o) }, true),
    updateReward: (id, o) => j(`/api/admin/rewards/${id}`, { method: 'PUT', ...body(o) }, true),
    delReward: (id) => j(`/api/admin/rewards/${id}`, { method: 'DELETE' }, true),
    createRank: (o) => j('/api/admin/ranks', { method: 'POST', ...body(o) }, true),
    updateRank: (id, o) => j(`/api/admin/ranks/${id}`, { method: 'PUT', ...body(o) }, true),
    delRank: (id) => j(`/api/admin/ranks/${id}`, { method: 'DELETE' }, true),
    createTask: (o) => j('/api/admin/tasks', { method: 'POST', ...body(o) }, true),
    updateTask: (id, o) => j(`/api/admin/tasks/${id}`, { method: 'PUT', ...body(o) }, true),
    delTask: (id) => j(`/api/admin/tasks/${id}`, { method: 'DELETE' }, true),
    createDaily: (o) => j('/api/admin/daily', { method: 'POST', ...body(o) }, true),
    updateDaily: (id, o) => j(`/api/admin/daily/${id}`, { method: 'PUT', ...body(o) }, true),
    delDaily: (id) => j(`/api/admin/daily/${id}`, { method: 'DELETE' }, true),
  },
}
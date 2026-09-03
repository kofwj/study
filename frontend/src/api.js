const j = async (url, opts = {}) => {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    let msg = `请求失败 (${r.status})`
    try { msg = (await r.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return r.json()
}

export const api = {
  tasks: () => j('/api/tasks'),
  checkin: () => j('/api/checkin', { method: 'POST' }),
  complete: (task_id, metrics) => j('/api/complete', { method: 'POST', body: JSON.stringify({ task_id, metrics }) }),
  cancel: (task_id) => j('/api/cancel', { method: 'POST', body: JSON.stringify({ task_id }) }),
  rewards: () => j('/api/rewards'),
  redeem: (reward_id) => j('/api/rewards/redeem', { method: 'POST', body: JSON.stringify({ reward_id }) }),
  ledger: () => j('/api/ledger?limit=15'),
}
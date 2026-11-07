const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  let response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (cause) {
    const error = new Error('Could not reach the outbox service. Is it running?');
    error.cause = cause;
    throw error;
  }
  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = { error: { message: raw } };
    }
  }
  if (!response.ok) {
    const info = data?.error || {};
    const message = info.message || `Request failed with HTTP ${response.status}.`;
    const error = new Error(message);
    error.status = response.status;
    error.code = info.code;
    error.currentStatus = info.current_status;
    error.allowedActions = info.allowed_actions;
    error.details = info.details;
    error.data = data;
    throw error;
  }
  return data;
}

function queryString(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export const api = {
  info: () => request('/api/info'),
  health: () => request('/api/health'),
  listMessages: (params) => request(`/api/messages${queryString(params)}`),
  getMessage: (id) => request(`/api/messages/${encodeURIComponent(id)}`),
  getHistory: (id) => request(`/api/messages/${encodeURIComponent(id)}/history`),
  getHandoff: (id) => request(`/api/messages/${encodeURIComponent(id)}/handoff`),
  getWebhookEvents: (id) => request(`/api/messages/${encodeURIComponent(id)}/webhook-events`),
  approve: (id) => request(`/api/messages/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  reject: (id, reason) => request(`/api/messages/${encodeURIComponent(id)}/reject`, {
    method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ reason })
  }),
  cancel: (id, reason) => request(`/api/messages/${encodeURIComponent(id)}/cancel`, {
    method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(reason ? { reason } : {})
  }),
  markSent: (id) => request(`/api/messages/${encodeURIComponent(id)}/mark-sent`, {
    method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ confirmed: true })
  }),
  patch: (id, payload) => request(`/api/messages/${encodeURIComponent(id)}`, {
    method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(payload)
  }),
  destinations: () => request('/api/destinations'),
  putLabel: (channel, destination, label) => request('/api/destinations/label', {
    method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify({ channel, destination, label })
  }),
  deleteLabel: (channel, destination) => request(
    `/api/destinations/label?channel=${encodeURIComponent(channel)}&destination=${encodeURIComponent(destination)}`,
    { method: 'DELETE' }
  )
};

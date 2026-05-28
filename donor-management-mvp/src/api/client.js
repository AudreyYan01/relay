const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  getDashboard: () => request('/dashboard'),
  getDonors: (params = {}) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.status) q.set('status', params.status);
    if (params.relationship_type) q.set('relationship_type', params.relationship_type);
    if (params.limit) q.set('limit', params.limit);
    return request(`/donors?${q.toString()}`);
  },
  getDonor: (id) => request(`/donors/${id}`),
  getDonorBrief: (id) => request(`/donors/${id}/brief`),
  updateFollowUp: (id, status) =>
    request(`/donors/${id}/followup`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  logTouchpoint: (id, note) =>
    request(`/donors/${id}/touchpoints`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),
  overrideStatus: (id, status) =>
    request(`/donors/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  getEvents: () => request('/events'),
  recordDisposition: (donorId, logId, disposition, rationale = null, editedAction = null) =>
    request(`/donors/${donorId}/recommendation/${logId}/disposition`, {
      method: 'POST',
      body: JSON.stringify({ disposition, rationale, edited_action: editedAction }),
    }),
};

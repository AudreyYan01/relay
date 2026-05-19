import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

const STATUSES = ['', 'NEW', 'ACTIVE', 'WARM', 'LAPSED'];
const REL_TYPES = ['', 'DONOR', 'VOLUNTEER', 'SPONSOR', 'PROSPECT'];
const TIER_RANGES = { BRONZE: 'Under $100', SILVER: '$100–$499', GOLD: '$500–$1,999', PLATINUM: '$2,000+' };
const PRIORITY_FORMULA = 'Tier pts (BRONZE 5, SILVER 20, GOLD 35, PLATINUM 40) + Recency pts (30 max, −1 per 5 days idle) + Engagement pts (6 per completed event, max 30)';

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

export default function SupporterList() {
  const [donors, setDonors] = useState([]);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [relType, setRelType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const load = useCallback(() => {
    setLoading(true);
    api.getDonors({
      search: search || undefined,
      status: status || undefined,
      relationship_type: relType || undefined,
    })
      .then((d) => { setDonors(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [search, status, relType]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const handleExport = () => {
    const headers = ['Name', 'Organization', 'Type', 'Status', 'Total Given', 'Last Touch', 'Priority', 'Follow-Up'];
    const rows = donors.map((d) => [
      d.FullName,
      d.Organization || '',
      d.RelationshipType,
      d.Status,
      d.TotalDonated || 0,
      fmtDate(d.LastActivityAt || d.LastDonationAt),
      d.PriorityScore,
      d.FollowUpStatus,
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'supporters.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const filterParts = [
    status && status,
    relType && relType,
    search && `"${search}"`,
  ].filter(Boolean);

  const subtitleText = `${donors.length} supporter${donors.length !== 1 ? 's' : ''}${
    filterParts.length > 0 ? ` matching ${filterParts.join(', ')}` : ''
  } · sorted by priority score`;

  return (
    <div>
      <h1>Supporters</h1>
      <p className="subtitle">{subtitleText}</p>

      <div className="list-controls">
        <input
          className="search-input"
          placeholder="Search by name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="filter-select" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s || 'All stages'}</option>
          ))}
        </select>
        <select className="filter-select" value={relType} onChange={(e) => setRelType(e.target.value)}>
          {REL_TYPES.map((r) => (
            <option key={r} value={r}>{r || 'All types'}</option>
          ))}
        </select>
        <button className="export-btn" onClick={handleExport} disabled={donors.length === 0}>
          Export CSV
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="section" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Tier</th>
              <th>Status</th>
              <th>Total Given</th>
              <th>Last Touch</th>
              <th title={PRIORITY_FORMULA} style={{ cursor: 'help' }}>Priority ⓘ</th>
              <th>Follow-Up</th>
            </tr>
          </thead>
          <tbody>
            {!loading && donors.map((d) => (
              <tr key={d.DonorID} onClick={() => navigate(`/supporters/${d.DonorID}`)}>
                <td style={{ fontWeight: 600 }}>
                  {d.FullName}
                  {d.Organization && (
                    <div style={{ fontWeight: 400, fontSize: 11, color: '#a0aec0', marginTop: 2 }}>{d.Organization}</div>
                  )}
                </td>
                <td><span className={`badge badge-${d.RelationshipType}`}>{d.RelationshipType}</span></td>
                <td>
                  <span
                    className={`badge badge-${d.Tier}`}
                    title={`${d.Tier}: lifetime giving ${TIER_RANGES[d.Tier] || ''}`}
                  >
                    {d.Tier}
                  </span>
                </td>
                <td><span className={`badge badge-${d.Status}`}>{d.Status}</span></td>
                <td className="amount">{fmtMoney(d.TotalDonated)}</td>
                <td>{fmtDate(d.LastActivityAt || d.LastDonationAt)}</td>
                <td style={{ fontWeight: 600 }}>{d.PriorityScore}</td>
                <td><span className={`badge badge-${d.FollowUpStatus}`}>{d.FollowUpStatus?.replace('_', ' ')}</span></td>
              </tr>
            ))}
            {loading && (
              <tr><td colSpan={8} className="empty">Loading…</td></tr>
            )}
            {!loading && donors.length === 0 && (
              <tr><td colSpan={8} className="empty">No supporters match your filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

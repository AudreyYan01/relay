import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

function fmt(n) {
  return n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

const TIER_RANGES = { BRONZE: 'Under $100', SILVER: '$100–$499', GOLD: '$500–$1,999', PLATINUM: '$2,000+' };

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getDashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">Failed to load dashboard: {error}</div>;
  if (!data)  return <div className="loading">Loading…</div>;

  const subtitle = data.recent_event
    ? `Most recent event: ${data.recent_event.ActivityName} · ${fmtDate(data.recent_event.ActivityStartTime)}`
    : 'Supporter overview';

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">{subtitle}</p>

      <div className="cards">
        <div className="card">
          <div className="card-label">Total Supporters</div>
          <div className="card-value">{fmt(data.total_supporters)}</div>
        </div>
        <div className="card">
          <div className="card-label">Total Donated</div>
          <div className="card-value">${fmt(data.total_donated)}</div>
        </div>
        <div className="card">
          <div className="card-label">Need Follow-Up</div>
          <div className="card-value">{fmt(data.followup_needed)}</div>
          <div className="card-sub">active/warm, not yet started</div>
        </div>
        <div className="card">
          <div className="card-label">High Priority</div>
          <div className="card-value">{fmt(data.high_priority)}</div>
          <div className="card-sub">score ≥ 50</div>
        </div>
      </div>

      <div className="two-col">
        <div className="section">
          <h2>Top Supporters by Total Given</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Tier</th>
                <th>Status</th>
                <th>Total Given</th>
                <th>Follow-Up</th>
              </tr>
            </thead>
            <tbody>
              {data.top_donors.map((s, i) => (
                <tr key={s.DonorID} onClick={() => navigate(`/supporters/${s.DonorID}`)}>
                  <td style={{ color: '#a0aec0', fontWeight: 600 }}>{i + 1}</td>
                  <td style={{ fontWeight: 600 }}>{s.FullName}</td>
                  <td>
                    <span
                      className={`badge badge-${s.Tier}`}
                      title={`${s.Tier}: lifetime giving ${TIER_RANGES[s.Tier] || ''}`}
                    >
                      {s.Tier}
                    </span>
                  </td>
                  <td><span className={`badge badge-${s.Status}`}>{s.Status}</span></td>
                  <td style={{ fontWeight: 700, color: '#276749' }}>{fmtMoney(s.TotalDonated)}</td>
                  <td><span className={`badge badge-${s.FollowUpStatus}`}>{s.FollowUpStatus?.replace('_', ' ')}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 14, textAlign: 'right' }}>
            <button
              className="view-all-btn"
              onClick={() => navigate('/supporters')}
            >
              View all supporters →
            </button>
          </div>
        </div>

        <div className="section">
          <h2>Recent Donations</h2>
          <ul className="signal-list">
            {data.recent_donations.length === 0 && (
              <li style={{ color: '#a0aec0', fontSize: 13, padding: '12px 0' }}>No donations recorded.</li>
            )}
            {data.recent_donations.map((d) => (
              <li
                key={d.TransactionID}
                className="signal-item"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/supporters/${d.DonorID}`)}
              >
                <div className="signal-dot" />
                <div style={{ flex: 1 }}>
                  <div className="signal-name">{d.FullName}</div>
                  <div className="signal-meta">{fmtDate(d.TransactionDateTime)}</div>
                </div>
                <div style={{ fontWeight: 700, color: '#276749', fontSize: 13 }}>
                  {fmtMoney(d.TransactionAmount)}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

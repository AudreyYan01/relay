import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function initials(name) {
  if (!name) return '?';
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

const ENG_ICON = { ATTEND: '🎟', REGISTER: '📋', VOLUNTEER: '🤝' };
const TX_ICON  = { DONATION: '💛', TICKET: '🎫', MERCH: '👕', FEE: '📄', OTHER: '•' };
const FOLLOWUP_STATES = ['NOT_STARTED', 'PLANNED', 'COMPLETED'];
const TIER_RANGES = { BRONZE: 'Under $100', SILVER: '$100–$499', GOLD: '$500–$1,999', PLATINUM: '$2,000+' };
const PRIORITY_FORMULA = 'Tier pts (BRONZE 5, SILVER 20, GOLD 35, PLATINUM 40) + Recency pts (30 max, −1 per 5 days idle) + Engagement pts (6 per completed event, max 30)';

function BriefPanel({ donorId, donorEmail }) {
  const [brief, setBrief] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.getDonorBrief(donorId).then(setBrief).catch(() => {});
  }, [donorId]);

  if (!brief) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(brief.next_action).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const mailtoHref = donorEmail
    ? `mailto:${donorEmail}?subject=Following%20up&body=${encodeURIComponent(brief.next_action)}`
    : null;

  return (
    <div className="brief-panel">
      <h2>AI Relationship Brief</h2>

      <div className="brief-field">
        <label>Summary</label>
        <p>{brief.summary}</p>
      </div>
      <div className="brief-field">
        <label>Why This Supporter Matters</label>
        <p>{brief.why_matters}</p>
      </div>
      <div className="brief-field">
        <label>Recent Signal</label>
        <p>{brief.recent_signal}</p>
      </div>

      {brief.risk_flag && (
        <div className="brief-field">
          <label>Flag</label>
          <div className="risk-flag">{brief.risk_flag}</div>
        </div>
      )}

      <div className="brief-field">
        <label>Suggested Next Action</label>
        <div className="next-action-card">
          <p>{brief.next_action}</p>
        </div>
        <div className="brief-actions">
          <button className="brief-action-btn" onClick={handleCopy}>
            {copied ? '✓ Copied' : 'Copy message'}
          </button>
          {mailtoHref && (
            <a className="brief-action-btn" href={mailtoHref}>Open email draft</a>
          )}
        </div>
      </div>
    </div>
  );
}

function FollowUpToggle({ donorId, initial }) {
  const [status, setStatus] = useState(initial || 'NOT_STARTED');
  const [saving, setSaving] = useState(false);

  const handleClick = (s) => {
    if (s === status || saving) return;
    setSaving(true);
    api.updateFollowUp(donorId, s)
      .then(() => { setStatus(s); setSaving(false); })
      .catch(() => setSaving(false));
  };

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.5px', color: '#718096', marginBottom: 6 }}>
        Follow-Up Status
      </div>
      <div className="followup-toggle">
        {FOLLOWUP_STATES.map((s) => (
          <button
            key={s}
            className={`followup-btn ${status === s ? `selected-${s}` : ''}`}
            onClick={() => handleClick(s)}
            disabled={saving}
          >
            {s.replace('_', ' ')}
          </button>
        ))}
      </div>
    </div>
  );
}

function StatusSelect({ donorId, computedStatus, initialOverride }) {
  const [override, setOverride] = useState(initialOverride || null);
  const [saving, setSaving] = useState(false);
  const displayStatus = override || computedStatus;

  const handleChange = (val) => {
    if (saving) return;
    setSaving(true);
    api.overrideStatus(donorId, val)
      .then(() => { setOverride(val); setSaving(false); })
      .catch(() => setSaving(false));
  };

  const handleReset = () => {
    if (saving) return;
    setSaving(true);
    api.overrideStatus(donorId, null)
      .then(() => { setOverride(null); setSaving(false); })
      .catch(() => setSaving(false));
  };

  return (
    <span className="status-select-wrapper">
      <select
        value={displayStatus}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
        className={`status-select badge badge-${displayStatus}`}
      >
        {['NEW', 'ACTIVE', 'WARM', 'LAPSED'].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      {override && (
        <button
          className="reset-status-btn"
          onClick={handleReset}
          disabled={saving}
          title="Revert to auto-computed status"
        >
          ↺ auto
        </button>
      )}
    </span>
  );
}

export default function SupporterProfile() {
  const { id } = useParams();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);
  const [touchpoints, setTouchpoints] = useState([]);
  const [noteText, setNoteText] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);

  useEffect(() => {
    api.getDonor(id)
      .then((data) => {
        setProfile(data);
        setTouchpoints(data.touchpoints || []);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  const handleLogNote = () => {
    if (!noteText.trim() || noteSaving) return;
    setNoteSaving(true);
    api.logTouchpoint(id, noteText.trim())
      .then((tp) => {
        setTouchpoints((prev) => [tp, ...prev]);
        setNoteText('');
        setNoteSaving(false);
      })
      .catch(() => setNoteSaving(false));
  };

  if (error)   return <div className="error">{error}</div>;
  if (!profile) return <div className="loading">Loading…</div>;

  const { donor, transactions, engagements } = profile;

  // Merge engagements + touchpoints into a single sorted timeline
  const timelineItems = [
    ...engagements.map((e) => ({
      kind: 'engagement',
      date: e.ParticipateStartAt || e.EngagedAt || '',
      data: e,
    })),
    ...touchpoints.map((tp) => ({
      kind: 'touchpoint',
      date: tp.CreatedAt || '',
      data: tp,
    })),
  ].sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div>
      <Link to="/supporters" className="back-link">← Back to Supporters</Link>

      {/* ── Header ── */}
      <div className="profile-header">
        <div className="avatar">{initials(donor.FullName)}</div>
        <div style={{ flex: 1 }}>
          <div className="profile-name">{donor.FullName}</div>
          <div className="profile-meta">
            <span className={`badge badge-${donor.RelationshipType}`}>{donor.RelationshipType}</span>
            <span
              className={`badge badge-${donor.Tier}`}
              title={`${donor.Tier}: lifetime giving ${TIER_RANGES[donor.Tier] || ''}`}
            >
              {donor.Tier}
            </span>
            <StatusSelect donorId={id} computedStatus={donor.Status} initialOverride={donor.StatusOverride} />
          </div>
          <div className="profile-score">
            Priority score: <strong>{donor.PriorityScore}</strong>
            <span
              title={`Score = ${PRIORITY_FORMULA}`}
              style={{ marginLeft: 4, cursor: 'help', color: '#a0aec0', fontSize: 12 }}
            >
              ⓘ
            </span>
            {' · '}Last touch: {fmtDate(donor.LastActivityAt || donor.LastDonationAt)}
          </div>
        </div>
        <FollowUpToggle donorId={id} initial={donor.FollowUpStatus} />
      </div>

      {/* ── AI Brief ── */}
      <BriefPanel donorId={id} donorEmail={donor.Email} />

      {/* ── Basic Info + Giving History ── */}
      <div className="two-col">
        <div className="section">
          <h2>Contact Info</h2>
          <div className="info-grid">
            <div className="info-row">
              <label>Email</label>
              <span>{donor.Email || '—'}</span>
            </div>
            <div className="info-row">
              <label>Phone</label>
              <span>{donor.PhoneNumber || '—'}</span>
            </div>
            <div className="info-row">
              <label>Organization</label>
              <span>{donor.Organization || '—'}</span>
            </div>
            <div className="info-row">
              <label>Location</label>
              <span>{[donor.City, donor.State].filter(Boolean).join(', ') || '—'}</span>
            </div>
            <div className="info-row" style={{ gridColumn: '1/-1' }}>
              <label>Interests</label>
              <span>{donor.Interests || '—'}</span>
            </div>
            <div className="info-row">
              <label>Total Donated</label>
              <span style={{ fontWeight: 700, color: '#276749' }}>{fmtMoney(donor.TotalDonated)}</span>
            </div>
            <div className="info-row">
              <label>Active Since</label>
              <span>{fmtDate(donor.ActiveSinceDate)}</span>
            </div>
          </div>
        </div>

        <div className="section">
          <h2>Giving &amp; Transaction History</h2>
          {transactions.length === 0 ? (
            <p className="empty">No transactions recorded.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.TransactionID} style={{ cursor: 'default' }}>
                    <td>{fmtDate(t.TransactionDateTime)}</td>
                    <td>
                      {TX_ICON[t.TransactionType] || '•'} {t.TransactionType}
                      {t.TransactionItem && (
                        <div style={{ fontSize: 11, color: '#a0aec0' }}>{t.TransactionItem.split(' / ')[0]}</div>
                      )}
                    </td>
                    <td className="amount">{fmtMoney(t.TransactionAmount)}</td>
                    <td>
                      <span className={`badge badge-${t.PaymentStatus === 'SUCCESS' ? 'ACTIVE' : t.PaymentStatus === 'FAIL' ? 'LAPSED' : 'WARM'}`}>
                        {t.PaymentStatus}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── Activity & Notes Timeline ── */}
      <div className="section">
        <h2>Activity &amp; Notes</h2>

        <div className="note-form">
          <input
            type="text"
            className="note-input"
            placeholder="Log a call, email, or meeting note…"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLogNote()}
          />
          <button
            className="note-btn"
            onClick={handleLogNote}
            disabled={!noteText.trim() || noteSaving}
          >
            {noteSaving ? 'Saving…' : 'Log Note'}
          </button>
        </div>

        {timelineItems.length === 0 ? (
          <p className="empty">No activity recorded.</p>
        ) : (
          <ul className="timeline">
            {timelineItems.map((item) => {
              if (item.kind === 'touchpoint') {
                const tp = item.data;
                return (
                  <li key={`tp-${tp.TouchpointID}`} className="timeline-item">
                    <div className="tl-icon">📝</div>
                    <div className="tl-body">
                      <div className="tl-title">Note</div>
                      <div className="tl-note">{tp.Note}</div>
                      <div className="tl-meta">{fmtDate(tp.CreatedAt)}</div>
                    </div>
                  </li>
                );
              }
              const e = item.data;
              return (
                <li key={`eng-${e.DonorActivityID}`} className="timeline-item">
                  <div className="tl-icon">{ENG_ICON[e.EngagementType] || '•'}</div>
                  <div className="tl-body">
                    <div className="tl-title">
                      {e.EngagementType}
                      <span className={`badge badge-${e.EngagementStatus}`} style={{ marginLeft: 8 }}>
                        {e.EngagementStatus}
                      </span>
                    </div>
                    <div className="tl-meta">
                      {e.ActivityName && <span style={{ fontWeight: 500 }}>{e.ActivityName} · </span>}
                      {fmtDate(e.ParticipateStartAt || e.EngagedAt)}
                      {e.Notes ? ` · ${e.Notes}` : ''}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

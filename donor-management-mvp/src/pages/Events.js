import { useState, useEffect } from 'react';
import { api } from '../api/client';

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

export default function Events() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getEvents()
      .then((data) => { setEvents(data); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  if (error) return <div className="error">Failed to load events: {error}</div>;

  return (
    <div>
      <h1>Events</h1>
      <p className="subtitle">{events.length} events in system · sorted by date</p>

      <div className="section" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Event Name</th>
              <th>Date</th>
              <th>Attendees</th>
              <th>Revenue</th>
              <th>Ticket Price</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} className="empty">Loading…</td></tr>
            )}
            {!loading && events.length === 0 && (
              <tr><td colSpan={5} className="empty">No events recorded.</td></tr>
            )}
            {!loading && events.map((e) => (
              <tr key={e.ActivityID} style={{ cursor: 'default' }}>
                <td style={{ fontWeight: 600 }}>{e.ActivityName}</td>
                <td>{fmtDate(e.ActivityStartTime)}</td>
                <td>{e.attendee_count}</td>
                <td className="amount">{fmtMoney(e.total_revenue)}</td>
                <td>{e.ListPrice > 0 ? fmtMoney(e.ListPrice) : <span style={{ color: '#a0aec0' }}>Free</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

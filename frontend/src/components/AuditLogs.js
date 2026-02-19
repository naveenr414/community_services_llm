// AuditLogs.js - View audit logs
import React, { useState, useEffect } from 'react';
import { authenticatedFetch } from '../utils/api';
import { WellnessContext } from './AppStateContextProvider';
import { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import '../styles/pages/audit.css';

function AuditLogs() {
  const { user } = useContext(WellnessContext);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Filters
  const [username, setUsername] = useState('');
  const [action, setAction] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    
    try {
      // Build query params
      const params = new URLSearchParams();
      if (username) params.append('username', username);
      if (action) params.append('action', action);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('limit', limit);

      const response = await authenticatedFetch(`/api/audit/logs?${params.toString()}`);
      const data = await response.json();
      setLogs(data.logs);
    } catch (err) {
      setError(err.message || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = (e) => {
    e.preventDefault();
    fetchLogs();
  };

  const clearFilters = () => {
    setUsername('');
    setAction('');
    setStartDate('');
    setEndDate('');
    setLimit(100);
  };

  // Only admins can view
  if (user.role !== 'admin') {
    return <Navigate to="/" />;
  }

  return (
    <div className="audit-logs-container">
      <h1>Audit Logs</h1>
      
      <div className="filters-panel">
        <form onSubmit={handleFilter}>
          <div className="filter-row">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              type="text"
              placeholder="Action (e.g., login_success)"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            />
            <input
              type="date"
              placeholder="Start Date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <input
              type="date"
              placeholder="End Date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
            <input
              type="number"
              placeholder="Limit"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              min="10"
              max="1000"
            />
          </div>
          <div className="filter-buttons">
            <button type="submit" className="btn-primary">Apply Filters</button>
            <button type="button" onClick={clearFilters} className="btn-secondary">Clear</button>
            <button type="button" onClick={fetchLogs} className="btn-secondary">Refresh</button>
          </div>
        </form>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">Loading logs...</div>
      ) : (
        <div className="logs-table-container">
          <p className="log-count">Showing {logs.length} logs</p>
          <table className="logs-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Username</th>
                <th>Role</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Status</th>
                <th>IP Address</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className={log.status === 'failure' ? 'failure-row' : ''}>
                  <td>{new Date(log.timestamp).toLocaleString()}</td>
                  <td>{log.username}</td>
                  <td>{log.user_role}</td>
                  <td>{log.action}</td>
                  <td>
                    {log.resource_type}
                    {log.resource_id && `: ${log.resource_id}`}
                  </td>
                  <td>
                    <span className={`status-badge ${log.status}`}>
                      {log.status}
                    </span>
                  </td>
                  <td>{log.ip_address}</td>
                  <td>
                    {log.details && (
                      <details>
                        <summary>View</summary>
                        <pre>{JSON.stringify(log.details, null, 2)}</pre>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AuditLogs;
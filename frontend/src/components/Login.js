// Login.js - Updated with MFA support
import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { WellnessContext } from './AppStateContextProvider';
import Logo from '../icons/Logo.png';
import { Link } from 'react-router-dom';
import { API_URL } from '../config';
import '../styles/pages/login.css';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [showMfaInput, setShowMfaInput] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { setUser, setOrganization } = useContext(WellnessContext);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          username, 
          password,
          mfa_code: mfaCode || undefined
        }),
      });

      const data = await response.json();

      if (response.status === 403 && data.detail === "MFA code required") {
        setShowMfaInput(true);
        setError('');
        setIsLoading(false);
        return;
      }

      if (response.ok) {
        const { access_token, role, organization } = data;

        setUser({
          username: username,
          role: role,
          isAuthenticated: true,
          token: access_token, 
        });
        setOrganization(organization);

        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('userRole', role);
        localStorage.setItem('username', username);      
        localStorage.setItem('organization', organization);
        localStorage.setItem('loginTimestamp', Date.now().toString());

        navigate('/');
      } else {
        setError(data.detail || 'Login failed. Please try again.');
        setShowMfaInput(false);
        setMfaCode('');
      }
    } catch (err) {
      setError('Server error. Please try again later.');
      console.error('Login error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">
          <img src={Logo} alt="PeerCoPilot Logo" />
        </div>
        <h1>PeerCoPilot</h1>
        <h2>Login</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={showMfaInput}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={showMfaInput}
              required
            />
          </div>

          {showMfaInput && (
            <div className="form-group mfa-group">
              <label htmlFor="mfa-code">Authenticator Code</label>
              <input
                type="text"
                id="mfa-code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength="6"
                required
                autoFocus
                className="mfa-code-input"
              />
              <small>Enter the 6-digit code from your authenticator app</small>
            </div>
          )}
          
          <button 
            type="submit" 
            className="login-button"
            disabled={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>

          {showMfaInput && (
            <button 
              type="button"
              onClick={() => {
                setShowMfaInput(false);
                setMfaCode('');
              }}
              className="back-button"
            >
              ← Back
            </button>
          )}
        </form>
        <p className="register-link">
          Don't have an account? <Link to="/register">Register here</Link>
        </p>
      </div>
    </div>
  );
}

export default Login;
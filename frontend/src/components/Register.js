import React, { useState, useContext } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Logo from '../icons/Logo.png';
import { API_URL } from '../config';

import '../App.css';
import { WellnessContext } from './AppStateContextProvider';

function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [organization, setOrg] = useState('cspnj'); // default
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { setUser, setOrganization } = useContext(WellnessContext);


  /**
   * Handle submitting registration credentials to backend.
   * Sets user context and localStorage on success and redirects to home.
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, organization }),
      });

      const data = await response.json();

      if (response.ok) {
        const { access_token, role, organization } = data;
      
        // Set user context
        setUser({
          username: username,
          role: role,
          isAuthenticated: true,
          token: access_token,
        });
      
        // Set organization context
        setOrganization(organization);
      
        // Store in localStorage
        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('userRole', role);
        localStorage.setItem('username', username);
        localStorage.setItem('organization', organization);
      
        // Redirect straight to home
        navigate('/');
      } else {
        setError(data.detail || 'Registration failed. Please try again.');
      }      
    } catch (err) {
      console.error('Registration error:', err);
      setError('Server error. Please try again later.');
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
        <h2>Register</h2>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
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
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="organization">Organization</label>
            <select
                id="organization"
                value={organization}
                onChange={(e) => setOrg(e.target.value)}
                required
            >
                <option value="cspnj">CSPNJ</option>
                <option value="clhs">CLHS</option>
                <option value="georgia">Georgia</option>
            </select>
          </div>

          <button 
            type="submit" 
            className="login-button"
            disabled={isLoading}
          >
            {isLoading ? 'Registering...' : 'Register'}
          </button>
        </form>

        <p className="register-link">
          Already have an account? <Link to="/login">Login here</Link>
        </p>
      </div>
    </div>
  );
}

export default Register;

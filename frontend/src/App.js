// App.js - Main React application routes and layout with auto-logout
import React, { useContext, useCallback } from 'react';
import { BrowserRouter as Router, Route, Routes, useNavigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './components/Home';
import AuditLogs from './components/AuditLogs';
import Login from './components/Login';
import {WellnessGoals} from './components/GenericChat';
import {WellnessContextProvider, WellnessContext} from './components/AppStateContextProvider.js';
import ProfileManager from './components/ProfileManager';
import OutreachCalendar from './components/OutreachCalendar';
import Register from './components/Register';
import { useInactivityTimeout } from './utils/useInactivityTimeout';
import './styles/variable.css';
import './styles/base/base.css';
import './styles/layouts/content-layout.css';
import './styles/components/common.css';
import './styles/components/navbar.css';

// Inner component that has access to Router context
function AppContent() {
  const navigate = useNavigate();
  const { user, setUser, setOrganization, setConversation } = useContext(WellnessContext);

  // Auto-logout handler
  const handleAutoLogout = useCallback(() => {
    console.log('[Auto-Logout] Session expired due to inactivity');
    
    // Clear user state
    setUser({
      username: '',
      role: '',
      isAuthenticated: false,
      token: null,
    });
    setOrganization('');
    setConversation([]);
    
    // Clear localStorage
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('username');
    localStorage.removeItem('organization');
    localStorage.removeItem('loginTimestamp');
    
    // Redirect to login with message
    alert('Your session has expired due to inactivity. Please log in again.');
    navigate('/login');
  }, [navigate, setUser, setOrganization, setConversation]);

  // Only activate inactivity timer if user is authenticated
  useInactivityTimeout(
    user?.isAuthenticated ? handleAutoLogout : () => {}, 
    30 // 30 minutes of inactivity
  );

  return (
    <div className="App">
      <Navbar />
      <div className="content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/wellness-goals" element={<WellnessGoals />} />
          <Route path="/profile-manager" element={<ProfileManager />} />
          <Route path="/outreach-calendar" element={<OutreachCalendar />} />
          <Route path="/audit-logs" element={<AuditLogs />} />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <WellnessContextProvider>
      <Router>
        <AppContent />
      </Router>
    </WellnessContextProvider>
  );
}

export default App;
import React, { useContext } from 'react';
import { WellnessContext } from './AppStateContextProvider';
import { useNavigate } from 'react-router-dom';

function Logout() {
  const { setUser, setOrganization, setConversation } = useContext(WellnessContext);
  const navigate = useNavigate();

  const handleLogout = (reason = 'manual') => {
    console.log(`[Logout] User logged out: ${reason}`);
    
    setUser({
      username: '',
      role: '',
      isAuthenticated: false,
      token: null,
    });
    setOrganization('');
    setConversation([]);
    
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('username');
    localStorage.removeItem('organization');
    localStorage.removeItem('loginTimestamp');
    
    navigate('/login');
  };

  return (
    <button onClick={() => handleLogout('manual')} className="logout-button">
      Logout
    </button>
  );
}

export { Logout };
export default Logout;

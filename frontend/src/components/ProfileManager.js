import React, { useEffect, useState, useContext, useCallback, useMemo } from 'react';
import Sidebar from './Sidebar';
import AddIcon from '../icons/Add.png';
import SidebarInformation from './SidebarInformation';
import { useCheckIns } from '../hooks/useCheckIns';
import { WellnessContext } from './AppStateContextProvider';
import { apiPost, apiGet, authenticatedFetch } from '../utils/api';

// Initial form state
const INITIAL_FORM_STATE = {
  patientName: '',
  lastSession: '',
  nextCheckIn: '',
  followUpMessage: '',
  location: '',
};

const ProfileManager = () => {
  const { user } = useContext(WellnessContext);
  const [allNames, setAllNames] = useState([{}]);

  const [serviceUsers, setServiceUsers] = useState([]);
  const [hasSidebar, setSidebar] = useState(false);
  const [search, setSearch] = useState('');
  // Form state
  const [currentPatient, setCurrentPatient] = useState({});
  const [isEditable, setIsEditable] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [lastSession, setLastSession] = useState('');
  const [nextCheckIn, setNextCheckIn] = useState('');
  const [followUpMessage, setFollowUpMessage] = useState('');
  const {
    checkIns,
    isLoading: checkInsLoading,
    error: checkInsError,
    fetchCheckIns,
    saveAllCheckIns,
    updatePatientLastSession
  } = useCheckIns();

  useEffect(() => {
    if (currentPatient?.service_user_id && !isEditable) {
      fetchCheckIns(currentPatient.service_user_id);
    }
  }, [currentPatient?.service_user_id, isEditable, fetchCheckIns]);
  

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form state
  const [formData, setFormData] = useState(INITIAL_FORM_STATE);

  // Fetch service users
  const fetchServiceUsers = useCallback(async () => {
    if (!user?.username) return;

    setIsLoading(true);
    setError(null);
    
    try {
      const data = await apiGet(`/service_user_list/`);
      setServiceUsers(data || []);
      console.log('[ProfileManager] Loaded', data?.length || 0, 'profiles');
    } catch (err) {
      console.error('[ProfileManager] Error fetching users:', err);
      setError(err.message);
      setServiceUsers([]);
    } finally {
      setIsLoading(false);
    }
  }, [user?.username]);

  useEffect(() => {
    fetchServiceUsers();
  }, [fetchServiceUsers]);

  // Filter service users based on search
  const filteredServiceUsers = useMemo(() => {
    if (!search.trim()) return serviceUsers;

    const searchLower = search.toLowerCase();
    return serviceUsers.filter((user) => {
      const name = user.service_user_name?.toLowerCase() || '';
      const location = user.location?.toLowerCase() || '';
      return name.includes(searchLower) || location.includes(searchLower);
    });
  }, [serviceUsers, search]);

  // Handlers
  const handleSearchChange = useCallback((e) => {
    setSearch(e.target.value);
  }, []);

  const handleFormChange = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  }, []);

  const openSidebar = useCallback((patient, editable) => {
    setCurrentPatient(patient);
    setIsEditable(editable);

    if (editable) {
      // New patient - empty form
      setFormData(INITIAL_FORM_STATE);
    } else {
      // Existing patient - populate form
      setFormData({
        patientName: patient.service_user_name || '',
        lastSession: patient.last_session || '',
        nextCheckIn: patient.check_in || '',
        followUpMessage: patient.follow_up_message || '',
        location: patient.location || '',
      });
    }

    setSidebar(true);
  }, []);

  const closeSidebar = useCallback(() => {
    setSidebar(false);
    setCurrentPatient(null);
    setIsEditable(false);
    setFormData(INITIAL_FORM_STATE);
  }, []);

  const handleSubmit = useCallback(async () => {
    console.log('[ProfileManager] Submitting:', formData);
    setIsSubmitting(true);

    try {
      await apiPost('/new_service_user/', {
        ...formData,
        username: user.username,
      });

      console.log('[ProfileManager] Successfully created service user');

      // Refresh list and close sidebar
      await fetchServiceUsers();
      closeSidebar();
    } catch (err) {
      console.error('[ProfileManager] Submit error:', err);
      alert(`Failed to create service user: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [formData, user.username, fetchServiceUsers, closeSidebar]);

  const getAllNames = async () => {
    setIsLoading(true);
    try {
      // TODO: This endpoint reference looks like a typo (`$/service_user_list/`).
      // Replace with `/service_user_list/` or use apiGet if intended.
      const response = await authenticatedFetch(`/service_user_list/`);
      const res = await response.json()
      setAllNames(res);
      console.log('[Load] Got', res.length, 'profiles');
    } catch (error) {
      console.error('[Load] Error:', error);
      setAllNames([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    getAllNames();
  }, [user.username]);

  const handleUpdatePatient = async (updatedData) => {
    setIsSubmitting(true);
    try {
      if (updatedData.last_session !== undefined) {
        await updatePatientLastSession(currentPatient.service_user_id, updatedData.last_session);
        
        setCurrentPatient(prev => ({
          ...prev,
          last_session: updatedData.last_session
        }));
        setLastSession(updatedData.last_session);
      }

      await fetchServiceUsers();
      alert('Changes saved successfully!');
    } catch (error) {
      alert(`Failed to update: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Replace handleSaveAllCheckIns with:
  const handleSaveAllCheckIns = async (allEdits) => {
    setIsSubmitting(true);
    try {
      await saveAllCheckIns(allEdits, currentPatient.service_user_id);
      alert('All changes saved successfully!');
    } catch (error) {
      alert(`Failed to update check-ins: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };
  return (
    <div className="container">
      <div className={`main-content ${hasSidebar ? 'shifted' : ''}`}>
        <div className="search-container">
          <input
            type="text"
            placeholder="Search by name or location..."
            className="profile-search-box"
            value={search}
            onChange={handleSearchChange}
            aria-label="Search service users"
          />
          <button 
            className="add" 
            onClick={() => openSidebar({}, true)}
            aria-label="Add new service user"
          >
            <img src={AddIcon} alt="" />
            Add
          </button>
        </div>

        <div className="table-wrapper">
          {isLoading ? (
            <div className="loading-message">Loading service users...</div>
          ) : error ? (
            <div className="error-message">
              <p>Error: {error}</p>
              <button onClick={fetchServiceUsers}>Retry</button>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Last Session</th>
                  <th>Next Check-in</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredServiceUsers.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="empty-message">
                      {search
                        ? `No results found for "${search}"`
                        : 'No service users found'}
                    </td>
                  </tr>
                ) : (
                  filteredServiceUsers.map((user) => (
                    <tr
                      key={user.service_user_id || user.id}
                      onClick={() => openSidebar(user, false)}
                      className="clickable-row"
                    >
                      <td>{user.service_user_name || '—'}</td>
                      <td>{user.location || '—'}</td>
                      <td>{user.last_session || '—'}</td>
                      <td>{user.check_in || '—'}</td>
                      <td>
                        <div className={user.status}>
                          {user.status}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
      
      <Sidebar 
      isOpen={hasSidebar}
      content={
        hasSidebar ? (
          <SidebarInformation
            checkIns={checkIns}
            patient={currentPatient}
            isEditable={isEditable}
            isSubmitting={isSubmitting}
            onSubmit={handleSubmit}
            formData={formData}
            onFormChange={handleFormChange}
            onUpdatePatient={handleUpdatePatient}
            onSaveAllCheckIns={handleSaveAllCheckIns}
            onClose={() => setSidebar(false)}
            patientName={patientName}
            setPatientName={setPatientName}
            lastSession={lastSession}
            setLastSession={setLastSession}
          />
        ) : null
      }
    />
    </div>
  );
};

export default ProfileManager;
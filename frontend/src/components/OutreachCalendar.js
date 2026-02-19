// OutreachCalendar.js - Calendar view showing scheduled check-ins
import React, { useEffect, useState, useContext, useCallback, useMemo } from 'react';
import Sidebar from './Sidebar';
import SidebarInformation from './SidebarInformation';
import { WellnessContext } from './AppStateContextProvider';
import { useCheckIns } from '../hooks/useCheckIns';
import { authenticatedFetch, apiGet } from '../utils/api';
import '../styles/pages/calendar.css';

/**
 * parseCheckInDate - accepts several date formats and returns a Date or null
 * @param {string} checkInStr
 * @returns {Date|null}
 */

// Constants
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const COLORS = [
  '#FFBC2A', '#9F69AF', '#F5511F', '#79C981', '#34A2ED',
  '#5AD1D3', '#E57C7E', '#FF61B5', '#FFD83E', '#FFAE95'
];

const DAYS_OF_WEEK = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// Utility functions
const parseCheckInDate = (checkInStr) => {
  if (!checkInStr) {
    console.warn('Invalid or missing check-in date:', checkInStr);
    return null;
  }
  const parts = checkInStr.split('-').map(Number);
  
  if (parts[0] > 31) {
    const [year, month, day] = parts;
    return new Date(year, month - 1, day);
  } else {
    const [month, day, year] = parts;
    return new Date(year, month - 1, day);
  }
};

const getDateKey = (date) => {
  const year = date.getFullYear();
  const month = date.getMonth();
  const day = date.getDate();
  return `${year}-${month}-${day}`;
};

const OutreachCalendar = () => {
  const { user } = useContext(WellnessContext);
  
  const [search, setSearch] = useState('');
  const [allOutreach, setAllOutreach] = useState([]);
  const [currentPatient, setCurrentPatient] = useState(null);
  const [hasSidebar, setSidebar] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const {
    checkIns,
    isLoading: checkInsLoading,
    error: checkInsError,
    fetchCheckIns,
    saveAllCheckIns,
    updatePatientLastSession
  } = useCheckIns();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [lastSession, setLastSession] = useState('');

  // Fetch check-ins when patient changes
  useEffect(() => {
    if (currentPatient?.service_user_id) {
      fetchCheckIns(currentPatient.service_user_id);
    }
  }, [currentPatient?.service_user_id, fetchCheckIns]);

  // Fetch outreach data
  const fetchOutreach = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const data = await apiGet(`/service_user_list/`);
      console.log('Outreach data:', data);
      setAllOutreach(data);
    } catch (err) {
      console.error('Error fetching outreach:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOutreach();
  }, [fetchOutreach]);

  // Group outreach by actual date
  const outreachByDate = useMemo(() => {
    const grouped = {};
    const patientColors = {};
    let colorIndex = 0;

    allOutreach.forEach((outreach) => {
      const date = parseCheckInDate(outreach.check_in);
      if (!date || isNaN(date.getTime())) {
        console.warn('Skipping outreach with invalid date:', outreach);
        return;
      }
      
      const dateKey = getDateKey(date);

      if (!grouped[dateKey]) {
        grouped[dateKey] = {
          date: date,
          outreach: []
        };
      }

      if (!patientColors[outreach.service_user_name]) {
        patientColors[outreach.service_user_name] = COLORS[colorIndex % COLORS.length];
        colorIndex++;
      }

      grouped[dateKey].outreach.push({
        ...outreach,
        color: patientColors[outreach.service_user_name]
      });
    });

    return grouped;
  }, [allOutreach]);

  // Filter and render dates
  const dateComponents = useMemo(() => {
    const sortedDates = Object.keys(outreachByDate).sort((a, b) => {
      return outreachByDate[a].date.getTime() - outreachByDate[b].date.getTime();
    });
    
    const searchLower = search.toLowerCase();

    return sortedDates.map((dateKey) => {
      const { date, outreach } = outreachByDate[dateKey];
      const month = MONTHS[date.getMonth()];
      const day = date.getDate();
      const dayOfWeek = DAYS_OF_WEEK[date.getDay()];

      const filteredOutreach = outreach.filter((item) => {
        const name = (item.name || item.service_user_name || '').toLowerCase();
        return name.includes(searchLower);
      });

      if (filteredOutreach.length === 0 && search) {
        return null;
      }

      const year = date.getFullYear();

      return (
        <div key={dateKey} className="day">
          <div className="date black">{day}</div>
          <div className="info">
            {dayOfWeek}, {month} {day}, {year}
          </div>
          <ul>
            {filteredOutreach.map((item) => (
              <li key={item.service_user_id} onClick={() => handlePatientClick(item)}>
                <span className="dot" style={{ background: item.color }} />
                Follow-up Wellness Check-in w/ {item.name || item.service_user_name}
              </li>
            ))}
          </ul>
        </div>
      );
    }).filter(Boolean);
  }, [outreachByDate, search]);

  // Handlers
  const handleSearchChange = useCallback((e) => {
    setSearch(e.target.value);
  }, []);

  const handlePatientClick = useCallback((patient) => {
    setCurrentPatient(patient); // Pass the full patient object
    setSidebar(true);
  }, []);

  const handleCloseSidebar = useCallback(() => {
    setSidebar(false);
    setCurrentPatient(null);
  }, []);

  const handleUpdatePatient = async (updatedData) => {
    setIsSubmitting(true);
    try {
      if (updatedData.last_session !== undefined) {
        await updatePatientLastSession(currentPatient.service_user_id, updatedData.last_session);
        setCurrentPatient(prev => ({
          ...prev,
          last_session: updatedData.last_session
        }));
      }
      await fetchOutreach();
      alert('Changes saved successfully!');
    } catch (error) {
      alert(`Failed to update: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

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
  const currentMonth = MONTHS[new Date().getMonth()];
  const currentYear = new Date().getFullYear();

  return (
    <div className="container">
      <div className={`main-content ${hasSidebar ? 'shifted' : ''}`}>
        <div className="header">
          <h2 style={{ paddingRight: '20px' }}>
            {currentMonth} {currentYear}
          </h2>
          <input
            type="text"
            placeholder="Search by patient name..."
            className="search-box"
            value={search}
            onChange={handleSearchChange}
            aria-label="Search patients"
          />
        </div>

        <div className="table-wrapper">
          <div className="schedule">
            {isLoading && (
              <div className="loading-message">Loading outreach data...</div>
            )}
            
            {error && (
              <div className="error-message">
                Error: {error}
                <button onClick={fetchOutreach}>Retry</button>
              </div>
            )}

            {!isLoading && !error && dateComponents.length === 0 && (
              <div className="empty-message">
                {search
                  ? `No results found for "${search}"`
                  : 'No outreach scheduled'}
              </div>
            )}

            {!isLoading && !error && dateComponents}
          </div>
        </div>
      </div>

      <Sidebar
        isOpen={hasSidebar}
        content={
          hasSidebar && currentPatient ? (
            <SidebarInformation
              checkIns={checkIns}
              patient={currentPatient}
              isEditable={false}
              isSubmitting={isSubmitting}
              onSubmit={() => {}}
              onUpdatePatient={handleUpdatePatient}
              onSaveAllCheckIns={handleSaveAllCheckIns}
              onClose={handleCloseSidebar}
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

export default OutreachCalendar;
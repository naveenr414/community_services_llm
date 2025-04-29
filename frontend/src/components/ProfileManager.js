import React, { useEffect, useState, useContext } from 'react';
import Sidebar from './Sidebar';
import '../styles/feature.css';
import AddIcon from '../icons/Add.png';
import SidebarInformation from './SidebarInformation';
import { WellnessContext } from './AppStateContextProvider';

const ProfileManager = () => {
  const [allNames, setAllNames] = useState([{}]);
  const [hasSidebar, setSidebar] = useState(false);
  const [search, setSearch] = useState('');
  const { user } = useContext(WellnessContext);

  // Form state
  const [currentPatient, setCurrentPatient] = useState({});
  const [isEditable, setIsEditable] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [lastSession, setLastSession] = useState('');
  const [nextCheckIn, setNextCheckIn] = useState('');
  const [followUpMessage, setFollowUpMessage] = useState('');

  const handleSearchChange = (e) => {
    setSearch(e.target.value);
  };

  const handleSubmit = async () => {
    // Process form data
    console.log();
    
    try {
      const response = await fetch("http://localhost:8000/new_checkin/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          patientName, lastSession, nextCheckIn, followUpMessage }),
      });
  
      const result = await response.json();
      console.log("Response:", result);
    } catch (error) {
      console.error("Error:", error);
    }
  

    // Here you would typically save the data to your backend
    // savePatientData({ patientName, lastSession, nextCheckIn, followUpMessage });
    
    // Close sidebar after submission
    setSidebar(false);
  };

  const openSidebar = (patient, editable) => {
    // Set current patient data
    setCurrentPatient(patient);
    setIsEditable(editable);
    
    // For new patients (editable=true), initialize with empty values
    // For existing patients (editable=false), initialize with their current values
    if (editable) {
      setPatientName('');
      setLastSession('');
      setNextCheckIn('');
      setFollowUpMessage('');
    } else {
      setPatientName(patient.service_user_name || '');
      setLastSession(patient.last_session || '');
      setNextCheckIn(patient.check_in || '');
      setFollowUpMessage(patient.follow_up_message || '');
    }
    
    // Open the sidebar
    setSidebar(true);
  };

  const getAllNames = async () => {
    const response = await fetch(`http://${window.location.hostname}:8000/service_user_list/?name=${user.username}`);
    response.json().then((res) => setAllNames(res));
  };

  useEffect(() => {
    getAllNames();
  }, []);

  return (
    <div className="container">
      <div className={`main-content ${hasSidebar ? 'shifted' : ''}`}>
        <div className="search-container"> 
          <input 
            type="text" 
            placeholder="Search Name, Date, etc." 
            className="profile-search-box" 
            value={search}
            onChange={handleSearchChange}
          />
          <button className="add" onClick={() => openSidebar({}, true)}>
            <img src={AddIcon} alt="Add Icon" /> Add
          </button>
        </div>
        
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Location</th>
              <th>Other Info 1</th>
              <th>Other Info 2</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {allNames.map((d, index) => (
              (d.location !== undefined && d.location.toLowerCase().includes(search.toLowerCase())) || 
              (d.service_user_name !== undefined && d.service_user_name.toLowerCase().includes(search.toLowerCase()))
            ) ? (
              <tr key={index} onClick={() => openSidebar(d, false)}>
                <td>{d.service_user_name}</td>
                <td>{d.location}</td>
                <td>Other Info 1</td>
                <td>Other Info 2</td>
                <td><div className={d.status}>{d.status}</div></td>
              </tr>
            ) : null)}      
          </tbody>
        </table>
      </div>
      
      <Sidebar 
      isOpen={hasSidebar}
      content={
        hasSidebar ? (
          <SidebarInformation
            patient={currentPatient}
            isEditable={isEditable}
            onSubmit={handleSubmit}
            onClose={() => setSidebar(false)}
            patientName={patientName}
            setPatientName={setPatientName}
            lastSession={lastSession}
            setLastSession={setLastSession}
            nextCheckIn={nextCheckIn}
            setNextCheckIn={setNextCheckIn}
            followUpMessage={followUpMessage}
            setFollowUpMessage={setFollowUpMessage}
          />
        ) : null
      }
    />

    </div>
  );
};

export default ProfileManager;
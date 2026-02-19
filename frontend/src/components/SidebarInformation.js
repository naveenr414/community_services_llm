// SidebarInformation.js - Panel for viewing/editing a service user's details and upcoming check-ins
import CalendarIcon from '../icons/Calendar.png';
import ClockIcon from '../icons/Clock.png';
import EditIcon from '../icons/Pencil.png';
import ChatIcon from '../icons/Chat.png';
import ProfileIcon from '../icons/Profile.png';
import React, { useEffect, useState } from 'react';

/**
 * SidebarInformation component
 * @param {object} props
 * @param {object} props.patient - Service user record
 * @param {Array} props.checkIns - List of upcoming check-ins
 * @param {boolean} props.isEditable - Whether the form is editable
 * @param {object} props.formData - Controlled form data
 * @param {function} props.onFormChange - Callback(field, value)
 * @param {function} props.onSubmit - Callback to create/update patient
 * @param {function} props.onSaveAllCheckIns - Callback to save check-in edits
 */

const SidebarInformation = ({ 
  patient = {}, 
  checkIns = [],
  isEditable = false,
  isSubmitting = false, 
  formData = {},
  onFormChange,
  onSubmit, 
  onUpdatePatient,
  onSaveAllCheckIns,
  onClose,
}) => {
  // Manage state internally
  const [lastSession, setLastSession] = useState('');
  const [pendingCheckInEdits, setPendingCheckInEdits] = useState({});

  // Helper to format date for INPUT (YYYY-MM-DD)
  const formatDateForInput = (dateString) => {
    if (!dateString) return '';
    
    // If already in YYYY-MM-DD format, return as-is
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
      return dateString;
    }
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';
    
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  // Initialize when patient changes
  useEffect(() => {
    if (patient?.last_session) {
      setLastSession(formatDateForInput(patient.last_session));
    } else {
      setLastSession('');
    }
    setPendingCheckInEdits({}); // Reset edits when patient changes
  }, [patient?.service_user_id]);

  const handleCheckInEdit = (checkInId, updatedData) => {
    setPendingCheckInEdits(prev => ({
      ...prev,
      [checkInId]: updatedData
    }));
  };

  const handleSaveAll = async () => {
  if (isEditable) {
    // New patient - create
    await onSubmit();
  } else {
    // Existing patient - only save check-ins
    if (onSaveAllCheckIns && Object.keys(pendingCheckInEdits).length > 0) {
      await onSaveAllCheckIns(pendingCheckInEdits);
    } else {
      alert('No changes to save');
    }
  }
};

  const globalClassName = isEditable ? "input-section" : "info-section";

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      onSubmit();
    }}>
      <div className="card">
        <div className="card-header">
          <h2>{isEditable ? "Check-In Information" : patient.service_user_name}</h2>
          <button className="close-btn" type="button" onClick={onClose}>×</button>
        </div>
        
        {isEditable && (
          <div className="input-section">
            <div className="form-group">
              <label className="section-label" htmlFor="patientName">
                <img src={ProfileIcon} alt="Profile Icon" className="icon" />
                Patient Name
              </label>
              <input 
                type="text" 
                id="patientName" 
                placeholder="Enter service user name"
                value={formData.patientName || ''}
                onChange={(e) => onFormChange('patientName', e.target.value)}
              />
            </div>
          </div>
        )}
        
        {isEditable && (
          <div className="input-section">
            <div className="form-group">
              <label className="section-label" htmlFor="location">
                <img src={ProfileIcon} alt="Location Icon" className="icon" />
                Location
              </label>
              <input 
                type="text" 
                id="location" 
                placeholder="Enter location (e.g., city, clinic name)"
                value={formData.location || ''}
                onChange={(e) => onFormChange('location', e.target.value)}
              />
            </div>
          </div>
        )}

        {!isEditable && patient.location && (
          <div className="info-section">
            <div className="section-label">
              <img src={ProfileIcon} alt="Location Icon" className="icon" />
              Location
            </div>
            <div className="section-content">{patient.location}</div>
          </div>
        )}

        <div className={globalClassName}>
          <div className="section-label">
            <img src={CalendarIcon} alt="Calendar Icon" className="icon" />
            Last session
          </div>
          {/* <input 
            type="date" 
            id="lastSession"
            value={lastSession}
            onChange={(e) => setLastSession(e.target.value)}
          /> */}
          <div className="section-content">{patient.last_session || '—'}</div>
        </div>
        
        {checkIns.length > 0 && (
          <div>
            <div className="section-label" style={{marginLeft: "20px", marginTop: "16px"}}>
              <img src={ClockIcon} alt="Clock Icon" className="icon" />
              Upcoming Check-ins
            </div>
            {checkIns.map((checkIn, index) => (
              <CheckInItem 
                key={checkIn.id || index} 
                checkIn={checkIn}
                onEdit={handleCheckInEdit}
              />
            ))}
          </div>
        )}
        
        <div className="save-button-container">
          <button 
            onClick={handleSaveAll} 
            disabled={isSubmitting}
            type="button" 
            className="save-button"
          >
            {isSubmitting ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </form>
  );
};

/**
 * CheckInItem - small editable block for a single scheduled check-in
 * @param {object} props.checkIn - check-in record with fields `check_in` and `follow_up_message`
 * @param {function} props.onEdit - handler(checkInId, updatedData)
 */
const CheckInItem = ({checkIn, onEdit}) => {
  const formatDateForInput = (dateString) => {
    if (!dateString) return '';
    
    // If already in YYYY-MM-DD, return as-is
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
      return dateString;
    }
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';
    
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  const [editedCheckIn, setEditedCheckIn] = useState({
    checkInDate: formatDateForInput(checkIn.check_in),
    message: checkIn.follow_up_message || ''
  });

  const handleChange = (field, value) => {
    const updated = {
      ...editedCheckIn,
      [field]: value
    };
    setEditedCheckIn(updated);
    
    // Notify parent component
    onEdit(checkIn.id, {
      check_in: field === 'checkInDate' ? value : editedCheckIn.checkInDate,
      follow_up_message: field === 'message' ? value : editedCheckIn.message
    });
  };

  return (
    <div className="check-in-item" style={{
      margin: "10px 20px",
      padding: "10px",
      border: "1px solid #e0e0e0",
      borderRadius: "8px",
      backgroundColor: "#f9f9f9"
    }}>
      <div style={{ fontWeight: "bold", marginBottom: "5px", display: "flex", alignItems: "center" }}>
        <img src={ClockIcon} alt="Clock Icon" className="icon" style={{width: "16px", marginRight: "5px"}} />
        <input 
          type="date"
          value={editedCheckIn.checkInDate}
          onChange={(e) => handleChange('checkInDate', e.target.value)}
          style={{ border: "1px solid #ccc", padding: "5px", borderRadius: "4px" }}
        />
      </div>
      
      <div style={{marginTop: "10px"}}>
        <div style={{display: "flex", alignItems: "center", marginBottom: "5px"}}>
          <img src={ChatIcon} alt="Chat Icon" className="icon" style={{width: "16px", marginRight: "5px"}} />
          <span style={{fontSize: "14px", color: "#666"}}>Follow-up message</span>
        </div>
        <textarea
          value={editedCheckIn.message}
          onChange={(e) => handleChange('message', e.target.value)}
          style={{ 
            width: "100%", 
            minHeight: "60px",
            border: "1px solid #ccc", 
            padding: "8px", 
            borderRadius: "4px",
            resize: "vertical",
            fontFamily: "inherit",
            fontSize: "14px",
            boxSizing: "border-box"
          }}
        />
      </div>
    </div>
  );
};

export default SidebarInformation;
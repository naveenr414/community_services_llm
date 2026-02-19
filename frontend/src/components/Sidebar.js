// Sidebar.js - Simple slide-over container used for detail panels
import React from 'react';
import '../styles/sidebar.css';

const Sidebar = ({isOpen, content}) => {
  return (
    <div className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      {isOpen ? content : null}
    </div>
  );
};

export default Sidebar;
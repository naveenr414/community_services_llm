import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../App.css';
import HomeIcon from '../icons/Home.png';
import WellnessGoalsIcon from '../icons/WellnessGoalsAssistant.png';
import ResourceDatabaseIcon from '../icons/ResourceRecommendation.png';
import BenefitEligibilityIcon from '../icons/BenefitEligibilityChecker.png';

function Navbar() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = () => {
    setMenuOpen(!menuOpen);
  };

  return (
    <nav className="navbar">
      <h1 className="navbar-title">EPINET Co-Pilot</h1>
      <div className="hamburger" onClick={toggleMenu}>
        &#9776; {/* Hamburger icon */}
      </div>
      <div className={`navbar-links ${menuOpen ? 'active' : ''}`}>
        <Link
          to="/"
          className={`navbar-button ${location.pathname === '/' ? 'active' : ''}`}
        >
          <img src={HomeIcon} alt="Home Icon" className="navbar-icon" />
          Home
        </Link>
        <div className="navbar-spacer"></div>
        <div className="navbar-label">Tool</div>
        <Link
          to="/wellness-goals"
          className={`navbar-button ${
            location.pathname === '/wellness-goals' ? 'active' : ''
          }`}
        >
          <img src={WellnessGoalsIcon} alt="Wellness Goals Icon" className="navbar-icon" />
          Wellness Goals Assistant
        </Link>
        <Link
          to="/resource-database"
          className={`navbar-button ${
            location.pathname === '/resource-database' ? 'active' : ''
          }`}
        >
          <img
            src={ResourceDatabaseIcon}
            alt="Resource Database Icon"
            className="navbar-icon"
          />
          Resource Database
        </Link>
        <Link
          to="/benefit-eligibility"
          className={`navbar-button ${
            location.pathname === '/benefit-eligibility' ? 'active' : ''
          }`}
        >
          <img
            src={BenefitEligibilityIcon}
            alt="Benefit Eligibility Icon"
            className="navbar-icon"
          />
          Benefit Eligibility
        </Link>
      </div>
    </nav>
  );
}

export default Navbar;

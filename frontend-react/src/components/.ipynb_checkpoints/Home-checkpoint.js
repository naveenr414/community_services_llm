import React from 'react';
import { Link } from 'react-router-dom';
import '../App.css';
import Logo from '../icons/Logo.png';

function Home() {
  return (
    <div className="home-container">
      <div className="home-logo">
        <img src={Logo} alt="Logo" />
      </div>
      <h1 className="home-heading">Welcome!</h1>
      <p className="home-subheading">All Tools at One Glance:</p>
      <div className="tiles-container">
        <Link to="/wellness-goals" className="tile">
          <span>Tool 1</span>
          <h2>Wellness Goals Assistant</h2>
        </Link>
        <Link to="/resource-database" className="tile">
          <span>Tool 2</span>
          <h2>Resource Database</h2>
        </Link>
        <Link to="/benefit-eligibility" className="tile">
          <span>Tool 3</span>
          <h2>Benefit Eligibility</h2>
        </Link>
      </div>
    </div>
  );
}

export default Home;

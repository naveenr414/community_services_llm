import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './components/Home';
import Login from './components/Login';
import {WellnessGoals} from './components/GenericChat';
import {WellnessContextProvider} from './components/AppStateContextProvider.js';
import ProfileManager from './components/ProfileManager';
import OutreachCalendar from './components/OutreachCalendar';
import './App.css';

function App() {
  return (
    <WellnessContextProvider>
      <Router>
        <div className="App">
          <Navbar />
          <div className="content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/wellness-goals" element={<WellnessGoals />} />
              <Route path="/profile-manager" element={<ProfileManager />} />
              <Route path="/outreach-calendar" element={<OutreachCalendar />} />
            </Routes>
          </div>
        </div>
      </Router>
    </WellnessContextProvider>
  );
}

export default App;

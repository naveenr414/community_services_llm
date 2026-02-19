// AppStateContextProvider.js - Central React context for sharing app state
// Provides values used by chat and profile components (input text, conversation, user, etc.)
import React, { createContext, useState } from 'react';

/**
 * Create a context provider wrapper for the given Context.
 * Exposes a stable object of state and setter functions used across components.
 *
 * Provided values include:
 * - inputText, setInputText
 * - conversation, setConversation
 * - chatConvo, setChatConvo
 * - user, setUser
 */
const createContextProvider = (Context) => ({ children }) => {
  const [inputText, setInputText] = useState('');
  const [modelSelect, setModel] = useState('copilot');
  const [newMessage, setNewMessage] = useState('');
  const [conversation, setConversation] = useState([]);
  const [submitted] = useState(false);
  const [chatConvo, setChatConvo] = useState([]);
  const [inputLocationText, setInputLocationText] = useState('');
  const [organization, setOrganization] = useState(() => {
    // Try to get the saved organization, fallback to 'cspnj' if not found
    return localStorage.getItem('organization') || 'cspnj';
  });  
  // Initialize user state from localStorage if available
  const [user, setUser] = useState(() => {
    // This runs only once during initial render
    const storedToken = localStorage.getItem('accessToken');
    const storedRole = localStorage.getItem('userRole');
    const storedUsername = localStorage.getItem('username');

    if (storedToken && storedRole && storedUsername) {
      return {
        isAuthenticated: true,
        username: storedUsername,
        role: storedRole,
        token: storedToken,
      };
    }

    return {
      username: '', 
      isAuthenticated: false,
      token: null,
      role: null,
    };
  });

  const resetContext = () => {
    setInputText('');
    setNewMessage('');
    setConversation([]);
    setChatConvo([]);
    setInputLocationText('');
  };

  const contextValue = {
    inputText,
    setInputText,
    modelSelect,
    setModel,
    inputLocationText,
    setInputLocationText,
    newMessage,
    setNewMessage,
    conversation,
    setConversation,
    submitted,
    chatConvo,
    setChatConvo,
    organization,
    setOrganization,
    user,
    setUser,
    resetContext,
  };

  return <Context.Provider value={contextValue}>{children}</Context.Provider>;
};

export const WellnessContext = createContext();
export const WellnessContextProvider = createContextProvider(WellnessContext);
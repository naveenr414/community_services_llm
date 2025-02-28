import React, { createContext, useState } from 'react';

const createContextProvider = (Context) => ({ children }) => {
  const [inputText, setInputText] = useState('');
  const [modelSelect, setModel] = useState('copilot');
  const [newMessage, setNewMessage] = useState('');
  const [conversation, setConversation] = useState([]);
  const [submitted] = useState(false);
  const [chatConvo, setChatConvo] = useState([]);
  const [inputLocationText, setInputLocationText] = useState('');

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
    resetContext,
  };

  return <Context.Provider value={contextValue}>{children}</Context.Provider>;
};

export const WellnessContext = createContext();
export const BenefitContext = createContext();
export const ResourceContext = createContext();

export const WellnessContextProvider = createContextProvider(WellnessContext);
export const BenefitContextProvider = createContextProvider(BenefitContext);
export const ResourceContextProvider = createContextProvider(ResourceContext);

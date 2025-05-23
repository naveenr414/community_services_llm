import React, { useRef, useContext, useEffect } from 'react';
import '../styles/feature.css';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import ReactMarkdown from 'react-markdown';
import { jsPDF } from 'jspdf';
import { BenefitContext, ResourceContext, WellnessContext } from './AppStateContextProvider.js';

function GenericChat({ context, title, baseUrl, showLocation }) {
  const {
    inputText, setInputText,
    modelSelect, setModel,
    inputLocationText, setInputLocationText,
    newMessage, setNewMessage,
    conversation, setConversation,
    submitted,
    chatConvo, setChatConvo,
    resetContext
  } = useContext(context);

  const inputRef = useRef(null); // Ref for the textarea to adjust height
  const latestMessageRef = useRef(newMessage);

  const handleInputChange = (e) => {
    setInputText(e.target.value);
    adjustTextareaHeight(e.target); // Adjust textarea height dynamically
  };

  const handleModelChange = (e) => setModel(e.target.value);
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChangeLocation = (e) => setInputLocationText(e.target.value);

  const handleNewSession = async () => {
    abortController.abort();
    abortController = new AbortController();
    resetContext();
  };

  let shouldFetch = true;
  let abortController = new AbortController();
  let isRequestInProgress = false;

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && isRequestInProgress) {
      abortController.abort();
      isRequestInProgress = false;
    }
  });

  const handleSubmit = async () => {
    if (inputText.trim() && shouldFetch && !isRequestInProgress) {
      const newMessage = inputText.trim() + "\n Location: " + (inputLocationText.trim() || "New Jersey");
      const userMessage = { sender: 'user', text: inputText.trim() };
      setConversation((prev) => [...prev, userMessage]);
      setInputText('');
      setChatConvo((prev) => [...prev, { 'role': 'user', 'content': inputText.trim() }]);
      setNewMessage("");

      const botMessage = { sender: "bot", text: "Loading..." };
      setConversation((prev) => [...prev, botMessage]);
      shouldFetch = false;

      abortController.abort();
      abortController = new AbortController();
      isRequestInProgress = true;

      await fetchEventSource(baseUrl, {
        method: "POST",
        headers: { Accept: "text/event-stream", 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify({ "text": newMessage, "previous_text": chatConvo, "model": modelSelect }),
        onopen(res) {
          if (res.status >= 400 && res.status < 500 && res.status !== 429) {
            console.log("Client-side error ", res);
          }
        },
        onmessage(event) {
          setNewMessage((prev) => {
            const updatedMessage = prev + event.data.replaceAll("<br/>", "\n");
            const botMessage = { sender: "bot", text: updatedMessage };
            setConversation((convPrev) => {
              if (convPrev.length > 0) {
                return [...convPrev.slice(0, -1), botMessage];
              }
              return [botMessage];
            });
            return updatedMessage;
          });
        },
        onclose() {
          setChatConvo((prev) => [...prev, { 'role': 'system', 'content': latestMessageRef.current }]);
          shouldFetch = true;
        },
        onerror(err) {
          shouldFetch = true;
          console.log("There was an error from server", err);
        },
        retryInterval: 0
      });
    }
  };

  // Function to adjust the height of the textarea dynamically
  const adjustTextareaHeight = (textarea) => {
    if (textarea) {
      textarea.style.height = 'auto'; // Reset height
      textarea.style.height = `${textarea.scrollHeight}px`; // Set height based on content
    }
  };

  // Adjust height of textarea on initial render and when `inputText` changes
  useEffect(() => {
    if (inputRef.current) {
      adjustTextareaHeight(inputRef.current);
    }
  }, [inputText]);

  // Function to export chat history as PDF
  const exportChatToPDF = () => {
    const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4', // Standard A4 size
    });
    
    // Add a title to the PDF
    doc.setFontSize(16);
    doc.text('Chat History', 10, 10);
    
    // Formatting variables
    let yPosition = 20; // Initial Y position
    const lineHeight = 10; // Line height
    const pageHeight = doc.internal.pageSize.height; // Page height
    
    conversation.forEach((msg) => {
    const sender = msg.sender === 'user' ? 'You' : 'Bot';
    const text = `${sender}: ${msg.text}`;
    
    // Split long text into multiple lines to fit within the page width
    const lines = doc.splitTextToSize(text, 180);
    
    lines.forEach((line) => {
      if (yPosition + lineHeight > pageHeight - 10) {
        // Add a new page if the content exceeds the current page
        doc.addPage();
        yPosition = 10; // Reset Y position for the new page
      }
      doc.text(line, 10, yPosition); // Add the line to the current position
      yPosition += lineHeight; // Move to the next line position
    });
    });
    
    // Save the PDF
    doc.save('Chat_History.pdf');
    };


  return (
    <div className="resource-recommendation-container">
      <div className={`left-section ${submitted ? 'submitted' : ''}`}>
        <h1 className="page-title">{title}</h1>
        <h2 className="instruction">
          What is your client’s needs and goals for today’s meeting?
        </h2>
        <div className={`conversation-thread ${submitted ? 'visible' : ''}`}>
          {conversation.map((msg, index) => (
            <div
              key={index}
              className={`message-blurb ${msg.sender === 'user' ? 'user' : 'bot'}`}
            >
              <ReactMarkdown children={msg.text} />
            </div>
          ))}
        </div>
        <div className={`input-section ${submitted ? 'input-bottom' : ''}`}>
          {showLocation && (
            <div className="input-box">
              <textarea
                className="input-bar"
                placeholder={'Enter location (city or county)'}
                value={inputLocationText}
                onChange={handleInputChangeLocation}
                rows={1}
              />
            </div>
          )}
          <div className="input-box">
            <textarea
              className="input-bar"
              ref={inputRef} // Attach the ref for dynamic height adjustment
              placeholder={submitted ? 'Write a follow-up to update...' : 'Describe your client’s situation...'}
              value={inputText}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              style={{ overflow: 'hidden', resize: 'none' }} // Styling to prevent manual resizing
            />
            <button className="submit-button" onClick={handleSubmit}>
              ➤
            </button>
          </div>
          <div className="backend-selector-div">
            <select
              onChange={handleModelChange}
              value={modelSelect}
              name="model"
              id="model"
              className="backend-select"
            >
              <option value="copilot">Option A</option>
              <option value="chatgpt">Option B</option>
            </select>
            <button
              className="submit-button"
              style={{ width: '100px', height: '100%', marginLeft: '20px' }}
              onClick={handleNewSession}
            >
              Reset Session
            </button>
            <button
              className="submit-button"
              style={{ width: '150px', height: '100%', marginLeft: '20px' }}
              onClick={exportChatToPDF} // Button to export PDF
            >
              Save Session History
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export const ResourceRecommendation = () => (
  <GenericChat
    context={ResourceContext}
    title="Resource Database"
    baseUrl={`http://${window.location.hostname}:8000/resource_response/`}
    showLocation={true}
  />
);

export const WellnessGoals = () => (
  <GenericChat
    context={WellnessContext}
    title="Wellness Goals"
    baseUrl={`http://${window.location.hostname}:8000/wellness_response/`}
    showLocation={false}
  />
);

export const BenefitEligibility = () => (
  <GenericChat
    context={BenefitContext}
    title="Benefit Eligibility"
    baseUrl={`http://${window.location.hostname}:8000/benefit_response/`}
    showLocation={false}
  />
);

export default GenericChat;
import React, { useRef, useContext, useEffect, useState } from 'react';
import './GenericChat.css';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { jsPDF } from 'jspdf';
import io from 'socket.io-client';
import '../styles/feature.css';
import {WellnessContext } from './AppStateContextProvider';

function GenericChat({ context, title, socketServerUrl, showLocation, tool }) {
  const {
    inputText, setInputText,
    inputLocationText, setInputLocationText,
    conversation, setConversation,
    submitted,
    chatConvo, setChatConvo,
    organization,setOrganization,
  } = useContext(context);

  const inputRef = useRef(null);
  const conversationEndRef = useRef(null);
  const [socket, setSocket] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [goalsList, setGoalsList] = useState([]);
  const [resourcesList, setResourcesList] = useState([]);

  useEffect(() => {
    const newSocket = io(socketServerUrl, {
      transports: ['websocket'],
      reconnectionAttempts: 5,
    });
    setSocket(newSocket);

    newSocket.on('connect', () => {
      console.log('[Socket.io] Connected to server');
    });

    newSocket.on('welcome', (data) => {
      console.log('[Socket.io] Received welcome message:', data);
    });

    // ─── Chat streaming ───────────────────────────────────────────────
    newSocket.on('generation_update', (data) => {
      console.log('[Socket.io] generation_update:', data);
      if (typeof data.chunk === 'string') {
        setConversation(prev => {
          if (prev.length > 0 && prev[prev.length - 1].sender === 'bot') {
            const updated = [...prev];
            updated[updated.length - 1].text = data.chunk;
            return updated;
          }
          return [...prev, { sender: 'bot', text: data.chunk }];
        });
      }
    });

    // ─── Goals/Resources metadata ────────────────────────────────────
    newSocket.on('goals_update', ({ goals, resources }) => {
      console.log('[Socket.io] goals_update:', goals, resources);
      setGoalsList(goals);
      setResourcesList(resources);
    });

    newSocket.on('generation_complete', (data) => {
      console.log('[Socket.io] Generation complete:', data);
      setIsGenerating(false);
    });

    newSocket.on('error', (error) => {
      console.error('[Socket.io] Error:', error);
    });

    return () => {
      newSocket.disconnect();
    };
  }, [socketServerUrl]);

  const handleScroll = (e) => {
    const { scrollTop, clientHeight, scrollHeight } = e.target;
    if (scrollTop + clientHeight >= scrollHeight - 50) {
      setAutoScrollEnabled(true);
    } else {
      setAutoScrollEnabled(false);
    }
  };
  
  useEffect(() => {
    if (autoScrollEnabled && conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation, autoScrollEnabled]);
  

  const adjustTextareaHeight = (textarea) => {
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  };

  useEffect(() => {
    if (inputRef.current) {
      adjustTextareaHeight(inputRef.current);
    }
  }, [inputText]);

  const handleInputChange = (e) => {
    setInputText(e.target.value);
    adjustTextareaHeight(e.target);
  };

  const handleInputChangeLocation = (e) => {
    setInputLocationText(e.target.value);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!inputText.trim() || isGenerating) return;

    const messageText = inputText.trim();

    const userMsg = { sender: 'user', text: inputText.trim() };
    setConversation((prev) => [...prev, userMsg]);
    setChatConvo((prev) => [...prev, { role: 'user', content: inputText.trim() }]);
    setInputText('');

    setConversation((prev) => [...prev, { sender: 'bot', text: "Loading..." }]);
    setIsGenerating(true);

    if (socket) {
      console.log('[GenericChat] Emitting start_generation event');
      socket.emit('start_generation', {
        text: messageText,
        previous_text: chatConvo,
        model: "A",
        organization: organization, 
        tool,
      });
    } else {
      console.error('[GenericChat] Socket is not connected.');
    }
  };
  
  const handleNewSession = () => {
    window.location.reload();
  };

  const exportChatToPDF = () => {
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });
    doc.setFontSize(16);
    doc.text('Chat History', 10, 10);

    let yPosition = 20;
    const lineHeight = 10;
    const pageHeight = doc.internal.pageSize.height;

    conversation.forEach((msg) => {
      const sender = msg.sender === 'user' ? 'You' : 'Bot';
      const text = `${sender}: ${msg.text}`;
      const lines = doc.splitTextToSize(text, 180);
      lines.forEach((line) => {
        if (yPosition + lineHeight > pageHeight - 10) {
          doc.addPage();
          yPosition = 10;
        }
        doc.text(line, 10, yPosition);
        yPosition += lineHeight;
      });
    });

    doc.save('Chat_History.pdf');
  };

  return (
    <div className="resource-recommendation-container">
      <div className={`left-section ${submitted ? 'submitted' : ''}`}>
        <h1 className="page-title">{title}</h1>
        <h2 className="instruction">
          What is the service user’s needs and goals for today’s meeting?
        </h2>
        <div 
          className={`conversation-thread ${submitted ? 'visible' : ''}`}
          onScroll={handleScroll}
          style={{ overflowY: 'auto', maxHeight: '80vh' }} // ensure the container is scrollable
        >
          {conversation.map((msg, index) => (
            <div key={index} className={`message-blurb ${msg.sender === 'user' ? 'user' : 'bot'}`}>
              <ReactMarkdown
                children={msg.text}
                skipHtml={false}
                rehypePlugins={[rehypeRaw]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                }}
              />
            </div>
          ))}
          <div ref={conversationEndRef} />
        </div>

        <div className={`input-section ${submitted ? 'input-bottom' : ''}`}>
          {showLocation && (
            <div className="input-box">
              <textarea
                className="input-bar"
                placeholder="Enter location (city or county)"
                value={inputLocationText}
                onChange={handleInputChangeLocation}
                rows={1}
              />
            </div>
          )}
          <div className="input-box">
            <textarea
              className="input-bar"
              ref={inputRef}
              placeholder={
                submitted
                  ? 'Write a follow-up to update...'
                  : 'Describe the service user’s situation...'
              }
              value={inputText}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              style={{ overflow: 'hidden', resize: 'none' }}
            />
            <button className="submit-button" onClick={handleSubmit}>
              ➤
            </button>
          </div>
          <div className="backend-selector-div">
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
              onClick={exportChatToPDF}
            >
              Save Session History
            </button>
            {tool === "wellness" && (
              <button
                className="submit-button"
                style={{ width: '150px', height: '100%', marginLeft: '20px' }}
                onClick={() => window.open('https://www.youtube.com/watch?v=4rg1wmo2Y8w', '_blank')}
              >
                Tutorial
              </button>
            )}
          </div>
        </div>
      </div>
      {/* ← NEW: Right‐hand panel containing two empty boxes */}
      <div className="right-section">
      {/* Goals panel */}
      <div className="goals-box" style={{ height: '400px' }}>
        <h3>Goals</h3>
        <div className="scroll-container">
          {goalsList.map((goal, idx) => (
            <div key={idx} className="resource-item">
              <ReactMarkdown
                children={goal}
                skipHtml={false}
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                }}
              />
            </div>
          ))}
        </div>
      </div>

        {/* Resources panel */}
        <div className="resources-box" style={{ height: '500px' }}>
          <h3>Resources</h3>
          <div className="scroll-container">
            {resourcesList.map((res, idx) => {
              // Parse the backend’s flat “Name — [Link](url) (Action: act)” string
              // into a pretty markdown with name bold, link & action on their own lines.
              const regex = /^(.*?)\s+—\s+\[Link\]\((.*?)\)\s*(?:\(Action:\s*(.*?)\))?$/;
              const match = res.match(regex);
              let mdString = res;
              if (match) {
                const [, name, linkUrl, action] = match;
                mdString =
                  `**${name}**  \n` +     // bold name + linebreak
                  `[Link](${linkUrl})  \n` + // link + linebreak
                  `**Action:** ${action}`;   // action
              }

              return (
                <div key={idx} className="resource-item">
                  <ReactMarkdown
                    children={mdString}
                    skipHtml={false}
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={{
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {children}
                        </a>
                      ),
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export const WellnessGoals = () => (
  <GenericChat
    context={WellnessContext}
    title="Wellness Goals"
    socketServerUrl={`http://${window.location.hostname}:8000`}
    showLocation={false}
    tool="wellness"
  />
);

export default GenericChat;

import { useState, useRef, useEffect } from 'react';
import { GenerativeArtScene } from "./ui/anomalous-matter-hero";
import { 
  MessageSquare, 
  Clock, 
  Settings as SettingsIcon, 
  HelpCircle, 
  Sun, 
  Moon, 
  ChevronDown, 
  Paperclip, 
  Camera,
  Mic, 
  Compass, 
  Send,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
  ChevronUp,
  User,
  Activity,
  Smile,
  Mic2,
  Plus,
  MessageSquarePlus,
  Search,
  X
} from 'lucide-react';

interface RelatusDashboardProps {
  onLogout: () => void;
  theme?: 'dark' | 'light';
}

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
}

export default function RelatusDashboard({ onLogout, theme = 'dark' }: RelatusDashboardProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isDark = theme === 'dark';
  const [inputText, setInputText] = useState('');
  const [placeholderText, setPlaceholderText] = useState("Ask me anything");
  const [typedParagraph, setTypedParagraph] = useState("");
  const [paragraphDone, setParagraphDone] = useState(false);

  // Typewriter effect for the main chat starting text, beginning at 4200ms
  useEffect(() => {
    const startTimer = setTimeout(() => {
      const fullText = "Not sure where to start? Get started by describing a task and Chat can do the rest.";
      let currentIndex = 0;
      const interval = setInterval(() => {
        currentIndex++;
        setTypedParagraph(fullText.slice(0, currentIndex));
        if (currentIndex >= fullText.length) {
          clearInterval(interval);
          setParagraphDone(true);
        }
      }, 30); // type one letter every 30ms
      return () => clearInterval(interval);
    }, 4200);
    return () => clearTimeout(startTimer);
  }, []);

  // Typewriter effect for placeholder text, beginning after the paragraph finishes typing
  useEffect(() => {
    if (!paragraphDone) return;

    const fullText = "Ask me anything";
    let currentIndex = 0;
    let intervalId: any;
    let restartTimeoutId: any;

    const startTyping = () => {
      setPlaceholderText("");
      currentIndex = 0;
      intervalId = setInterval(() => {
        currentIndex++;
        setPlaceholderText(fullText.slice(0, currentIndex));
        if (currentIndex >= fullText.length) {
          clearInterval(intervalId);
          // Wait 2 seconds, then restart the animation
          restartTimeoutId = setTimeout(() => {
            startTyping();
          }, 2000);
        }
      }, 100);
    };

    startTyping();

    return () => {
      if (intervalId) clearInterval(intervalId);
      if (restartTimeoutId) clearTimeout(restartTimeoutId);
    };
  }, [paragraphDone]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchHovered, setIsSearchHovered] = useState(false);
  const [hoveredSearchItem, setHoveredSearchItem] = useState<string | null>(null);
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Escape key for closing search dialog
  useEffect(() => {
    if (!isSearchOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen]);

  // Auto collapse sidebar after the introductory glow animation completes (at 4200ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsCollapsed(true);
    }, 4200);
    return () => clearTimeout(timer);
  }, []);

  // Click outside to close attach menu
  useEffect(() => {
    if (!isAttachMenuOpen) return;
    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.attach-menu-container') && !target.closest('.attach-button')) {
        setIsAttachMenuOpen(false);
      }
    };
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, [isAttachMenuOpen]);

  // Auto scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Derived styling values based on theme (frosted glassmorphism)
  const bgColor = isDark ? '#000000' : '#ffffff';
  // Sidebar: true translucent glass that shows the background through
  const sidebarBg = isDark ? 'rgba(15, 17, 25, 0.75)' : 'rgba(255, 255, 255, 0.65)';
  const sidebarBorder = isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.08)';
  const textColor = isDark ? '#f3f4f6' : '#1f2937';
  const textMuted = isDark ? 'rgba(255, 255, 255, 0.45)' : 'rgba(0, 0, 0, 0.45)';
  const cardBg = isDark ? 'rgba(255, 255, 255, 0.04)' : '#f9fafb';
  const cardBorder = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
  const inputBg = isDark ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.01)';
  const itemHoverBg = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)';
  const activeItemBg = isDark ? 'rgba(255, 255, 255, 0.14)' : 'rgba(0, 0, 0, 0.06)';
  const activeItemText = isDark ? '#ffffff' : '#111827';

  const handleSend = async () => {
    if (!inputText.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    const queryText = inputText;
    setInputText('');
    setIsGenerating(true);

    const BACKEND_URL = 'http://127.0.0.1:8000';
    const TIMEOUT_MS = 10000;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: queryText }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      let data: any;
      try {
        data = await response.json();
      } catch {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          text: 'Unexpected response format',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, aiMsg]);
        setIsGenerating(false);
        return;
      }

      if (!response.ok) {
        const errText = (data && (data.detail || data.message)) || 'Service unavailable';
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          text: errText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, aiMsg]);
        setIsGenerating(false);
        return;
      }

      const reply = data.answer && data.answer.trim() ? data.answer : 'No result found';

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, aiMsg]);
      setIsGenerating(false);
    } catch (err: any) {
      clearTimeout(timeoutId);
      let errText = 'Server unavailable';
      if (err && err.name === 'AbortError') {
        errText = 'Request timed out';
      }

      const retryMsg = errText + ' — tap to retry';
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: retryMsg,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsGenerating(false);
    }
  };


  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const prefillInput = (text: string) => {
    setInputText(text);
  };

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      backgroundColor: bgColor,
      color: textColor,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      overflow: 'hidden',
      position: 'relative',
      transition: 'background-color 0.3s, color 0.3s'
    }}>

      {/* CSS Styles injection */}
      <style dangerouslySetInnerHTML={{ __html: `
        .sidebar-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          border-radius: 12px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          color: ${textMuted};
          transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          user-select: none;
          text-decoration: none;
          position: relative;
          overflow: hidden;
        }
        .sidebar-item::after {
          content: '';
          position: absolute;
          bottom: -2px;
          left: 10%;
          width: 80%;
          height: 0px;
          border-radius: 50%;
          background: ${isDark ? 'rgba(255,255,255,0.0)' : 'rgba(120,194,87,0.0)'};
          transition: height 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
          pointer-events: none;
        }
        .sidebar-item:hover {
          background: ${itemHoverBg};
          color: ${textColor};
          transform: translateY(-1px);
          box-shadow: 0 -1px 0 0 ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.6)'} inset;
        }
        .sidebar-item:hover::after {
          height: 8px;
          background: ${isDark ? 'rgba(255,255,255,0.15)' : 'rgba(120,194,87,0.18)'};
          box-shadow: 0 0 18px 6px ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(120,194,87,0.22)'};
          bottom: 0px;
        }
        .sidebar-item.active {
          background: ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'};
          color: ${textColor};
          font-weight: 600;
          border: 1px solid ${isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'};
          box-shadow: 0 0 8px ${isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'};
        }
        .sidebar-item.active:hover {
          background: ${isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)'};
          box-shadow: 0 0 12px ${isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)'};
          transform: translateY(-2px);
        }
        }
        .dashboard-card {
          background: ${cardBg};
          border: 1px solid ${cardBorder};
          border-radius: 16px;
          padding: 24px;
          transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          cursor: pointer;
          position: relative;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0,0,0,0.01);
        }
        .dashboard-card:hover {
          transform: translateY(-4px);
          border-color: ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'};
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.05);
        }
        .input-glow-box {
          /* Base border: black in light mode, white in dark mode */
          border: 1px solid ${isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)'};
          transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
          background: ${isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.15)'} !important;
          backdrop-filter: blur(24px) saturate(180%);
          -webkit-backdrop-filter: blur(24px) saturate(180%);
        }
        .input-glow-box:hover {
          /* Glowy border: retain white glow for dark, black glow for light */
          border-color: ${isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)'} !important;
          box-shadow: ${isDark ? "0 0 0 1px rgba(255,255,255,0.6), 0 0 20px 4px rgba(255,255,255,0.15), 0 8px 32px rgba(255,255,255,0.06)" : "0 0 0 1px rgba(0,0,0,0.6), 0 0 20px 4px rgba(0,0,0,0.15), 0 8px 32px rgba(0,0,0,0.06)"} !important;
          transform: translateY(-3px);
        }
        .input-glow-box:focus-within {
          border-color: ${isDark ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.95)'} !important;
          box-shadow: ${isDark ? "0 0 0 1.5px rgba(255,255,255,0.7), 0 0 28px 6px rgba(255,255,255,0.18), 0 12px 40px rgba(255,255,255,0.08)" : "0 0 0 1.5px rgba(0,0,0,0.7), 0 0 28px 6px rgba(0,0,0,0.18), 0 12px 40px rgba(0,0,0,0.08)"} !important;
          transform: translateY(-3px);
        }
        /* Placeholder styling to ensure visibility in both themes */
        .input-glow-box textarea::placeholder {
          color: darkgrey !important;
          opacity: 1 !important;
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'};
        }
        @keyframes floatMsg {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes sidebarGlow {
          0%, 100% { 
            box-shadow: 4px 0 25px 2px ${isDark ? 'rgba(56, 189, 248, 0.28)' : 'rgba(0, 0, 0, 0.08)'}; 
          }
          50% { 
            box-shadow: 6px 0 45px 5px ${isDark ? 'rgba(56, 189, 248, 0.48)' : 'rgba(0, 0, 0, 0.16)'}; 
          }
        }
        @keyframes centralAnimationZoom {
          from {
            transform: scale(0);
            opacity: 0;
          }
          to {
            transform: scale(1);
            opacity: 1;
          }
        }
        @keyframes chatbotSlideUp {
          from {
            transform: translateY(30px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        @keyframes collapseIconIndicator {
          0%, 100% {
            transform: scale(1) translateX(0);
            box-shadow: none;
            background: transparent;
            color: ${textMuted};
          }
          25%, 75% {
            transform: scale(1.1) translateX(-4px);
            background: ${itemHoverBg};
            color: ${textColor};
            box-shadow: 0 0 12px 2px ${isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.08)'};
          }
          50% {
            transform: scale(1) translateX(0);
            background: transparent;
            color: ${textMuted};
            box-shadow: none;
          }
        }
      `}} />

      {/* ─────────────────── SIDEBAR ─────────────────── */}
      <aside style={{
        width: isCollapsed ? '72px' : '260px',
        backgroundColor: sidebarBg,
        borderRight: `1px solid ${sidebarBorder}`,
        backdropFilter: 'blur(32px) saturate(200%) brightness(1.08)',
        WebkitBackdropFilter: 'blur(32px) saturate(200%) brightness(1.08)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '20px 12px',
        zIndex: 10,
        boxSizing: 'border-box',
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.3s, border-color 0.3s',
        position: 'relative',
        animation: 'sidebarGlow 5s infinite ease-in-out'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'flex-end',
          gap: '8px',
          marginBottom: '20px',
          padding: '0 2px',
          boxSizing: 'border-box',
          width: '100%'
        }}>
          {!isCollapsed && (
            <img
              src="/watermark.png"
              alt="Reliance Retail Logo"
              style={{
                height: "105px",
                width: "auto",
                objectFit: "contain",
                marginRight: 'auto',
                paddingLeft: '4px',
              }}
            />
          )}
          {!isCollapsed && (
            <button 
              onClick={() => setIsSearchOpen(true)}
              onMouseEnter={() => setIsSearchHovered(true)}
              onMouseLeave={() => setIsSearchHovered(false)}
              aria-label="Search"
              style={{
                background: 'none',
                border: 'none',
                color: textMuted,
                cursor: 'pointer',
                padding: '8px',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                backgroundColor: isSearchHovered ? itemHoverBg : 'transparent',
                transform: isSearchHovered ? 'translateY(-2px) scale(1.08)' : 'scale(1)',
                boxShadow: isSearchHovered 
                  ? (isDark ? '0 0 14px 2px rgba(255, 255, 255, 0.22)' : '0 0 14px 2px rgba(0, 0, 0, 0.1)') 
                  : 'none',
              }}
            >
              <Search size={18} />
            </button>
          )}
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{
              background: 'none',
              border: 'none',
              color: textMuted,
              cursor: 'pointer',
              padding: '8px',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              animation: 'collapseIconIndicator 2s ease-in-out 2.2s 1',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.backgroundColor = itemHoverBg;
              e.currentTarget.style.color = textColor;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = textMuted;
            }}
          >
            {isCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* Extended glass morphed container with translucent background for all buttons */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            background: isDark ? 'rgba(255, 255, 255, 0.025)' : 'rgba(0, 0, 0, 0.015)',
            border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.05)',
            borderRadius: '20px',
            padding: '16px 8px',
            boxSizing: 'border-box',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            boxShadow: isDark 
              ? 'inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 32px rgba(0,0,0,0.2)' 
              : 'inset 0 1px 0 rgba(255,255,255,0.4), 0 8px 32px rgba(0,0,0,0.03)',
            overflow: 'hidden',
          }}
        >
          {/* Navigation Items */}
          <nav style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            marginBottom: '20px'
          }}>
          {/* New Chat Button */}
          <div 
            className={`sidebar-item ${messages.length === 0 ? 'active' : ''}`} 
            onClick={() => { setMessages([]); setInputText(''); }} 
            style={{ justifyContent: isCollapsed ? 'center' : 'flex-start' }}
          >
            <Plus size={18} style={{ flexShrink: 0 }} />
            {!isCollapsed && <span>New Chat</span>}
          </div>

          {/* History Collapsable Tab */}
          <div 
            className="sidebar-item" 
            onClick={() => {
              if (isCollapsed) {
                setIsCollapsed(false);
                setIsHistoryOpen(true);
              } else {
                setIsHistoryOpen(!isHistoryOpen);
              }
            }} 
            style={{ 
              display: 'flex', 
              justifyContent: isCollapsed ? 'center' : 'space-between', 
              alignItems: 'center' 
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Clock size={18} style={{ flexShrink: 0 }} />
              {!isCollapsed && <span>Recents</span>}
            </div>
            {!isCollapsed && (
              <ChevronDown size={14} style={{ transform: isHistoryOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s', opacity: 0.7 }} />
            )}
          </div>

          {/* History Items (Collapsable Chat Logs) */}
          {isHistoryOpen && !isCollapsed && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '2px',
              paddingLeft: '14px',
              marginTop: '4px',
              borderLeft: `1.5px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'}`,
              animation: 'floatMsg 0.25s ease',
              marginBottom: '10px'
            }}>
              {messages.length > 0 ? (
                /* Dynamic session chat in history */
                <div 
                  className="sidebar-item active" 
                  onClick={() => {}}
                  style={{ 
                    padding: '4px 8px', 
                    fontSize: '12px',
                    backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)'
                  }}
                >
                  <MessageSquare size={14} style={{ flexShrink: 0, opacity: 0.8 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 600 }}>
                    {messages[0].text.length > 20 ? messages[0].text.slice(0, 20) + '...' : messages[0].text}
                  </span>
                </div>
              ) : (
                /* Empty history state */
                <div style={{ 
                  padding: '8px 12px', 
                  fontSize: '12px', 
                  color: textMuted, 
                  fontStyle: 'italic',
                  userSelect: 'none'
                }}>
                  No recent chats
                </div>
              )}
            </div>
          )}
        </nav>

        {/* Scrollable list area for chats & other content */}
        <div className="custom-scrollbar" style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '18px',
          marginBottom: '20px',
          boxSizing: 'border-box'
        }}>
          {/* Unified Settings, Help Stack */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: 'auto' }}>
            <div className="sidebar-item" style={{ padding: isCollapsed ? '10px' : '10px 14px', justifyContent: isCollapsed ? 'center' : 'flex-start' }}>
              <SettingsIcon size={18} style={{ flexShrink: 0 }} />
              {!isCollapsed && <span>Settings</span>}
            </div>
            
            <div className="sidebar-item" style={{ padding: isCollapsed ? '10px' : '10px 14px', justifyContent: isCollapsed ? 'center' : 'flex-start' }}>
              <HelpCircle size={18} style={{ flexShrink: 0 }} />
              {!isCollapsed && <span>Help</span>}
            </div>
          </div>
        </div>

        {/* Account / Profile — same size as other sidebar items */}
        <div style={{ position: 'relative' }}>
          <div
            className="sidebar-item"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            style={{
              padding: isCollapsed ? '10px' : '10px 14px',
              justifyContent: isCollapsed ? 'center' : 'space-between',
              background: showProfileMenu ? activeItemBg : undefined
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Small avatar badge */}
              <div style={{
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #f472b6, #ec4899)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: '8px',
                fontWeight: 700,
                flexShrink: 0
              }}>JW</div>
              {!isCollapsed && <span>My Account</span>}
            </div>
            {!isCollapsed && (
              <div style={{ color: textMuted, display: 'flex', alignItems: 'center' }}>
                {showProfileMenu ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </div>
            )}
          </div>

          {/* Profile Dropdown Menu */}
          {showProfileMenu && (
            <div style={{
              position: 'absolute',
              bottom: '100%',
              left: 0,
              marginBottom: '6px',
              width: showProfileMenu ? '200px' : '0px',
              background: isDark ? '#1e2230' : '#ffffff',
              border: `1px solid ${sidebarBorder}`,
              borderRadius: '12px',
              padding: showProfileMenu ? '6px' : '0px 6px',
              overflow: 'hidden',
              boxShadow: '0 -10px 25px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05)',
              zIndex: 100,
              transition: 'width 0.3s ease, padding 0.3s ease',
              animation: 'floatMsg 0.2s ease',
              transform: showProfileMenu ? 'translateX(0)' : 'translateX(-100%)',
              transformOrigin: 'left'
            }}>
              <div className="sidebar-item" onClick={() => { setShowProfileMenu(false); alert("Profile settings are coming soon!"); }} style={{ fontSize: '13px', padding: '8px 12px' }}>
                <User size={15} />
                <span>My Profile</span>
              </div>
              <div className="sidebar-item" onClick={onLogout} style={{ fontSize: '13px', padding: '8px 12px', color: '#ef4444' }}>
                <LogOut size={15} />
                <span>Log Out</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>

      {/* ─────────────────── MAIN CHAT AREA ─────────────────── */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
        zIndex: 1,
        boxSizing: 'border-box'
      }}>


        {/* Messages Scrolling Container or Welcome Grid */}
        <div className="custom-scrollbar" style={{
          flex: 1,
          overflowY: 'auto',
          padding: '40px 8% 24px 8%',
          display: 'flex',
          flexDirection: 'column',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 2
        }}>
          {messages.length === 0 ? (
            /* Welcome / Initial Screen */
            <div style={{
              margin: 'auto',
              maxWidth: '860px',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              paddingBottom: '20px'
            }}>
              {/* Generative art scene (icosahedron) above the instruction text */}
              <div className="chatbot-avatar" style={{
                width: '300px',
                height: '300px',
                position: 'relative',
                marginBottom: '28px',
                borderRadius: '50%',
                overflow: 'hidden',
                boxShadow: isDark 
                  ? '0 0 50px rgba(56,189,248,0.2), inset 0 0 30px rgba(56,189,248,0.15)' 
                  : '0 0 35px rgba(30,58,138,0.08), inset 0 0 25px rgba(30,58,138,0.05)',
                border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.05)',
                background: isDark ? '#111' : '#f9f9f9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10,
                animation: 'centralAnimationZoom 1.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
              }}>
                <GenerativeArtScene />
              </div>

              <p style={{
                fontSize: '16px',
                color: textColor,
                maxWidth: '600px',
                lineHeight: 1.6,
                marginBottom: '48px',
                marginTop: '0',
                position: 'relative',
                zIndex: 10,
                opacity: 0,
                animation: 'chatbotSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.1s forwards',
              }}>
                {typedParagraph || "\u00a0"}
              </p>


            </div>
          ) : (
            /* Chat Messages List */
            <div style={{
              maxWidth: '860px',
              width: '100%',
              margin: '0 auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '24px'
            }}>
              {messages.map((msg) => (
                <div 
                  key={msg.id} 
                  style={{
                    display: 'flex',
                    gap: '16px',
                    alignItems: 'flex-start',
                    animation: 'floatMsg 0.3s ease',
                    alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row'
                  }}
                >
                  {/* Sender Avatar */}
                  {msg.sender === 'user' ? (
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '50%',
                      backgroundColor: '#ec4899',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#ffffff',
                      fontWeight: 700,
                      fontSize: '12px',
                      flexShrink: 0
                    }}>
                      JW
                    </div>
                  ) : (
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '50%',
                      backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <svg width="20" height="20" viewBox="0 0 40 40" fill="none">
                        <rect x="6" y="6" width="13" height="13" rx="4" fill="#78c257" transform="rotate(-15 6 6)" opacity="0.9" />
                        <rect x="21" y="6" width="13" height="13" rx="4" fill="#ffb020" transform="rotate(15 21 6)" opacity="0.9" />
                        <rect x="6" y="21" width="13" height="13" rx="4" fill="#14b8a6" transform="rotate(15 6 21)" opacity="0.9" />
                        <rect x="21" y="21" width="13" height="13" rx="4" fill="#ec4899" transform="rotate(-15 21 21)" opacity="0.9" />
                      </svg>
                    </div>
                  )}

                  {/* Message bubble */}
                  <div style={{
                    padding: '12px 18px',
                    borderRadius: msg.sender === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                    backgroundColor: msg.sender === 'user' ? '#007AFF' : (isDark ? '#333333' : '#E9E9EB'),
                    color: msg.sender === 'user' ? '#FFFFFF' : (isDark ? '#FFFFFF' : '#000000'),
                    fontSize: '15px',
                    lineHeight: 1.4,
                    whiteSpace: 'pre-wrap'
                  }}>
                    {msg.text}
                    <div style={{
                      fontSize: '10px',
                      color: msg.sender === 'user' ? 'rgba(255,255,255,0.7)' : textMuted,
                      textAlign: 'right',
                      marginTop: '6px'
                    }}>
                      {msg.timestamp}
                    </div>
                  </div>
                </div>
              ))}

              {isGenerating && (
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center', alignSelf: 'flex-start' }}>
                  <div style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <svg width="20" height="20" viewBox="0 0 40 40" fill="none" className="pulse-animation">
                      <rect x="6" y="6" width="13" height="13" rx="4" fill="#78c257" />
                    </svg>
                  </div>
                  <span style={{ fontSize: '14px', color: textMuted }}>Relatus is thinking...</span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input & Footer Container */}
        <div style={{
          padding: '0 8% 24px 8%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 2,
          opacity: 0,
          animation: 'chatbotSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.3s forwards',
        }}>
          {/* Transparent Liquid Glass Input Box */}
          <div className="input-glow-box" style={{
            maxWidth: '860px',
            width: '100%',
            backgroundColor: 'transparent',
            borderRadius: '20px',
            padding: '16px 20px',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            {/* Top row: actual text input area */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <textarea 
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholderText}
                rows={1}
                style={{
                  flex: 1,
                  background: 'none',
                  border: 'none',
                  outline: 'none',
                  color: textColor,
                  fontSize: '15px',
                  fontFamily: 'inherit',
                  resize: 'none',
                  lineHeight: '22px',
                  maxHeight: '120px',
                  boxSizing: 'border-box',
                  padding: '4px 0'
                }}
              />
              <button 
                onClick={handleSend}
                disabled={!inputText.trim()}
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '50%',
                  border: '2px solid #fff',
                  background: inputText.trim() ? '#78c257' : (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'),
                  color: inputText.trim() ? '#ffffff' : textMuted,
                  cursor: inputText.trim() ? 'pointer' : 'default',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s',
                  boxShadow: inputText.trim() ? '0 0 8px rgba(255,255,255,0.6), 0 4px 12px rgba(120, 194, 87, 0.35)' : '0 0 8px rgba(255,255,255,0.6)',
                  transform: inputText.trim() ? 'translateY(-2px)' : 'none'
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 0 12px rgba(255,255,255,0.8), 0 4px 12px rgba(120, 194, 87, 0.35)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = inputText.trim() ? '0 0 8px rgba(255,255,255,0.6), 0 4px 12px rgba(120, 194, 87, 0.35)' : '0 0 8px rgba(255,255,255,0.6)'; }}
              >
                <Send size={16} />
              </button>
            </div>

            {/* Bottom Row: Attachments and character counter */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '8px',
              borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)'}`
            }}>
              {/* Attachment icons */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                position: 'relative'
              }}>
                <button 
                  className="attach-button"
                  onClick={() => setIsAttachMenuOpen(!isAttachMenuOpen)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: textMuted,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    fontSize: '13px',
                    fontWeight: 500,
                    padding: '4px 8px',
                    borderRadius: '6px',
                    transition: 'background 0.2s, color 0.2s'
                  }} onMouseEnter={e => { e.currentTarget.style.backgroundColor = itemHoverBg; e.currentTarget.style.color = textColor; }}
                     onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = textMuted; }}>
                  <Paperclip size={14} /> Attach
                </button>

                {isAttachMenuOpen && (
                  <div 
                    className="attach-menu-container"
                    style={{
                      position: 'absolute',
                      bottom: 'calc(100% + 12px)',
                      left: '0',
                      width: '280px',
                      backgroundColor: isDark ? '#1e1e1e' : '#ffffff',
                      border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                      borderRadius: '14px',
                      padding: '6px',
                      boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                      zIndex: 100,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '2px',
                      animation: 'floatMsg 0.18s ease',
                    }}
                  >
                    <div 
                      onClick={() => {
                        setIsAttachMenuOpen(false);
                        alert("File upload is coming soon!");
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        color: textColor,
                        fontSize: '14px',
                        fontWeight: 500,
                        transition: 'background 0.2s, color 0.2s',
                        userSelect: 'none',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.backgroundColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <Paperclip size={16} style={{ opacity: 0.8 }} />
                        <span>Add files or photos</span>
                      </div>
                      <span style={{ fontSize: '12px', color: textMuted, fontWeight: 400 }}>⌘U</span>
                    </div>

                    <div 
                      onClick={() => {
                        setIsAttachMenuOpen(false);
                        alert("Screenshot capture is coming soon!");
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '10px 14px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        color: textColor,
                        fontSize: '14px',
                        fontWeight: 500,
                        transition: 'background 0.2s, color 0.2s',
                        userSelect: 'none',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.backgroundColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <Camera size={16} style={{ opacity: 0.8 }} />
                        <span>Take a screenshot</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Character counter */}
              <div style={{
                fontSize: '12px',
                color: textMuted,
                fontWeight: 500
              }}>
                {inputText.length}/1,500
              </div>
            </div>
          </div>

          {/* Underneath Disclaimer Text */}
          <div style={{
            fontSize: '12px',
            color: textMuted,
            marginTop: '12px',
            textAlign: 'center',
            lineHeight: 1.5
          }}>
            Relatus may display inaccurate info, so please double check the response.{' '}
            <span style={{ fontWeight: 600, color: textColor, cursor: 'pointer', textDecoration: 'underline' }}>Your Privacy & Relatus.AI</span>
          </div>
        </div>
      </main>

      {/* ─────────────────── SEARCH POPUP MODAL ─────────────────── */}
      {isSearchOpen && (
        <>
          {/* Backdrop mask */}
          <div
            onClick={() => setIsSearchOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: isDark ? 'rgba(0,0,0,0.65)' : 'rgba(255,255,255,0.45)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
              zIndex: 10000,
              transition: 'all 0.3s ease',
            }}
          />

          {/* Centered Flexbox Wrapper */}
          <div
            style={{
              position: 'fixed',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10001,
              pointerEvents: 'none',
            }}
          >
            {/* Centered Command Menu Box */}
            <div
              style={{
                pointerEvents: 'auto',
                width: '90%',
                maxWidth: '640px',
                backgroundColor: isDark ? 'rgba(30, 30, 30, 0.92)' : 'rgba(255, 255, 255, 0.92)',
                backdropFilter: 'blur(30px) saturate(180%)',
                WebkitBackdropFilter: 'blur(30px) saturate(180%)',
                border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.08)',
                borderRadius: '16px',
                boxShadow: isDark 
                  ? '0 24px 64px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.06)' 
                  : '0 24px 64px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.4)',
                color: textColor,
                fontFamily: "'Inter', sans-serif",
                overflow: 'hidden',
                boxSizing: 'border-box',
                animation: 'floatMsg 0.25s ease-out forwards',
              }}
            >
            {/* Search Input Row */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              padding: '16px 20px',
              gap: '14px',
              position: 'relative'
            }}>
              <Search size={20} style={{ color: textMuted, flexShrink: 0 }} />
              <input
                type="text"
                autoFocus
                placeholder="Search chats and projects"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{
                  flex: 1,
                  background: 'none',
                  border: 'none',
                  outline: 'none',
                  color: textColor,
                  fontSize: '16px',
                  fontFamily: 'inherit',
                  padding: '4px 0',
                }}
              />
              
              {/* Close Button */}
              <button
                onClick={() => setIsSearchOpen(false)}
                aria-label="Close search"
                style={{
                  background: 'none',
                  border: 'none',
                  color: textMuted,
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'background 0.2s, color 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.backgroundColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)';
                  e.currentTarget.style.color = textColor;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = textMuted;
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Separator line */}
            <div style={{
              height: '1px',
              backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
              width: '100%'
            }} />

            {/* Results Area */}
            <div style={{
              padding: '8px',
              maxHeight: '340px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '2px'
            }}>
              {[
                { id: '1', title: 'Greeting', time: '' },
                { id: '2', title: 'x', time: 'Past week' },
                { id: '3', title: 'y', time: 'Past week' },
                { id: '4', title: 'z', time: 'Past week' },
              ]
                .filter(item => item.title.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((item, idx) => {
                  const isHovered = hoveredSearchItem === item.id;
                  // First item or hovered item gets active background to replicate the image style
                  const isActive = isHovered || (hoveredSearchItem === null && idx === 0);
                  
                  return (
                    <div
                      key={item.id}
                      onMouseEnter={() => setHoveredSearchItem(item.id)}
                      onMouseLeave={() => setHoveredSearchItem(null)}
                      onClick={() => {
                        setIsSearchOpen(false);
                        alert(`Opened chat: ${item.title}`);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 16px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        backgroundColor: isActive 
                          ? (isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)') 
                          : 'transparent',
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: 0 }}>
                        <MessageSquare 
                          size={16} 
                          style={{ 
                            color: isActive ? textColor : textMuted, 
                            opacity: isActive ? 0.9 : 0.6,
                            flexShrink: 0 
                          }} 
                        />
                        <span style={{ 
                          fontSize: '14.5px', 
                          fontWeight: isActive ? 600 : 400,
                          color: textColor,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {item.title}
                        </span>
                      </div>

                      {/* Right hand metadata (time) or enter arrow */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                        {item.time && !isActive && (
                          <span style={{ fontSize: '13px', color: textMuted }}>
                            {item.time}
                          </span>
                        )}
                        {isActive && (
                          <span 
                            style={{ 
                              fontSize: '15px', 
                              color: textMuted, 
                              opacity: 0.8,
                              display: 'flex',
                              alignItems: 'center'
                            }}
                          >
                            {/* Return arrow ↵ character */}
                            &#8629;
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      </>
    )}
  </div>
  );
}

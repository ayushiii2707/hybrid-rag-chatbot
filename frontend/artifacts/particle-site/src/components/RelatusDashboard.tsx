import { useState, useRef, useEffect, useCallback } from 'react';
import { GenerativeArtScene } from "./ui/anomalous-matter-hero";
import {
  MessageSquare,
  Clock,
  Settings as SettingsIcon,
  HelpCircle,
  ChevronDown,
  Paperclip,
  Camera,
  Send,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
  ChevronUp,
  User,
  Plus,
  Search,
  X,
  Trash2,
} from 'lucide-react';

const BACKEND_URL = 'http://127.0.0.1:8000';

interface RelatusDashboardProps {
  onLogout: () => void;
  theme?: 'dark' | 'light';
  userEmail?: string;
}

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  isSaved?: boolean;
}

interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

// ── API helpers ────────────────────────────────────────────────────────────────

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function getInitials(email: string): string {
  if (!email) return 'ME';
  const prefix = email.split('@')[0];
  const cleanPrefix = prefix.replace(/[^a-zA-Z._-]/g, '');
  const parts = cleanPrefix.split(/[._-]/);
  const validParts = parts.filter(p => p.length > 0);
  if (validParts.length >= 2) {
    return (validParts[0][0] + validParts[1][0]).toUpperCase();
  }
  return prefix.slice(0, 2).toUpperCase();
}

async function apiCreateConversation(title: string): Promise<Conversation> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to create conversation');
  }
  return res.json();
}

async function apiFetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to fetch conversations');
  }
  return res.json();
}

async function apiUpdateTitle(convId: string, title: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations/${convId}`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to update title');
  }
}

async function apiAppendMessage(convId: string, role: string, content: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations/${convId}/messages`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ role, content }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to append message');
  }
}

async function apiFetchMessages(convId: string): Promise<{ role: string; content: string; created_at: string }[]> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations/${convId}/messages`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to fetch messages');
  }
  return res.json();
}

async function apiSoftDeleteConversation(convId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/chat/conversations/${convId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.message || 'Failed to soft delete conversation');
  }
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function RelatusDashboard({ onLogout, theme = 'dark', userEmail = '' }: RelatusDashboardProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isDark = theme === 'dark';

  // ── Chat state ───────────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  // ── Conversation / history state ─────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [hoveredConvId, setHoveredConvId] = useState<string | null>(null);

  // ── UI state ─────────────────────────────────────────────────────────────────
  const [placeholderText, setPlaceholderText] = useState('Ask me anything');
  const [typedParagraph, setTypedParagraph] = useState('');
  const [paragraphDone, setParagraphDone] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchHovered, setIsSearchHovered] = useState(false);
  const [hoveredSearchItem, setHoveredSearchItem] = useState<string | null>(null);
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── Derived styling ──────────────────────────────────────────────────────────
  const bgColor = isDark ? '#000000' : '#ffffff';
  const sidebarBg = isDark ? 'rgba(15, 17, 25, 0.75)' : 'rgba(255, 255, 255, 0.65)';
  const sidebarBorder = isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.08)';
  const textColor = isDark ? '#f3f4f6' : '#1f2937';
  const textMuted = isDark ? 'rgba(255, 255, 255, 0.45)' : 'rgba(0, 0, 0, 0.45)';
  const cardBg = isDark ? 'rgba(255, 255, 255, 0.04)' : '#f9fafb';
  const cardBorder = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
  const itemHoverBg = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)';
  const activeItemBg = isDark ? 'rgba(255, 255, 255, 0.14)' : 'rgba(0, 0, 0, 0.06)';

  // User initials from email prefix (generic)
  const userInitials = getInitials(userEmail);

  // ── Fetch sidebar conversations from PostgreSQL ──────────────────────────────
  const fetchConversations = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const data = await apiFetchConversations();
      setConversations(data);
    } catch {
      // silent — user may not be authenticated yet
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  // Load conversations on mount
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // ── Typewriter: welcome paragraph (runs once at mount) ───────────────────────
  useEffect(() => {
    const startTimer = setTimeout(() => {
      const fullText = 'Not sure where to start? Get started by describing a task and Chat can do the rest.';
      let i = 0;
      const interval = setInterval(() => {
        i++;
        setTypedParagraph(fullText.slice(0, i));
        if (i >= fullText.length) {
          clearInterval(interval);
          setParagraphDone(true);
        }
      }, 30);
      return () => clearInterval(interval);
    }, 4200);
    return () => clearTimeout(startTimer);
  }, []);

  // ── Typewriter: cycling placeholder ─────────────────────────────────────────
  useEffect(() => {
    if (!paragraphDone) return;
    const fullText = 'Ask me anything';
    let i = 0;
    let intervalId: ReturnType<typeof setInterval>;
    let restartId: ReturnType<typeof setTimeout>;
    const startTyping = () => {
      setPlaceholderText('');
      i = 0;
      intervalId = setInterval(() => {
        i++;
        setPlaceholderText(fullText.slice(0, i));
        if (i >= fullText.length) {
          clearInterval(intervalId);
          restartId = setTimeout(startTyping, 2000);
        }
      }, 100);
    };
    startTyping();
    return () => {
      clearInterval(intervalId);
      clearTimeout(restartId);
    };
  }, [paragraphDone]);

  // ── Auto-collapse sidebar at 4200ms ─────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setIsCollapsed(true), 4200);
    return () => clearTimeout(t);
  }, []);

  // ── Escape to close search ───────────────────────────────────────────────────
  useEffect(() => {
    if (!isSearchOpen) return;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') setIsSearchOpen(false); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [isSearchOpen]);

  // ── Click-outside to close attach menu ──────────────────────────────────────
  useEffect(() => {
    if (!isAttachMenuOpen) return;
    const h = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (!t.closest('.attach-menu-container') && !t.closest('.attach-button')) {
        setIsAttachMenuOpen(false);
      }
    };
    document.addEventListener('click', h);
    return () => document.removeEventListener('click', h);
  }, [isAttachMenuOpen]);

  // ── Auto-scroll to bottom of chat ───────────────────────────────────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── New Chat ─────────────────────────────────────────────────────────────────
  // CORRECT behavior:
  //   1. Fetch the latest conversations from PostgreSQL (preserves the old one)
  //   2. Clear the chat window
  //   3. Unset the active conversation
  // We NEVER call setConversations([]) or filter anything out.
  const handleNewChat = useCallback(async () => {
    await fetchConversations(); // re-sync sidebar with DB — old conv stays visible
    setCurrentConversationId(null);
    setMessages([]);
    setInputText('');
  }, [fetchConversations]);

  // ── Open a previous conversation ─────────────────────────────────────────────
  const handleOpenConversation = useCallback(async (conv: Conversation) => {
    setCurrentConversationId(conv.id);
    setMessages([]); // clear while loading
    try {
      const msgs = await apiFetchMessages(conv.id);
      const mapped: Message[] = msgs.map((m, idx) => ({
        id: `${conv.id}-${idx}`,
        sender: m.role === 'user' ? 'user' : 'ai',
        text: m.content,
        timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }));
      setMessages(mapped);
    } catch {
      setMessages([]);
    }
  }, []);

  // ── Soft-delete a conversation ───────────────────────────────────────────────
  const handleDeleteConversation = useCallback(async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation(); // don't open the conversation
    await apiSoftDeleteConversation(convId);
    // If deleted the active conversation, reset the chat window
    if (convId === currentConversationId) {
      setCurrentConversationId(null);
      setMessages([]);
    }
    // Refresh sidebar — deleted conv disappears, all others stay
    await fetchConversations();
  }, [currentConversationId, fetchConversations]);

  // ── Send message with full auto-save ─────────────────────────────────────────
  const handleSend = async () => {
    if (!inputText.trim()) return;

    const queryText = inputText.trim();
    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Optimistically add user message to UI
    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: queryText,
      timestamp: nowStr,
      isSaved: false,
    };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsGenerating(true);

    const TIMEOUT_MS = 10000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const headers = getAuthHeaders();

      // ── Step 1: Ensure a conversation exists ──────────────────────────────────
      let convId = currentConversationId;
      const isFirstMessage = messages.length === 0;

      if (!convId) {
        // Generate title from first 50 chars of the user's message
        const rawTitle = queryText.slice(0, 50);
        const title = rawTitle.length < queryText.length ? rawTitle + '...' : rawTitle;
        const newConv = await apiCreateConversation(title);
        convId = newConv.id;
        setCurrentConversationId(convId);
        // Immediately add to sidebar without a full fetch (avoids flicker)
        setConversations(prev => [newConv, ...prev]);
      } else if (isFirstMessage) {
        // Conversation already exists but this is the first message in this session
        // (user loaded an old conv then somehow the messages list was empty — set title)
        const rawTitle = queryText.slice(0, 50);
        const title = rawTitle.length < queryText.length ? rawTitle + '...' : rawTitle;
        await apiUpdateTitle(convId, title);
      }

      // ── Step 2: Persist the user message ─────────────────────────────────────
      await apiAppendMessage(convId, 'user', queryText);
      setMessages(prev => prev.map(m => m.id === userMsg.id ? { ...m, isSaved: true } : m));

      // ── Step 3: Query the RAG backend ─────────────────────────────────────────
      const response = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: queryText }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      let data: any;
      try { data = await response.json(); } catch { data = {}; }

      let reply: string;
      let isSystemError = false;
      if (!response.ok) {
        reply = (data && (data.detail || data.message)) || 'Service unavailable';
        isSystemError = true;
      } else {
        reply = data.answer && data.answer.trim() ? data.answer : 'No result found';
      }

      if (!isSystemError) {
        // ── Step 4: Persist the assistant message ─────────────────────────────────
        await apiAppendMessage(convId, 'assistant', reply);
      }

      // ── Step 5: Refresh sidebar so updated_at sorts correctly ─────────────────
      await fetchConversations();

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: reply + (isSystemError ? ' — tap to retry' : ''),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, aiMsg]);

    } catch (err: any) {
      clearTimeout(timeoutId);
      const errText = err?.name === 'AbortError' ? 'Request timed out' : 'Server unavailable';
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: errText + ' — tap to retry',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, aiMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRetry = async () => {
    if (isGenerating) return;

    // Find the last user message
    const userMsgs = messages.filter(m => m.sender === 'user');
    if (userMsgs.length === 0) return;
    const lastUserMsg = userMsgs[userMsgs.length - 1];
    const queryText = lastUserMsg.text;

    // Remove the last AI error message from UI state
    setMessages(prev => {
      const lastMsg = prev[prev.length - 1];
      if (
        lastMsg &&
        lastMsg.sender === 'ai' &&
        (lastMsg.text.includes('timed out') || lastMsg.text.includes('unavailable') || lastMsg.text.includes('retry'))
      ) {
        return prev.slice(0, -1);
      }
      return prev;
    });

    setIsGenerating(true);

    const TIMEOUT_MS = 10000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const headers = getAuthHeaders();
      let convId = currentConversationId;

      if (!convId) {
        const rawTitle = queryText.slice(0, 50);
        const title = rawTitle.length < queryText.length ? rawTitle + '...' : rawTitle;
        const newConv = await apiCreateConversation(title);
        convId = newConv.id;
        setCurrentConversationId(convId);
        setConversations(prev => [newConv, ...prev]);
      }

      // Check if user message is already persisted in DB via frontend retry metadata
      if (!lastUserMsg.isSaved) {
        await apiAppendMessage(convId, 'user', queryText);
        setMessages(prev => prev.map(m => m.id === lastUserMsg.id ? { ...m, isSaved: true } : m));
      }

      // Query the RAG backend
      const response = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: queryText }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      let data: any;
      try { data = await response.json(); } catch { data = {}; }

      let reply: string;
      let isSystemError = false;
      if (!response.ok) {
        reply = (data && (data.detail || data.message)) || 'Service unavailable';
        isSystemError = true;
      } else {
        reply = data.answer && data.answer.trim() ? data.answer : 'No result found';
      }

      if (!isSystemError) {
        await apiAppendMessage(convId, 'assistant', reply);
      }

      await fetchConversations();

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: reply + (isSystemError ? ' — tap to retry' : ''),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, aiMsg]);

    } catch (err: any) {
      clearTimeout(timeoutId);
      const errText = err?.name === 'AbortError' ? 'Request timed out' : 'Server unavailable';
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: errText + ' — tap to retry',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, aiMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────
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
      transition: 'background-color 0.3s, color 0.3s',
    }}>

      {/* ── CSS injected styles ── */}
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
        .conv-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 8px;
          border-radius: 10px;
          cursor: pointer;
          transition: background 0.2s;
        }
        .conv-item:hover {
          background: ${itemHoverBg};
        }
        .conv-item.active-conv {
          background: ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.09)'};
          border: 1px solid ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'};
        }
        .conv-delete-btn {
          background: none;
          border: none;
          color: ${textMuted};
          cursor: pointer;
          padding: 4px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          opacity: 0;
          transition: opacity 0.15s, color 0.15s, background 0.15s;
          flex-shrink: 0;
        }
        .conv-item:hover .conv-delete-btn {
          opacity: 1;
        }
        .conv-delete-btn:hover {
          color: #ef4444 !important;
          background: ${isDark ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.08)'} !important;
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
          border: 1px solid ${isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)'};
          transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
          background: ${isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.15)'} !important;
          backdrop-filter: blur(24px) saturate(180%);
          -webkit-backdrop-filter: blur(24px) saturate(180%);
        }
        .input-glow-box:hover {
          border-color: ${isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)'} !important;
          box-shadow: ${isDark ? "0 0 0 1px rgba(255,255,255,0.6), 0 0 20px 4px rgba(255,255,255,0.15), 0 8px 32px rgba(255,255,255,0.06)" : "0 0 0 1px rgba(0,0,0,0.6), 0 0 20px 4px rgba(0,0,0,0.15), 0 8px 32px rgba(0,0,0,0.06)"} !important;
          transform: translateY(-3px);
        }
        .input-glow-box:focus-within {
          border-color: ${isDark ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.95)'} !important;
          box-shadow: ${isDark ? "0 0 0 1.5px rgba(255,255,255,0.7), 0 0 28px 6px rgba(255,255,255,0.18), 0 12px 40px rgba(255,255,255,0.08)" : "0 0 0 1.5px rgba(0,0,0,0.7), 0 0 28px 6px rgba(0,0,0,0.18), 0 12px 40px rgba(0,0,0,0.08)"} !important;
          transform: translateY(-3px);
        }
        .input-glow-box textarea::placeholder {
          color: darkgrey !important;
          opacity: 1 !important;
        }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'};
        }
        @keyframes floatMsg {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes sidebarGlow {
          0%, 100% { box-shadow: 4px 0 25px 2px ${isDark ? 'rgba(56, 189, 248, 0.28)' : 'rgba(0, 0, 0, 0.08)'}; }
          50%       { box-shadow: 6px 0 45px 5px ${isDark ? 'rgba(56, 189, 248, 0.48)' : 'rgba(0, 0, 0, 0.16)'}; }
        }
        @keyframes centralAnimationZoom {
          from { transform: scale(0); opacity: 0; }
          to   { transform: scale(1); opacity: 1; }
        }
        @keyframes chatbotSlideUp {
          from { transform: translateY(30px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes collapseIconIndicator {
          0%, 100% { transform: scale(1) translateX(0); box-shadow: none; background: transparent; color: ${textMuted}; }
          25%, 75%  { transform: scale(1.1) translateX(-4px); background: ${itemHoverBg}; color: ${textColor}; box-shadow: 0 0 12px 2px ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.08)'}; }
          50%       { transform: scale(1) translateX(0); background: transparent; color: ${textMuted}; box-shadow: none; }
        }
        @keyframes shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .skeleton {
          background: linear-gradient(90deg,
            ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} 25%,
            ${isDark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.08)'} 50%,
            ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} 75%
          );
          background-size: 200% 100%;
          animation: shimmer 1.4s infinite;
          border-radius: 8px;
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
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        position: 'relative',
        animation: 'sidebarGlow 5s infinite ease-in-out',
      }}>

        {/* Header: logo + search + collapse toggle */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'flex-end',
          gap: '8px',
          marginBottom: '20px',
          padding: '0 2px',
          boxSizing: 'border-box',
          width: '100%',
        }}>
          {!isCollapsed && (
            <img
              src="/watermark.png"
              alt="Reliance Retail Logo"
              style={{ height: '105px', width: 'auto', objectFit: 'contain', marginRight: 'auto', paddingLeft: '4px' }}
            />
          )}
          {!isCollapsed && (
            <button
              onClick={() => setIsSearchOpen(true)}
              onMouseEnter={() => setIsSearchHovered(true)}
              onMouseLeave={() => setIsSearchHovered(false)}
              aria-label="Search conversations"
              style={{
                background: 'none', border: 'none', color: textMuted, cursor: 'pointer',
                padding: '8px', borderRadius: '10px', display: 'flex', alignItems: 'center',
                justifyContent: 'center', transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                backgroundColor: isSearchHovered ? itemHoverBg : 'transparent',
                transform: isSearchHovered ? 'translateY(-2px) scale(1.08)' : 'scale(1)',
                boxShadow: isSearchHovered ? (isDark ? '0 0 14px 2px rgba(255,255,255,0.22)' : '0 0 14px 2px rgba(0,0,0,0.1)') : 'none',
              }}
            >
              <Search size={18} />
            </button>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            aria-label={isCollapsed ? 'Open sidebar' : 'Close sidebar'}
            style={{
              background: 'none', border: 'none', color: textMuted, cursor: 'pointer',
              padding: '8px', borderRadius: '10px', display: 'flex', alignItems: 'center',
              justifyContent: 'center', transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              animation: 'collapseIconIndicator 2s ease-in-out 2.2s 1',
            }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = itemHoverBg; e.currentTarget.style.color = textColor; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = textMuted; }}
          >
            {isCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* Glass inner container */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          background: isDark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.015)',
          border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.05)',
          borderRadius: '20px', padding: '16px 8px', boxSizing: 'border-box',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          boxShadow: isDark
            ? 'inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 32px rgba(0,0,0,0.2)'
            : 'inset 0 1px 0 rgba(255,255,255,0.4), 0 8px 32px rgba(0,0,0,0.03)',
          overflow: 'hidden',
        }}>

          {/* Nav items */}
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '20px' }}>

            {/* New Chat */}
            <div
              className={`sidebar-item ${currentConversationId === null && messages.length === 0 ? 'active' : ''}`}
              onClick={handleNewChat}
              style={{ justifyContent: isCollapsed ? 'center' : 'flex-start' }}
            >
              <Plus size={18} style={{ flexShrink: 0 }} />
              {!isCollapsed && <span>New Chat</span>}
            </div>

            {/* Recents toggle */}
            <div
              className="sidebar-item"
              onClick={() => {
                if (isCollapsed) { setIsCollapsed(false); setIsHistoryOpen(true); }
                else setIsHistoryOpen(!isHistoryOpen);
              }}
              style={{ display: 'flex', justifyContent: isCollapsed ? 'center' : 'space-between', alignItems: 'center' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Clock size={18} style={{ flexShrink: 0 }} />
                {!isCollapsed && <span>Recents</span>}
              </div>
              {!isCollapsed && (
                <ChevronDown size={14} style={{ transform: isHistoryOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s', opacity: 0.7 }} />
              )}
            </div>

            {/* History list — driven entirely by PostgreSQL */}
            {isHistoryOpen && !isCollapsed && (
              <div style={{
                display: 'flex', flexDirection: 'column', gap: '2px',
                paddingLeft: '6px', marginTop: '4px',
                borderLeft: `1.5px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'}`,
                animation: 'floatMsg 0.25s ease', marginBottom: '10px',
                maxHeight: '340px', overflowY: 'auto',
              }} className="custom-scrollbar">

                {isLoadingHistory ? (
                  // Skeleton shimmer while loading
                  [1, 2, 3].map(i => (
                    <div key={i} className="skeleton" style={{ height: '32px', margin: '2px 4px' }} />
                  ))
                ) : conversations.length === 0 ? (
                  <div style={{ padding: '8px 12px', fontSize: '12px', color: textMuted, fontStyle: 'italic', userSelect: 'none' }}>
                    No recent chats
                  </div>
                ) : (
                  conversations.map(conv => (
                    <div
                      key={conv.id}
                      className={`conv-item ${conv.id === currentConversationId ? 'active-conv' : ''}`}
                      onClick={() => handleOpenConversation(conv)}
                      title={conv.title}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                        <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.7, color: conv.id === currentConversationId ? textColor : textMuted }} />
                        <span style={{
                          fontSize: '12px',
                          fontWeight: conv.id === currentConversationId ? 600 : 400,
                          color: conv.id === currentConversationId ? textColor : textMuted,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {conv.title.length > 28 ? conv.title.slice(0, 28) + '…' : conv.title}
                        </span>
                      </div>
                      <button
                        className="conv-delete-btn"
                        onClick={(e) => handleDeleteConversation(e, conv.id)}
                        title="Delete conversation"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </nav>

          {/* Scrollable area with Settings / Help */}
          <div className="custom-scrollbar" style={{
            flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
            gap: '18px', marginBottom: '20px', boxSizing: 'border-box',
          }}>
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

          {/* Profile / Account */}
          <div style={{ position: 'relative' }}>
            <div
              className="sidebar-item"
              onClick={() => setShowProfileMenu(!showProfileMenu)}
              style={{
                padding: isCollapsed ? '10px' : '10px 14px',
                justifyContent: isCollapsed ? 'center' : 'space-between',
                background: showProfileMenu ? activeItemBg : undefined,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '18px', height: '18px', borderRadius: '50%',
                  background: 'linear-gradient(135deg, #f472b6, #ec4899)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: '7px', fontWeight: 700, flexShrink: 0,
                }}>{userInitials}</div>
                {!isCollapsed && <span>My Account</span>}
              </div>
              {!isCollapsed && (
                <div style={{ color: textMuted, display: 'flex', alignItems: 'center' }}>
                  {showProfileMenu ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </div>
              )}
            </div>

            {showProfileMenu && (
              <div style={{
                position: 'absolute', bottom: '100%', left: 0, marginBottom: '6px',
                width: '200px', background: isDark ? '#1e2230' : '#ffffff',
                border: `1px solid ${sidebarBorder}`, borderRadius: '12px',
                padding: '6px', overflow: 'hidden',
                boxShadow: '0 -10px 25px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05)',
                zIndex: 100, animation: 'floatMsg 0.2s ease',
              }}>
                <div className="sidebar-item" onClick={() => { setShowProfileMenu(false); }} style={{ fontSize: '13px', padding: '8px 12px' }}>
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
        flex: 1, display: 'flex', flexDirection: 'column', height: '100%',
        position: 'relative', zIndex: 1, boxSizing: 'border-box',
      }}>

        {/* Messages / Welcome screen */}
        <div className="custom-scrollbar" style={{
          flex: 1, overflowY: 'auto', padding: '40px 8% 24px 8%',
          display: 'flex', flexDirection: 'column', boxSizing: 'border-box',
          position: 'relative', zIndex: 2,
        }}>
          {messages.length === 0 ? (
            /* Welcome screen */
            <div style={{
              margin: 'auto', maxWidth: '860px', width: '100%',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              textAlign: 'center', paddingBottom: '20px',
            }}>
              <div className="chatbot-avatar" style={{
                width: '300px', height: '300px', position: 'relative',
                marginBottom: '28px', borderRadius: '50%', overflow: 'hidden',
                boxShadow: isDark
                  ? '0 0 50px rgba(56,189,248,0.2), inset 0 0 30px rgba(56,189,248,0.15)'
                  : '0 0 35px rgba(30,58,138,0.08), inset 0 0 25px rgba(30,58,138,0.05)',
                border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.05)',
                background: isDark ? '#111' : '#f9f9f9',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 10,
                animation: 'centralAnimationZoom 1.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
              }}>
                <GenerativeArtScene />
              </div>

              <p style={{
                fontSize: '16px', color: textColor, maxWidth: '600px',
                lineHeight: 1.6, marginBottom: '48px', marginTop: '0',
                position: 'relative', zIndex: 10, opacity: 0,
                animation: 'chatbotSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.1s forwards',
              }}>
                {typedParagraph || '\u00a0'}
              </p>
            </div>
          ) : (
            /* Chat messages list */
            <div style={{ maxWidth: '860px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {messages.map(msg => (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex', gap: '16px', alignItems: 'flex-start',
                    animation: 'floatMsg 0.3s ease',
                    alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row',
                  }}
                >
                  {/* Avatar */}
                  {msg.sender === 'user' ? (
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '50%',
                      backgroundColor: '#ec4899', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      color: '#ffffff', fontWeight: 700, fontSize: '12px', flexShrink: 0,
                    }}>{userInitials}</div>
                  ) : (
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '50%',
                      backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      <svg width="20" height="20" viewBox="0 0 40 40" fill="none">
                        <rect x="6" y="6" width="13" height="13" rx="4" fill="#78c257" transform="rotate(-15 6 6)" opacity="0.9" />
                        <rect x="21" y="6" width="13" height="13" rx="4" fill="#ffb020" transform="rotate(15 21 6)" opacity="0.9" />
                        <rect x="6" y="21" width="13" height="13" rx="4" fill="#14b8a6" transform="rotate(15 6 21)" opacity="0.9" />
                        <rect x="21" y="21" width="13" height="13" rx="4" fill="#ec4899" transform="rotate(-15 21 21)" opacity="0.9" />
                      </svg>
                    </div>
                  )}

                  {/* Bubble */}
                  <div 
                    onClick={() => {
                      if (msg.sender === 'ai' && msg.text.includes('retry')) {
                        handleRetry();
                      }
                    }}
                    style={{
                      padding: '12px 18px',
                      borderRadius: msg.sender === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                      backgroundColor: msg.sender === 'user' ? '#007AFF' : (isDark ? '#333333' : '#E9E9EB'),
                      color: msg.sender === 'user' ? '#FFFFFF' : (isDark ? '#FFFFFF' : '#000000'),
                      fontSize: '15px', lineHeight: 1.4, whiteSpace: 'pre-wrap',
                      cursor: (msg.sender === 'ai' && msg.text.includes('retry')) ? 'pointer' : 'default',
                      border: (msg.sender === 'ai' && msg.text.includes('retry')) ? '1px dashed #ef4444' : undefined,
                    }}
                  >
                    {msg.text}
                    <div style={{ fontSize: '10px', color: msg.sender === 'user' ? 'rgba(255,255,255,0.7)' : textMuted, textAlign: 'right', marginTop: '6px' }}>
                      {msg.timestamp}
                    </div>
                  </div>
                </div>
              ))}

              {isGenerating && (
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center', alignSelf: 'flex-start' }}>
                  <div style={{
                    width: '36px', height: '36px', borderRadius: '50%',
                    backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <svg width="20" height="20" viewBox="0 0 40 40" fill="none">
                      <rect x="6" y="6" width="13" height="13" rx="4" fill="#78c257" />
                    </svg>
                  </div>
                  <span style={{ fontSize: '14px', color: textMuted }}>Relatus is thinking…</span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input & footer */}
        <div style={{
          padding: '0 8% 24px 8%', display: 'flex', flexDirection: 'column',
          alignItems: 'center', boxSizing: 'border-box', position: 'relative', zIndex: 2,
          opacity: 0, animation: 'chatbotSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.3s forwards',
        }}>
          <div className="input-glow-box" style={{
            maxWidth: '860px', width: '100%', backgroundColor: 'transparent',
            borderRadius: '20px', padding: '16px 20px', boxSizing: 'border-box',
            display: 'flex', flexDirection: 'column', gap: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <textarea
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholderText}
                rows={1}
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  color: textColor, fontSize: '15px', fontFamily: 'inherit',
                  resize: 'none', lineHeight: '22px', maxHeight: '120px',
                  boxSizing: 'border-box', padding: '4px 0',
                }}
              />
              <button
                onClick={handleSend}
                disabled={!inputText.trim() || isGenerating}
                style={{
                  width: '38px', height: '38px', borderRadius: '50%',
                  border: '2px solid #fff',
                  background: inputText.trim() && !isGenerating ? '#78c257' : (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'),
                  color: inputText.trim() && !isGenerating ? '#ffffff' : textMuted,
                  cursor: inputText.trim() && !isGenerating ? 'pointer' : 'default',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.2s',
                  boxShadow: inputText.trim() ? '0 0 8px rgba(255,255,255,0.6), 0 4px 12px rgba(120,194,87,0.35)' : '0 0 8px rgba(255,255,255,0.6)',
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
              >
                <Send size={16} />
              </button>
            </div>

            {/* Bottom row */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              paddingTop: '8px',
              borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)'}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' }}>
                <button
                  className="attach-button"
                  onClick={() => setIsAttachMenuOpen(!isAttachMenuOpen)}
                  style={{
                    background: 'none', border: 'none', color: textMuted, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px',
                    fontWeight: 500, padding: '4px 8px', borderRadius: '6px', transition: 'background 0.2s, color 0.2s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = itemHoverBg; e.currentTarget.style.color = textColor; }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = textMuted; }}
                >
                  <Paperclip size={14} /> Attach
                </button>

                {isAttachMenuOpen && (
                  <div className="attach-menu-container" style={{
                    position: 'absolute', bottom: 'calc(100% + 12px)', left: '0', width: '280px',
                    backgroundColor: isDark ? '#1e1e1e' : '#ffffff',
                    border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                    borderRadius: '14px', padding: '6px', boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                    zIndex: 100, display: 'flex', flexDirection: 'column', gap: '2px',
                    animation: 'floatMsg 0.18s ease',
                  }}>
                    {[
                      { icon: <Paperclip size={16} style={{ opacity: 0.8 }} />, label: 'Add files or photos', shortcut: '⌘U' },
                      { icon: <Camera size={16} style={{ opacity: 0.8 }} />, label: 'Take a screenshot', shortcut: '' },
                    ].map(item => (
                      <div
                        key={item.label}
                        onClick={() => { setIsAttachMenuOpen(false); }}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '10px 14px', borderRadius: '10px', cursor: 'pointer',
                          color: textColor, fontSize: '14px', fontWeight: 500,
                          transition: 'background 0.2s', userSelect: 'none',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.backgroundColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)'; }}
                        onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>{item.icon}<span>{item.label}</span></div>
                        {item.shortcut && <span style={{ fontSize: '12px', color: textMuted, fontWeight: 400 }}>{item.shortcut}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ fontSize: '12px', color: textMuted, fontWeight: 500 }}>
                {inputText.length}/1,500
              </div>
            </div>
          </div>

          <div style={{ fontSize: '12px', color: textMuted, marginTop: '12px', textAlign: 'center', lineHeight: 1.5 }}>
            Relatus may display inaccurate info, so please double check the response.{' '}
            <span style={{ fontWeight: 600, color: textColor, cursor: 'pointer', textDecoration: 'underline' }}>Your Privacy &amp; Relatus.AI</span>
          </div>
        </div>
      </main>

      {/* ─────────────────── SEARCH MODAL ─────────────────── */}
      {isSearchOpen && (
        <>
          <div
            onClick={() => setIsSearchOpen(false)}
            style={{
              position: 'fixed', inset: 0,
              background: isDark ? 'rgba(0,0,0,0.65)' : 'rgba(255,255,255,0.45)',
              backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
              zIndex: 10000,
            }}
          />
          <div style={{
            position: 'fixed', inset: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'center', zIndex: 10001, pointerEvents: 'none',
          }}>
            <div style={{
              pointerEvents: 'auto', width: '90%', maxWidth: '640px',
              backgroundColor: isDark ? 'rgba(30,30,30,0.92)' : 'rgba(255,255,255,0.92)',
              backdropFilter: 'blur(30px) saturate(180%)',
              WebkitBackdropFilter: 'blur(30px) saturate(180%)',
              border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
              borderRadius: '16px',
              boxShadow: isDark ? '0 24px 64px rgba(0,0,0,0.75)' : '0 24px 64px rgba(0,0,0,0.12)',
              color: textColor, fontFamily: "'Inter', sans-serif",
              overflow: 'hidden', boxSizing: 'border-box',
              animation: 'floatMsg 0.25s ease-out forwards',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', padding: '16px 20px', gap: '14px' }}>
                <Search size={20} style={{ color: textMuted, flexShrink: 0 }} />
                <input
                  type="text"
                  autoFocus
                  placeholder="Search conversations"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  style={{
                    flex: 1, background: 'none', border: 'none', outline: 'none',
                    color: textColor, fontSize: '16px', fontFamily: 'inherit', padding: '4px 0',
                  }}
                />
                <button
                  onClick={() => setIsSearchOpen(false)}
                  style={{
                    background: 'none', border: 'none', color: textMuted, cursor: 'pointer',
                    padding: '6px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'; e.currentTarget.style.color = textColor; }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = textMuted; }}
                >
                  <X size={18} />
                </button>
              </div>

              <div style={{ height: '1px', backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }} />

              <div style={{ padding: '8px', maxHeight: '340px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {conversations
                  .filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase()))
                  .map((conv, idx) => {
                    const isHovered = hoveredSearchItem === conv.id;
                    const isActive = isHovered || (hoveredSearchItem === null && idx === 0);
                    return (
                      <div
                        key={conv.id}
                        onMouseEnter={() => setHoveredSearchItem(conv.id)}
                        onMouseLeave={() => setHoveredSearchItem(null)}
                        onClick={() => { setIsSearchOpen(false); handleOpenConversation(conv); }}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '12px 16px', borderRadius: '10px', cursor: 'pointer',
                          backgroundColor: isActive ? (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)') : 'transparent',
                          transition: 'background-color 0.15s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: 0 }}>
                          <MessageSquare size={16} style={{ color: isActive ? textColor : textMuted, opacity: isActive ? 0.9 : 0.6, flexShrink: 0 }} />
                          <span style={{
                            fontSize: '14.5px', fontWeight: isActive ? 600 : 400, color: textColor,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>{conv.title}</span>
                        </div>
                        {isActive && <span style={{ fontSize: '15px', color: textMuted, opacity: 0.8 }}>&#8629;</span>}
                      </div>
                    );
                  })}
                {conversations.filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase())).length === 0 && (
                  <div style={{ padding: '20px', textAlign: 'center', color: textMuted, fontSize: '14px' }}>
                    No conversations found
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

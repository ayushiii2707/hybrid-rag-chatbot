import { useRef, useState, useEffect, useCallback } from "react";
import ThreeScene from "./components/ThreeScene";
import {
  Section2,
} from "./components/ContentSections";
import WebGLErrorBoundary from "./components/WebGLErrorBoundary";
import RelatusDashboard from "./components/RelatusDashboard";
import ThemeToggle, { type ThemeMode } from "./components/ThemeToggle";

const TOTAL_HEIGHT = 180;

function parseJwt(token: string) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window.atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

export default function App() {
  const scrollRef = useRef(0);
  const [scroll, setScroll] = useState(0);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [theme, setTheme] = useState<ThemeMode>('light');

  const onScroll = useCallback(() => {
    const el = document.documentElement;
    const scrollMax = el.scrollHeight - el.clientHeight;
    const progress = scrollMax > 0 ? el.scrollTop / scrollMax : 0;
    scrollRef.current = progress;
    setScroll(progress);
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  // Session recovery on startup
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      const payload = parseJwt(token);
      if (payload && payload.exp * 1000 > Date.now()) {
        setUserEmail(payload.email || '');
        setIsLoggedIn(true);
      } else {
        localStorage.removeItem('access_token');
        setIsLoggedIn(false);
        setUserEmail('');
      }
    }
  }, []);

  const [typewriterDone, setTypewriterDone] = useState(false);

  // Auto demonstration of theme switching after the toggle button wiggle concludes (at 3000ms)
  useEffect(() => {
    if (!typewriterDone) return;
    
    // Switch to dark mode at 3.0s
    const darkTimer = setTimeout(() => {
      setTheme('dark');
    }, 3000);

    // Switch back to light mode at 4.5s
    const lightTimer = setTimeout(() => {
      setTheme('light');
    }, 4500);

    return () => {
      clearTimeout(darkTimer);
      clearTimeout(lightTimer);
    };
  }, [typewriterDone]);

  if (isLoggedIn) {
    return (
      <RelatusDashboard
        onLogout={() => {
          localStorage.removeItem('access_token');
          setIsLoggedIn(false);
          setUserEmail('');
        }}
        theme={theme}
        userEmail={userEmail}
      />
    );
  }

  return (
    <>
      {/* Scroll container that creates the scroll height */}
      <div
        style={{
          height: `${TOTAL_HEIGHT}vh`,
          width: "100%",
          position: "relative",
        }}
      />

      {/* Fixed 3D scene */}
      <WebGLErrorBoundary>
        <ThreeScene scrollRef={scrollRef} theme={theme} />
      </WebGLErrorBoundary>

      {/* Light mode gradient background — white→lightgrey→darkgrey→black from top to bottom */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          opacity: theme === 'light' ? 1 : 0,
          transition: "opacity 0.8s ease",
          background: "linear-gradient(to bottom, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.93) 65%, rgba(220,220,220,0.85) 100%)",
        }}
      />

      {/* Zooming white background on initial load */}
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          width: "200vmax",
          height: "200vmax",
          background: "#ffffff",
          zIndex: 99,
          transformOrigin: "center center",
          transform: "translate(-50%, -50%)",
          pointerEvents: "none",
          animation: "bgZoomOut 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards, bgFadeOut 0.8s ease 1.2s forwards",
        }}
      />

      {/* Watermark Logo at Top-Left Corner */}
      <div
        style={{
          position: "fixed",
          top: "0px",
          left: "24px",
          zIndex: 100,
          pointerEvents: "none",
          opacity: 0,
          animation: "logoFadeIn 0.8s ease 1.2s forwards",
        }}
      >
        <img
          src="/watermark.png"
          alt="Watermark Logo"
          style={{
            height: "140px",
            width: "auto",
            objectFit: "contain",
          }}
        />
      </div>

      <Section2 
        scroll={scroll} 
        onLoginSuccess={() => {
          const token = localStorage.getItem('access_token');
          if (token) {
            const payload = parseJwt(token);
            if (payload && payload.email) {
              setUserEmail(payload.email);
            }
          }
          setIsLoggedIn(true);
        }} 
        theme={theme} 
        onTypewriterComplete={setTypewriterDone}
      />

      {/* Theme toggle button — bottom right */}
      <ThemeToggle onThemeChange={setTheme} show={typewriterDone} delay={100} currentTheme={theme} />
    </>
  );
}

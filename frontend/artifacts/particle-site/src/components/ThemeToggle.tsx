import { useState, useEffect } from 'react';

export type ThemeMode = 'dark' | 'light';

interface ThemeToggleProps {
  onThemeChange: (mode: ThemeMode) => void;
  show: boolean;
  delay?: number;
  currentTheme?: ThemeMode;
}

export default function ThemeToggle({ onThemeChange, show, delay = 0, currentTheme }: ThemeToggleProps) {
  const [mode, setMode] = useState<ThemeMode>('light');
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    if (currentTheme) {
      setMode(currentTheme);
    }
  }, [currentTheme]);

  const toggle = () => {
    const next = mode === 'dark' ? 'light' : 'dark';
    setMode(next);
    onThemeChange(next);
  };

  // Sun icon (for switching TO light mode — shown when in dark mode)
  const sunIcon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );

  // Moon icon (for switching TO dark mode — shown when in light mode)
  const moonIcon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes toggleIndicator {
          0%, 100% {
            transform: translateY(0) scale(1);
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
          }
          25% {
            transform: translateY(-10px) scale(1.05);
            box-shadow: ${mode === 'dark' 
              ? '0 0 20px 6px rgba(255,255,255,0.25), 0 0 40px 12px rgba(255,255,255,0.1)' 
              : '0 0 20px 6px rgba(0,0,0,0.15), 0 0 40px 12px rgba(0,0,0,0.06)'};
          }
          50% {
            transform: translateY(0) scale(1);
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
          }
          75% {
            transform: translateY(-5px) scale(1.03);
            box-shadow: ${mode === 'dark' 
              ? '0 0 16px 4px rgba(255,255,255,0.2)' 
              : '0 0 16px 4px rgba(0,0,0,0.1)'};
          }
        }
      `}} />
      <button
        onClick={toggle}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-label={`Switch to ${mode === 'dark' ? 'light' : 'dark'} mode`}
        style={{
          position: 'fixed',
          bottom: '28px',
          right: '28px',
          zIndex: 9999,
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          border: mode === 'dark'
            ? '1px solid rgba(255,255,255,0.2)'
            : '1px solid rgba(0,0,0,0.15)',
          background: mode === 'dark'
            ? `rgba(255,255,255,${hovered ? 0.15 : 0.08})`
            : `rgba(0,0,0,${hovered ? 0.12 : 0.06})`,
          color: mode === 'dark' ? '#ffffff' : '#1a1a1a',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          boxShadow: hovered
            ? (mode === 'dark'
              ? '0 0 20px 6px rgba(255,255,255,0.25), 0 0 40px 12px rgba(255,255,255,0.1)'
              : '0 0 20px 6px rgba(0,0,0,0.15), 0 0 40px 12px rgba(0,0,0,0.06)')
            : '0 2px 10px rgba(0,0,0,0.2)',
          
          // Pop up animations:
          opacity: show ? 1 : 0,
          pointerEvents: show ? 'auto' : 'none',
          transform: show 
            ? (hovered ? 'translateY(0) scale(1.1)' : 'translateY(0) scale(1)') 
            : 'translateY(60px) scale(0.92)',
          animation: show ? 'toggleIndicator 1.5s ease-in-out 1.5s 1' : 'none',
          transition: `opacity 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}ms, transform 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}ms, background 0.3s, border-color 0.3s, color 0.3s, box-shadow 0.3s`,
        }}
      >
        {mode === 'dark' ? sunIcon : moonIcon}
      </button>
    </>
  );
}

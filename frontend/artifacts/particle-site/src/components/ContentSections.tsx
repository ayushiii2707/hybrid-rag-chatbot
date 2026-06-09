import { useEffect, useRef, useState } from 'react';
import NexusGateModal from './NexusGateModal';

function useTypewriter(text: string, active: boolean, speed = 38, delay = 0, resetTrigger?: any) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!active) { setDisplayed(''); setDone(false); return; }
    let i = 0;
    setDisplayed('');
    setDone(false);
    
    let interval: any;
    const timeout = setTimeout(() => {
      interval = setInterval(() => {
        i++;
        setDisplayed(text.slice(0, i));
        if (i >= text.length) { clearInterval(interval); setDone(true); }
      }, speed);
    }, delay);

    return () => {
      clearTimeout(timeout);
      if (interval) clearInterval(interval);
    };
  }, [active, text, speed, delay, resetTrigger]);
  return { displayed, done };
}

function FadeIn({ children, show, delay = 0 }: { children: React.ReactNode; show: boolean; delay?: number }) {
  return (
    <div style={{
      opacity: show ? 1 : 0,
      transform: show ? 'translateY(0)' : 'translateY(18px)',
      transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
    }}>
      {children}
    </div>
  );
}

function PopUpButton({ children, show, delay = 0 }: { children: React.ReactNode; show: boolean; delay?: number }) {
  return (
    <div style={{
      opacity: show ? 1 : 0,
      transform: show ? 'translateY(0) scale(1)' : 'translateY(60px) scale(0.92)',
      transition: `opacity 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}ms, transform 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}ms`,
    }}>
      {children}
    </div>
  );
}

const buttonBase: React.CSSProperties = {
  border: '1px solid rgba(255,255,255,0.28)',
  borderRadius: '100px',
  cursor: 'pointer',
  fontFamily: 'inherit',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  transition: 'background 0.2s, border-color 0.2s',
  letterSpacing: '-0.01em',
};

const primaryBtn: React.CSSProperties = {
  ...buttonBase,
  background: 'rgba(255,255,255,0.12)',
  color: '#fff',
  fontSize: '18px',
  fontWeight: 500,
  padding: '16px 36px',
};

export function Section2({ 
  scroll, 
  onLoginSuccess, 
  theme = 'dark', 
  onTypewriterComplete 
}: { 
  scroll: number; 
  onLoginSuccess: () => void; 
  theme?: 'dark' | 'light';
  onTypewriterComplete?: (done: boolean) => void;
}) {
  const visible = true; // Always visible on the landing page
  const heading = 'Everything revolves around one thing — your convenience';
  const { displayed, done } = useTypewriter(heading, visible, 30, 1200);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    onTypewriterComplete?.(done);
  }, [done, onTypewriterComplete]);

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      pointerEvents: visible ? 'auto' : 'none',
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.6s ease',
      zIndex: 10,
      padding: '0 8% 0 8%',
    }}>
      <div style={{ flex: 1, maxWidth: '52%' }}>
        <h2 style={{
          fontSize: 'clamp(28px, 4vw, 56px)',
          fontWeight: 700,
          color: theme === 'light' ? '#000000' : '#ffffff',
          lineHeight: 1.1,
          letterSpacing: '-0.035em',
          margin: 0,
          minHeight: '3.3em',
          transition: 'color 0.8s ease',
        }}>
          {displayed}
        </h2>
      </div>

      <div style={{ flex: 1, maxWidth: '36%', marginLeft: '8%' }}>
        <FadeIn show={visible} delay={1700}>
          <p style={{
            fontSize: '14.5px',
            color: theme === 'light' ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.55)',
            lineHeight: 1.7,
            margin: '0 0 68px 0',
            fontWeight: 400,
            transition: 'color 0.8s ease',
          }}>
            Thousands of data points. One centre of gravity. We turn the noise of information into a focused point of energy for your query.
          </p>
        </FadeIn>
        
        {/* Button animation triggers exactly when the typewriter effect completes */}
        <PopUpButton show={done} delay={700}>
          <style dangerouslySetInnerHTML={{ __html: `
            @keyframes buttonAttentionWiggle {
              0%, 100% {
                transform: translateY(0) scale(1);
              }
              25% {
                transform: translateY(-10px) scale(1.03);
              }
              50% {
                transform: translateY(0) scale(1);
              }
              75% {
                transform: translateY(-5px) scale(1.015);
              }
            }
          `}} />
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button 
              onClick={() => setIsModalOpen(true)}
              style={{
                ...primaryBtn,
                animation: done ? 'buttonAttentionWiggle 1.5s ease-in-out 4.5s 1' : 'none',
                ...(theme === 'light' ? {
                  background: 'rgba(0,0,0,0.1)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  border: '1px solid rgba(0,0,0,0.2)',
                  color: '#000000',
                  transition: 'background 0.3s, border-color 0.3s, color 0.8s, transform 0.3s',
                } : {
                  transition: 'background 0.2s, border-color 0.2s, transform 0.3s',
                }),
              }}
            >
              Let's get started!
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2.5 6.5h8M7.5 3.5l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </PopUpButton>
      </div>

      {/* Glassmorphic Login Modal overlay */}
      <NexusGateModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onSuccess={onLoginSuccess} theme={theme} />
    </div>
  );
}

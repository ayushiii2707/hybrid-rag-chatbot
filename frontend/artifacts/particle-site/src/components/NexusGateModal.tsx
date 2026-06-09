import { useState, useEffect } from 'react';

interface NexusGateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  theme?: 'dark' | 'light';
}

// ─── Shared design tokens ────────────────────────────────────────────────────
const ROLES = [
  'Product Designer',
  'Software Engineer',
  'Data Analyst',
  'Marketing Manager',
  'Sales Executive',
  'Operations Lead',
  'Other',
];

// ─── Reusable pill input style factory ───────────────────────────────────────
function inputStyle(focused: boolean, theme: 'dark' | 'light', extra?: React.CSSProperties): React.CSSProperties {
  return {
    width: '100%',
    padding: '12px 16px',
    background: theme === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
    border: focused
      ? (theme === 'dark' ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(0,0,0,0.35)')
      : (theme === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)'),
    borderRadius: '100px',
    color: theme === 'dark' ? '#fff' : '#000',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box' as const,
    transition: 'border-color 0.2s, background 0.2s, color 0.2s',
    ...extra,
  };
}

const BACKEND_URL = 'http://127.0.0.1:8000';

export default function NexusGateModal({ isOpen, onClose, onSuccess, theme = 'dark' }: NexusGateModalProps) {
  // ─── Shared state ────────────────────────────────────────────────────────
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [view, setView] = useState<'login' | 'signup' | 'forgot' | 'otp_verify' | 'update_password' | 'welcome_screen'>('login');

  // ─── Login state ─────────────────────────────────────────────────────────
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [isRemembered, setIsRemembered] = useState(false);
  const [isSwitchHovered, setIsSwitchHovered] = useState(false);
  const [loginEmailFocused, setLoginEmailFocused] = useState(false);
  const [loginPassFocused, setLoginPassFocused] = useState(false);

  // ─── Signup state ────────────────────────────────────────────────────────
  const [role, setRole] = useState('Product Designer');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [firstNameFocused, setFirstNameFocused] = useState(false);
  const [lastNameFocused, setLastNameFocused] = useState(false);
  const [usernameFocused, setUsernameFocused] = useState(false);
  const [signupEmailFocused, setSignupEmailFocused] = useState(false);
  const [signupPassFocused, setSignupPassFocused] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [showOtpPopup, setShowOtpPopup] = useState(false);
  const [isOtpVerified, setIsOtpVerified] = useState(false);
  const [isOtpVerifying, setIsOtpVerifying] = useState(false);
  const [otpSuccess, setOtpSuccess] = useState(false);
  const [showOtpCard, setShowOtpCard] = useState(false);
  const [otpCode, setOtpCode] = useState(['', '', '', '']);
  const [timer, setTimer] = useState(49);
  const [signupConfirmPassword, setSignupConfirmPassword] = useState('');
  const [showSignupConfirmPassword, setShowSignupConfirmPassword] = useState(false);
  const [confirmPassFocused, setConfirmPassFocused] = useState(false);

  // ─── Forgot password state ─────────────────────────────────────────
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotEmailFocused, setForgotEmailFocused] = useState(false);
  const [forgotOtpCode, setForgotOtpCode] = useState(['', '', '', '', '', '']);
  const [isForgotOtpVerifying, setIsForgotOtpVerifying] = useState(false);
  const [forgotOtpSuccess, setForgotOtpSuccess] = useState(false);

  // ─── Update password state ─────────────────────────────────────────
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmNewPassword, setShowConfirmNewPassword] = useState(false);
  const [newPasswordFocused, setNewPasswordFocused] = useState(false);
  const [confirmNewPasswordFocused, setConfirmNewPasswordFocused] = useState(false);

  // ─── Welcome screen typewriter state ─────────────────────────────────────
  const [typedTitle, setTypedTitle] = useState('');
  const [typedSubtitle, setTypedSubtitle] = useState('');

  // ─── Derived password strength metrics ───────────────────────────────────
  const hasMinLength = signupPassword.length >= 8;
  const [hasNumber, hasLowercase, hasUppercase, hasSpecialChar] = [
    /\d/.test(signupPassword),
    /[a-z]/.test(signupPassword),
    /[A-Z]/.test(signupPassword),
    /[^a-zA-Z0-9\s]/.test(signupPassword)
  ];
  const metCount = [hasMinLength, hasNumber, hasLowercase, hasUppercase, hasSpecialChar].filter(Boolean).length;
  const passwordsMatch = signupPassword !== '' && signupPassword === signupConfirmPassword;

  // ─── Derived update password strength metrics ────────────────────────────
  const newHasMinLength = newPassword.length >= 8;
  const [newHasNumber, newHasLowercase, newHasUppercase, newHasSpecialChar] = [
    /\d/.test(newPassword),
    /[a-z]/.test(newPassword),
    /[A-Z]/.test(newPassword),
    /[^a-zA-Z0-9\s]/.test(newPassword)
  ];
  const newMetCount = [newHasMinLength, newHasNumber, newHasLowercase, newHasUppercase, newHasSpecialChar].filter(Boolean).length;
  const newPasswordsMatch = newPassword !== '' && newPassword === confirmNewPassword;
  const isForgotEmailValid = forgotEmail.includes('@');

  // ─── Escape key ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Reset view when modal closes
  useEffect(() => {
    if (!isOpen) {
      setView('login');
      setShowOtpPopup(false);
      setShowOtpCard(false);
      setIsOtpVerified(false);
      setIsOtpVerifying(false);
      setOtpSuccess(false);
      setOtpCode(['', '', '', '']);
      setTimer(49);
      setSignupConfirmPassword('');
      setShowSignupConfirmPassword(false);
      setConfirmPassFocused(false);
      setForgotEmail('');
      setForgotEmailFocused(false);
      setForgotOtpCode(['', '', '', '', '', '']);
      setIsForgotOtpVerifying(false);
      setForgotOtpSuccess(false);
      setNewPassword('');
      setConfirmNewPassword('');
      setShowNewPassword(false);
      setShowConfirmNewPassword(false);
      setNewPasswordFocused(false);
      setConfirmNewPasswordFocused(false);
      setTypedTitle('');
      setTypedSubtitle('');
      setAuthError('');
      setAuthLoading(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (metCount < 5 && signupConfirmPassword !== '') {
      setSignupConfirmPassword('');
    }
  }, [metCount, signupConfirmPassword]);

  useEffect(() => {
    if (newMetCount < 5 && confirmNewPassword !== '') {
      setConfirmNewPassword('');
    }
  }, [newMetCount, confirmNewPassword]);

  useEffect(() => {
    if (view !== 'welcome_screen') {
      setTypedTitle('');
      setTypedSubtitle('');
      return;
    }

    const titleText = 'Welcome';
    const subtitleText = 'Experience the future of digital interaction with our premium platform';
    
    let currentTitle = '';
    let currentSubtitle = '';
    let titleIdx = 0;
    let subtitleIdx = 0;

    const titleInterval = setInterval(() => {
      if (titleIdx < titleText.length) {
        currentTitle += titleText[titleIdx];
        setTypedTitle(currentTitle);
        titleIdx++;
      } else {
        clearInterval(titleInterval);
        
        const subtitleInterval = setInterval(() => {
          if (subtitleIdx < subtitleText.length) {
            currentSubtitle += subtitleText[subtitleIdx];
            setTypedSubtitle(currentSubtitle);
            subtitleIdx++;
          } else {
            clearInterval(subtitleInterval);
          }
        }, 30);
      }
    }, 100);

    return () => {
      clearInterval(titleInterval);
    };
  }, [view]);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(data.detail || data.message || 'Login failed');
        setAuthLoading(false);
        return;
      }
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
      }
      setAuthLoading(false);
      setView('welcome_screen');
    } catch {
      setAuthError('Server unavailable');
      setAuthLoading(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreeTerms) return;
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: signupEmail, password: signupPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(data.detail || data.message || 'Registration failed');
        setAuthLoading(false);
        return;
      }
      setAuthLoading(false);
      setView('welcome_screen');
    } catch {
      setAuthError('Server unavailable');
      setAuthLoading(false);
    }
  };

  const handleWelcomeRedirect = () => {
    onClose();
    onSuccess();
  };

  const handleForgotSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Forgot Password:', { forgotEmail });
    setView('otp_verify');
  };

  const handleForgotOtpChange = (index: number, val: string) => {
    if (isNaN(Number(val))) return;
    const newOtp = [...forgotOtpCode];
    newOtp[index] = val.slice(-1);
    setForgotOtpCode(newOtp);
    if (val && index < 5) {
      const nextInput = document.getElementById(`forgot-otp-input-${index + 1}`);
      if (nextInput) (nextInput as HTMLInputElement).focus();
    }
  };

  const handleForgotOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !forgotOtpCode[index] && index > 0) {
      const prevInput = document.getElementById(`forgot-otp-input-${index - 1}`);
      if (prevInput) {
        (prevInput as HTMLInputElement).focus();
        const newOtp = [...forgotOtpCode];
        newOtp[index - 1] = '';
        setForgotOtpCode(newOtp);
      }
    }
  };

  const handleForgotOtpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isForgotOtpVerifying || forgotOtpSuccess) return;
    setIsForgotOtpVerifying(true);
    setTimeout(() => {
      setIsForgotOtpVerifying(false);
      setForgotOtpSuccess(true);
      setTimeout(() => {
        console.log('Forgot Password OTP Verified:', forgotOtpCode.join(''));
        setView('update_password');
        setForgotOtpSuccess(false);
      }, 800);
    }, 1200);
  };

  const handleUpdatePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Password Updated Successfully:', { newPassword });
    setView('login');
    setNewPassword('');
    setConfirmNewPassword('');
    setShowNewPassword(false);
    setShowConfirmNewPassword(false);
  };

  const handleOtpChange = (index: number, val: string) => {
    if (isNaN(Number(val))) return;
    const newOtp = [...otpCode];
    newOtp[index] = val.slice(-1);
    setOtpCode(newOtp);
    if (val && index < 3) {
      const nextInput = document.getElementById(`otp-input-${index + 1}`);
      if (nextInput) (nextInput as HTMLInputElement).focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpCode[index] && index > 0) {
      const prevInput = document.getElementById(`otp-input-${index - 1}`);
      if (prevInput) {
        (prevInput as HTMLInputElement).focus();
        const newOtp = [...otpCode];
        newOtp[index - 1] = '';
        setOtpCode(newOtp);
      }
    }
  };

  const formatTime = (seconds: number) => {
    return `00:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  useEffect(() => {
    if (!showOtpCard) return;
    setTimer(49);
    const interval = setInterval(() => {
      setTimer((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [showOtpCard]);

  if (!isOpen) return null;


  // ─── Derived colours ─────────────────────────────────────────────────────
  const isDark = theme === 'dark';
  const cardBg = isDark ? 'rgba(0,0,0,0.72)' : 'rgba(255,255,255,0.72)';
  const cardBorder = isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)';
  const cardShadow = isDark
    ? '0 24px 64px rgba(0,0,0,0.85), inset 0 1px 0 rgba(255,255,255,0.06)'
    : '0 24px 64px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.6)';
  const textColor = isDark ? '#fff' : '#000';
  const subColor = isDark ? 'rgba(255,255,255,0.52)' : 'rgba(0,0,0,0.52)';
  const labelColor = isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)';
  const btnBg = isDark ? '#fff' : '#000';
  const btnText = isDark ? '#000' : '#fff';
  const btnHover = isDark ? '#e5e7eb' : '#1f2937';
  const accentGlow = isDark
    ? '0 12px 28px rgba(255,255,255,0.35), 0 4px 12px rgba(255,255,255,0.12)'
    : '0 12px 28px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.08)';

  const updateBtnBg = isDark ? '#2563eb' : '#000000';
  const updateBtnText = '#ffffff';
  const updateBtnHover = isDark ? '#1d4ed8' : '#1f2937';
  const updateBtnShadow = isDark ? '0 4px 14px rgba(37, 99, 235, 0.4)' : '0 4px 14px rgba(0, 0, 0, 0.2)';
  const updateBtnHoverShadow = isDark ? '0 6px 20px rgba(37, 99, 235, 0.6)' : '0 6px 20px rgba(0, 0, 0, 0.35)';

  const iconColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
  const iconFocused = textColor;

  return (
    <>
      {/* ── Keyframes injected once ── */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes modalEntrance {
          from { opacity: 0; transform: translate(-50%, -50%) scale(0.92); }
          to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        }
        @keyframes slideFromRight {
          from { opacity: 0; transform: translateX(30px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideFromLeft {
          from { opacity: 0; transform: translateX(-30px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes themeBtnEntrance {
          from { opacity: 0; transform: translateY(20px) scale(0.8); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes slideUpFromBottom {
          from { opacity: 0; transform: translate(-50%, 100vh); }
          to   { opacity: 1; transform: translate(-50%, -50%); }
        }
        @keyframes blink {
          from, to { color: transparent; }
          50% { color: currentColor; }
        }
        .nexus-input::placeholder { color: ${isDark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)'}; }
        .nexus-input:-webkit-autofill,
        .nexus-input:-webkit-autofill:hover,
        .nexus-input:-webkit-autofill:focus {
          -webkit-text-fill-color: ${textColor};
          -webkit-box-shadow: 0 0 0px 1000px ${isDark ? 'rgba(12,12,24,0.95)' : 'rgba(240,240,240,0.95)'} inset;
          transition: background-color 5000s ease-in-out 0s;
        }
        .nexus-select option { background: #111; color: #fff; }
      `}} />

      {/* ── Backdrop ── */}
      <div
        onClick={view === 'welcome_screen' ? handleWelcomeRedirect : onClose}
        style={{
          position: 'fixed', inset: 0,
          background: isDark ? 'rgba(0,0,0,0.5)' : 'rgba(200,200,200,0.45)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          zIndex: 1000,
          transition: 'background 0.35s ease',
        }}
      />

      {/* ── Modal Card ── */}
      <div
        onClick={view === 'welcome_screen' ? handleWelcomeRedirect : undefined}
        style={{
          position: 'fixed',
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1001,
          width: '90%',
          maxWidth: view === 'signup' ? '440px' : '410px',
          background: cardBg,
          backdropFilter: 'blur(32px) saturate(200%)',
          WebkitBackdropFilter: 'blur(32px) saturate(200%)',
          border: cardBorder,
          borderRadius: '24px',
          padding: view === 'signup' ? '48px 38px 44px 38px' : '64px 38px 60px 38px',
          boxShadow: cardShadow,
          color: textColor,
          fontFamily: "'Inter', sans-serif",
          boxSizing: 'border-box',
          animation: 'modalEntrance 0.3s cubic-bezier(0.34,1.56,0.64,1) forwards',
          transition: 'background 0.35s, border-color 0.35s, color 0.35s, box-shadow 0.35s, max-width 0.35s, padding 0.35s, opacity 0.3s, filter 0.3s',
          maxHeight: '92vh',
          overflowY: 'auto',
          scrollbarWidth: 'none',
          opacity: (showOtpPopup || showOtpCard) ? 0.3 : 1,
          pointerEvents: (showOtpPopup || showOtpCard) ? 'none' : 'auto',
          filter: (showOtpPopup || showOtpCard) ? 'blur(2px)' : 'none',
          cursor: view === 'welcome_screen' ? 'pointer' : 'default',
        }}
      >
        {/* ── Close button ── */}
        {view !== 'welcome_screen' && (
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              position: 'absolute', top: '20px', right: '20px',
              background: 'none', border: 'none',
              color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)',
              cursor: 'pointer', padding: '6px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              borderRadius: '50%', transition: 'color 0.2s, background 0.2s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = textColor;
              e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
              e.currentTarget.style.background = 'none';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/>
            </svg>
          </button>
        )}

        {/* ════════════════ LOGIN VIEW ════════════════ */}
        {view === 'login' && (
          <div style={{ animation: 'slideFromLeft 0.3s ease forwards' }}>
            <h3 style={{ fontSize: '28px', fontWeight: 700, textAlign: 'center', letterSpacing: '-0.025em', margin: '0 0 48px 0', color: textColor }}>
              Log in to your account
            </h3>

            <form onSubmit={handleLoginSubmit} style={{ width: '100%' }}>
              {/* Email */}
              <div style={{ position: 'relative', marginBottom: '20px' }}>
                <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: loginEmailFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                  </svg>
                </span>
                <input type="email" required placeholder="Email address" className="nexus-input"
                  value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
                  onFocus={() => setLoginEmailFocused(true)} onBlur={() => setLoginEmailFocused(false)}
                  style={inputStyle(loginEmailFocused, theme, { paddingLeft: '46px' })}
                />
              </div>

              {/* Password */}
              <div style={{ position: 'relative', marginBottom: '20px' }}>
                <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: loginPassFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                </span>
                <input type={showLoginPassword ? 'text' : 'password'} required placeholder="Password" className="nexus-input"
                  value={loginPassword} onChange={e => setLoginPassword(e.target.value)}
                  onFocus={() => setLoginPassFocused(true)} onBlur={() => setLoginPassFocused(false)}
                  style={inputStyle(loginPassFocused, theme, { paddingLeft: '46px', paddingRight: '46px' })}
                />
                <button type="button" onClick={() => setShowLoginPassword(!showLoginPassword)} style={{ position: 'absolute', top: '50%', right: '16px', transform: 'translateY(-50%)', background: 'none', border: 'none', color: iconColor, cursor: 'pointer', padding: 0, display: 'flex' }}
                  onMouseEnter={e => (e.currentTarget.style.color = textColor)} onMouseLeave={e => (e.currentTarget.style.color = iconColor)}>
                  {showLoginPassword
                    ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                    : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
                </button>
              </div>

              {/* Remember + Forgot */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', fontSize: '13.5px' }}>
                <div onClick={() => setIsRemembered(!isRemembered)} onMouseEnter={() => setIsSwitchHovered(true)} onMouseLeave={() => setIsSwitchHovered(false)}
                  style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', userSelect: 'none' }}>
                  <div style={{ width: '38px', height: '20px', borderRadius: '100px', background: isRemembered ? btnBg : (isDark ? 'rgba(255,255,255,0.16)' : 'rgba(0,0,0,0.12)'), position: 'relative', transition: 'background 0.25s ease, box-shadow 0.25s ease', boxShadow: isSwitchHovered ? (isDark ? '0 6px 18px rgba(255,255,255,0.4)' : '0 6px 18px rgba(0,0,0,0.2)') : 'none' }}>
                    <div style={{ width: '14px', height: '14px', borderRadius: '50%', background: isRemembered ? btnText : (isDark ? '#fff' : '#888'), position: 'absolute', top: '3px', left: isRemembered ? '21px' : '3px', transition: 'left 0.25s cubic-bezier(0.25,0.8,0.25,1), background 0.25s ease', boxShadow: '0 1px 3px rgba(0,0,0,0.4)' }} />
                  </div>
                  <span style={{ color: isDark ? 'rgba(255,255,255,0.72)' : 'rgba(0,0,0,0.72)', marginLeft: '10px', fontWeight: 400 }}>Remember me</span>
                </div>
                <a href="#forgot" onClick={e => { e.preventDefault(); setView('forgot'); }} style={{ color: subColor, textDecoration: 'none', transition: 'color 0.2s' }}
                  onMouseEnter={e => (e.currentTarget.style.color = textColor)} onMouseLeave={e => (e.currentTarget.style.color = subColor)}>
                  Forgot password?
                </a>
              </div>

              {/* Auth error message */}
              {authError && view === 'login' && (
                <p style={{ fontSize: '13px', color: '#ef4444', textAlign: 'center', margin: '0 0 16px 0' }}>
                  {authError}
                </p>
              )}

              {/* Log In button */}
              <button type="submit" disabled={authLoading}
                style={{ width: '100%', padding: '15px', border: 'none', borderRadius: '100px', background: btnBg, color: btnText, fontSize: '15.5px', fontWeight: 600, cursor: 'pointer', boxShadow: '0 8px 24px rgba(0,0,0,0.2)', transition: 'background 0.2s, transform 0.1s, box-shadow 0.2s', outline: 'none' }}
                onMouseEnter={e => { e.currentTarget.style.background = btnHover; e.currentTarget.style.boxShadow = accentGlow; }}
                onMouseLeave={e => { e.currentTarget.style.background = btnBg; e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.2)'; }}
                onMouseDown={e => { e.currentTarget.style.transform = 'scale(0.985)'; }}
                onMouseUp={e => { e.currentTarget.style.transform = 'scale(1)'; }}
              >
                Log In
              </button>
            </form>

            <div style={{ width: '100%', height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', margin: '40px 0' }} />

            <p style={{ fontSize: '13.5px', textAlign: 'center', color: subColor, margin: 0 }}>
              Don't have an account?{' '}
              <a href="#create" onClick={e => { e.preventDefault(); setView('signup'); }}
                style={{ color: textColor, fontWeight: 600, textDecoration: 'none', cursor: 'pointer', transition: 'text-decoration 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
                Create Account
              </a>
            </p>
          </div>
        )}

        {/* ════════════════ SIGNUP VIEW ════════════════ */}
        {view === 'signup' && (
          <div style={{ animation: 'slideFromRight 0.3s ease forwards' }}>
            <h3 style={{ fontSize: '26px', fontWeight: 700, textAlign: 'center', letterSpacing: '-0.025em', margin: '0 0 6px 0', color: textColor }}>
              Create an account
            </h3>
            <p style={{ fontSize: '14px', textAlign: 'center', color: subColor, margin: '0 0 32px 0' }}>
              Welcome! Create an account to get started.
            </p>

            <form onSubmit={handleSignupSubmit} style={{ width: '100%' }}>
              {/* Role dropdown */}
              <div style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Role</label>
                <div style={{ position: 'relative' }}>
                  <div onClick={() => setRoleOpen(!roleOpen)}
                    style={{ ...inputStyle(roleOpen, theme), display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', paddingLeft: '16px', paddingRight: '40px', userSelect: 'none' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.5)'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                    </svg>
                    <span style={{ flex: 1, fontSize: '14px', color: textColor }}>{role}</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.5)'} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ position: 'absolute', right: '16px', transition: 'transform 0.2s', transform: roleOpen ? 'rotate(180deg)' : 'none' }}>
                      <path d="m6 9 6 6 6-6"/>
                    </svg>
                  </div>
                  {roleOpen && (
                    <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, background: isDark ? 'rgba(18,18,28,0.97)' : 'rgba(250,250,250,0.97)', backdropFilter: 'blur(16px)', border: isDark ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(0,0,0,0.1)', borderRadius: '16px', overflow: 'hidden', zIndex: 10, boxShadow: '0 12px 40px rgba(0,0,0,0.4)' }}>
                      {ROLES.map(r => (
                        <div key={r} onClick={() => { setRole(r); setRoleOpen(false); }}
                          style={{ padding: '11px 18px', cursor: 'pointer', fontSize: '14px', color: r === role ? btnBg : textColor, background: r === role ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)') : 'transparent', transition: 'background 0.15s' }}
                          onMouseEnter={e => (e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)')}
                          onMouseLeave={e => (e.currentTarget.style.background = r === role ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)') : 'transparent')}>
                          {r}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* First + Last name */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '18px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>First name</label>
                  <input type="text" placeholder="" className="nexus-input"
                    value={firstName} onChange={e => setFirstName(e.target.value)}
                    onFocus={() => setFirstNameFocused(true)} onBlur={() => setFirstNameFocused(false)}
                    style={{ ...inputStyle(firstNameFocused, theme), borderRadius: '14px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Last name</label>
                  <input type="text" placeholder="" className="nexus-input"
                    value={lastName} onChange={e => setLastName(e.target.value)}
                    onFocus={() => setLastNameFocused(true)} onBlur={() => setLastNameFocused(false)}
                    style={{ ...inputStyle(lastNameFocused, theme), borderRadius: '14px' }}
                  />
                </div>
              </div>

              {/* Username */}
              <div style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Username</label>
                <input type="text" placeholder="" className="nexus-input"
                  value={username} onChange={e => setUsername(e.target.value)}
                  onFocus={() => setUsernameFocused(true)} onBlur={() => setUsernameFocused(false)}
                  style={{ ...inputStyle(usernameFocused, theme), borderRadius: '14px' }}
                />
              </div>

              {/* Email */}
              <div style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Email address</label>
                <input type="email" required placeholder="" className="nexus-input"
                  value={signupEmail} onChange={e => setSignupEmail(e.target.value)}
                  onFocus={() => setSignupEmailFocused(true)}
                  onBlur={() => {
                    setSignupEmailFocused(false);
                    const emailValid = signupEmail && signupEmail.includes('@') && signupEmail.split('@')[1]?.includes('.');
                    if (emailValid && !isOtpVerified) {
                      setShowOtpPopup(true);
                    }
                  }}
                  style={{ ...inputStyle(signupEmailFocused, theme), borderRadius: '14px' }}
                />
              </div>

              {/* Password */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Input with password strength indicator</label>
                <div 
                  style={{ position: 'relative', cursor: isOtpVerified ? 'text' : 'pointer' }}
                  onClick={() => {
                    if (!isOtpVerified) {
                      const emailValid = signupEmail && signupEmail.includes('@') && signupEmail.split('@')[1]?.includes('.');
                      if (emailValid) {
                        setShowOtpPopup(true);
                      } else {
                        const emailInput = document.querySelector('input[type="email"]');
                        if (emailInput) (emailInput as HTMLInputElement).focus();
                      }
                    }
                  }}
                >
                  <input type={showSignupPassword ? 'text' : 'password'} required placeholder="Password" className="nexus-input"
                    id="signup-password-input"
                    value={signupPassword} onChange={e => setSignupPassword(e.target.value)}
                    onFocus={() => {
                      if (!isOtpVerified) {
                        document.getElementById('signup-password-input')?.blur();
                        const emailValid = signupEmail && signupEmail.includes('@') && signupEmail.split('@')[1]?.includes('.');
                        if (emailValid) {
                          setShowOtpPopup(true);
                        }
                      } else {
                        setSignupPassFocused(true);
                      }
                    }}
                    onBlur={() => setSignupPassFocused(false)}
                    style={{ 
                      ...inputStyle(signupPassFocused, theme), 
                      borderRadius: '14px', 
                      paddingRight: '46px',
                      opacity: isOtpVerified ? 1 : 0.6,
                      cursor: isOtpVerified ? 'text' : 'not-allowed'
                    }}
                    disabled={!isOtpVerified}
                  />
                  <button type="button" 
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isOtpVerified) {
                        setShowSignupPassword(!showSignupPassword);
                      }
                    }}
                    style={{ position: 'absolute', top: '50%', right: '14px', transform: 'translateY(-50%)', background: 'none', border: 'none', color: iconColor, cursor: isOtpVerified ? 'pointer' : 'not-allowed', padding: 0, display: 'flex' }}
                    onMouseEnter={e => { if (isOtpVerified) e.currentTarget.style.color = textColor; }} 
                    onMouseLeave={e => { e.currentTarget.style.color = iconColor; }}>
                    {showSignupPassword
                      ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                      : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
                  </button>
                </div>
              </div>

              {/* Password strength indicator requirements container */}
              <div
                style={{
                  maxHeight: (signupPassFocused || signupPassword) ? '270px' : '0px',
                  opacity: (signupPassFocused || signupPassword) ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.35s ease, margin-top 0.35s ease, margin-bottom 0.35s ease',
                  marginTop: (signupPassFocused || signupPassword) ? '12px' : '0px',
                  marginBottom: (signupPassFocused || signupPassword) ? '24px' : '0px',
                }}
              >
                {/* Strength bar track */}
                <div style={{
                  width: '100%',
                  height: '6px',
                  background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)',
                  borderRadius: '100px',
                  marginBottom: '16px',
                  overflow: 'hidden',
                  position: 'relative',
                }}>
                  <div style={{
                    width: `${(metCount / 5) * 100}%`,
                    height: '100%',
                    background: signupPassword === '' 
                      ? (isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)') 
                      : (metCount === 5 ? '#22c55e' : '#f97316'),
                    borderRadius: '100px',
                    transition: 'width 0.3s ease-out, background-color 0.3s ease',
                  }} />
                </div>

                {/* Status text */}
                <div style={{ 
                  fontSize: '15.5px', 
                  fontWeight: 600, 
                  color: textColor, 
                  marginBottom: '12px',
                  fontFamily: "'Inter', sans-serif"
                }}>
                  {signupPassword === '' 
                    ? 'Enter a password. Must contain:' 
                    : (metCount === 5 ? 'Strong password.' : 'Weak password. Must contain:')
                  }
                </div>

                {/* Requirement list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '4px' }}>
                  {[
                    { label: 'At least 8 characters', met: hasMinLength },
                    { label: 'At least 1 number', met: hasNumber },
                    { label: 'At least 1 lowercase letter', met: hasLowercase },
                    { label: 'At least 1 uppercase letter', met: hasUppercase },
                    { label: 'At least 1 special character', met: hasSpecialChar },
                  ].map((req, i) => (
                    <div key={i} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '10px', 
                      fontSize: '14.5px',
                      color: req.met 
                        ? (isDark ? '#4ade80' : '#15803d') 
                        : (isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)'),
                      transition: 'color 0.2s',
                    }}>
                      {req.met ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                          <line x1="18" x2="6" y1="6" y2="18" />
                          <line x1="6" x2="18" y1="6" y2="18" />
                        </svg>
                      )}
                      <span>{req.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Confirm Password (collapsible container) */}
              <div
                style={{
                  maxHeight: (metCount === 5) ? '120px' : '0px',
                  opacity: (metCount === 5) ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.35s ease, margin-bottom 0.35s ease',
                  marginBottom: (metCount === 5) ? '20px' : '0px',
                }}
              >
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Confirm Password</label>
                <div style={{ position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: confirmPassFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </span>
                  <input 
                    type={showSignupConfirmPassword ? 'text' : 'password'} 
                    placeholder="Confirm your password" 
                    className="nexus-input"
                    value={signupConfirmPassword} 
                    onChange={e => setSignupConfirmPassword(e.target.value)}
                    onFocus={() => setConfirmPassFocused(true)} 
                    onBlur={() => setConfirmPassFocused(false)}
                    style={{ 
                      ...inputStyle(confirmPassFocused, theme, { paddingLeft: '46px', paddingRight: '46px' }), 
                      borderRadius: '14px' 
                    }}
                  />
                  <button 
                    type="button" 
                    onClick={() => setShowSignupConfirmPassword(!showSignupConfirmPassword)}
                    style={{ position: 'absolute', top: '50%', right: '16px', transform: 'translateY(-50%)', background: 'none', border: 'none', color: iconColor, cursor: 'pointer', padding: 0, display: 'flex' }}
                    onMouseEnter={e => (e.currentTarget.style.color = textColor)} 
                    onMouseLeave={e => (e.currentTarget.style.color = iconColor)}
                  >
                    {showSignupConfirmPassword
                      ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                      : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
                  </button>
                </div>
              </div>

              {/* Terms checkbox */}
              <div 
                onClick={() => {
                  if (metCount === 5 && passwordsMatch) {
                    setAgreeTerms(!agreeTerms);
                  }
                }}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '10px', 
                  marginBottom: '24px', 
                  cursor: (metCount === 5 && passwordsMatch) ? 'pointer' : 'not-allowed', 
                  userSelect: 'none',
                  opacity: (metCount === 5 && passwordsMatch) ? 1 : 0.5,
                  transition: 'opacity 0.2s',
                }}
              >
                <div style={{ width: '18px', height: '18px', borderRadius: '6px', border: agreeTerms ? 'none' : (isDark ? '1.5px solid rgba(255,255,255,0.3)' : '1.5px solid rgba(0,0,0,0.25)'), background: agreeTerms ? btnBg : 'transparent', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.2s, border 0.2s' }}>
                  {agreeTerms && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke={btnText} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>}
                </div>
                <span style={{ fontSize: '13.5px', color: isDark ? 'rgba(255,255,255,0.72)' : 'rgba(0,0,0,0.72)' }}>
                  I agree to the{' '}
                  <span style={{ color: textColor, fontWeight: 600 }}>Terms</span>
                  {' '}&{' '}
                  <span style={{ color: textColor, fontWeight: 600 }}>Conditions</span>
                </span>
              </div>

              {/* Auth error message */}
              {authError && view === 'signup' && (
                <p style={{ fontSize: '13px', color: '#ef4444', textAlign: 'center', margin: '0 0 16px 0' }}>
                  {authError}
                </p>
              )}

              {/* Create Account button — always white, glows from below on hover */}
              <button type="submit" disabled={!agreeTerms || metCount < 5 || !passwordsMatch || authLoading}
                style={{
                  width: '100%',
                  padding: '15px',
                  border: 'none',
                  borderRadius: '100px',
                  background: '#ffffff',
                  color: '#000000',
                  fontSize: '15.5px',
                  fontWeight: 600,
                  cursor: (agreeTerms && metCount === 5 && passwordsMatch) ? 'pointer' : 'default',
                  opacity: (agreeTerms && metCount === 5 && passwordsMatch) ? 1 : 0.45,
                  transition: 'background 0.2s, opacity 0.2s, transform 0.1s, box-shadow 0.2s',
                  outline: 'none',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                }}
                onMouseEnter={e => {
                  if (!agreeTerms || metCount < 5 || !passwordsMatch) return;
                  e.currentTarget.style.background = '#e5e7eb';
                  e.currentTarget.style.boxShadow = '0 14px 32px rgba(255, 255, 255, 0.45), 0 4px 14px rgba(255, 255, 255, 0.2)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = '#ffffff';
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18)';
                }}
                onMouseDown={e => {
                  if (!agreeTerms || metCount < 5 || !passwordsMatch) return;
                  e.currentTarget.style.transform = 'scale(0.985)';
                  e.currentTarget.style.boxShadow = '0 6px 18px rgba(255, 255, 255, 0.55), 0 2px 8px rgba(255, 255, 255, 0.25)';
                }}
                onMouseUp={e => {
                  e.currentTarget.style.transform = 'scale(1)';
                  e.currentTarget.style.boxShadow = '0 14px 32px rgba(255, 255, 255, 0.45), 0 4px 14px rgba(255, 255, 255, 0.2)';
                }}>
                Sign Up
              </button>
            </form>

            <div style={{ width: '100%', height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', margin: '28px 0' }} />

            <p style={{ fontSize: '13.5px', textAlign: 'center', color: subColor, margin: 0 }}>
              Already have an account?{' '}
              <a href="#signin" onClick={e => { e.preventDefault(); setView('login'); }}
                style={{ color: textColor, fontWeight: 600, textDecoration: 'none', cursor: 'pointer' }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
                Sign in
              </a>
            </p>
          </div>
        )}

        {/* ════════════════ FORGOT PASSWORD VIEW ════════════════ */}
        {view === 'forgot' && (
          <div style={{ animation: 'slideFromRight 0.3s ease forwards' }}>
            <h3 style={{ fontSize: '28px', fontWeight: 700, textAlign: 'center', letterSpacing: '-0.025em', margin: '0 0 12px 0', color: textColor }}>
              Forgot password?
            </h3>
            <p style={{ fontSize: '14.5px', textAlign: 'center', color: subColor, margin: '0 0 38px 0', lineHeight: 1.5 }}>
              Enter your email and we'll send you a reset link
            </p>

            <form onSubmit={handleForgotSubmit} style={{ width: '100%' }}>
              {/* Email field */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: forgotEmailFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                    </svg>
                  </span>
                  <input type="email" required placeholder="you@example.com" className="nexus-input"
                    value={forgotEmail} onChange={e => setForgotEmail(e.target.value)}
                    onFocus={() => setForgotEmailFocused(true)} onBlur={() => setForgotEmailFocused(false)}
                    style={inputStyle(forgotEmailFocused, theme, { paddingLeft: '46px', borderRadius: '14px' })}
                  />
                </div>
              </div>

              {/* Submit button */}
              <button type="submit"
                disabled={!isForgotEmailValid}
                style={{
                  width: '100%',
                  padding: '15px',
                  border: 'none',
                  borderRadius: '100px',
                  background: isForgotEmailValid ? btnBg : '#7e7e7e',
                  color: isForgotEmailValid ? btnText : '#ffffff',
                  fontSize: '15.5px',
                  fontWeight: 600,
                  cursor: isForgotEmailValid ? 'pointer' : 'not-allowed',
                  boxShadow: isForgotEmailValid ? '0 8px 24px rgba(0,0,0,0.2)' : 'none',
                  transition: 'background 0.2s, transform 0.1s, box-shadow 0.2s',
                  outline: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
                onMouseEnter={e => {
                  if (!isForgotEmailValid) return;
                  e.currentTarget.style.background = btnHover;
                  e.currentTarget.style.boxShadow = accentGlow;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = isForgotEmailValid ? btnBg : '#7e7e7e';
                  e.currentTarget.style.boxShadow = isForgotEmailValid ? '0 8px 24px rgba(0,0,0,0.2)' : 'none';
                  e.currentTarget.style.transform = 'none';
                }}
                onMouseDown={e => {
                  if (!isForgotEmailValid) return;
                  e.currentTarget.style.transform = 'scale(0.985)';
                }}
                onMouseUp={e => {
                  if (!isForgotEmailValid) return;
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                <span>Send OTP</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </button>
            </form>

            {/* Separator */}
            <div style={{ display: 'flex', alignItems: 'center', margin: '32px 0' }}>
              <div style={{ flex: 1, height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' }} />
              <span style={{ padding: '0 16px', fontSize: '13.5px', color: subColor, fontWeight: 500 }}>OR</span>
              <div style={{ flex: 1, height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' }} />
            </div>

            {/* Navigation stack */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', fontSize: '14px' }}>
              <a href="#signin" onClick={e => { e.preventDefault(); setView('login'); }}
                style={{ color: textColor, fontWeight: 600, textDecoration: 'none', cursor: 'pointer' }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
                Back to log in
              </a>
              <a href="#create" onClick={e => { e.preventDefault(); setView('signup'); }}
                style={{ color: subColor, textDecoration: 'none', cursor: 'pointer', transition: 'color 0.2s' }}
                onMouseEnter={e => { e.currentTarget.style.color = textColor; e.currentTarget.style.textDecoration = 'underline'; }}
                onMouseLeave={e => { e.currentTarget.style.color = subColor; e.currentTarget.style.textDecoration = 'none'; }}>
                Create a new account
              </a>
            </div>
          </div>
        )}

        {/* ════════════════ FORGOT PASSWORD OTP VERIFICATION VIEW ════════════════ */}
        {view === 'otp_verify' && (
          <div style={{ animation: 'slideFromRight 0.3s ease forwards' }}>
            {/* Header circular envelope icon */}
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
              <div style={{
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
                border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.06)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.4)' : '0 8px 24px rgba(0,0,0,0.05)',
                position: 'relative'
              }}>
                <div style={{
                  position: 'absolute',
                  inset: '-6px',
                  borderRadius: '50%',
                  border: isDark ? '1px solid rgba(255,255,255,0.03)' : '1px solid rgba(0,0,0,0.02)',
                  pointerEvents: 'none'
                }} />
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)' }}>
                  <path d="M22 13V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h9" />
                  <polyline points="22 7 12 13 2 7" />
                  <path d="m16 19 2 2 4-4" stroke={isDark ? '#4ade80' : '#16a34a'} strokeWidth="2.5" />
                </svg>
              </div>
            </div>

            <h3 style={{ fontSize: '24px', fontWeight: 700, textAlign: 'center', margin: '0 0 8px 0', letterSpacing: '-0.02em', color: textColor }}>
              Enter your one-time password
            </h3>
            <p style={{ fontSize: '14.5px', textAlign: 'center', color: subColor, margin: '0 0 32px 0', lineHeight: 1.5 }}>
              We've sent a code to your email. Please enter it below.
            </p>

            <div style={{ width: '100%', height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', marginBottom: '32px' }} />

            <form onSubmit={handleForgotOtpSubmit} style={{ width: '100%' }}>
              {/* 6 digits OTP grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '10px', marginBottom: '32px' }}>
                {forgotOtpCode.map((digit, index) => (
                  <input
                    key={index}
                    id={`forgot-otp-input-${index}`}
                    type="text"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleForgotOtpChange(index, e.target.value)}
                    onKeyDown={(e) => handleForgotOtpKeyDown(index, e)}
                    style={{
                      width: '100%',
                      height: '56px',
                      background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
                      border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.15)',
                      borderRadius: '12px',
                      textAlign: 'center',
                      fontSize: '20px',
                      fontWeight: '600',
                      color: textColor,
                      outline: 'none',
                      transition: 'border-color 0.2s',
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';
                    }}
                  />
                ))}
              </div>

              {/* Continue button */}
              <button
                type="submit"
                disabled={forgotOtpCode.some(d => !d) || isForgotOtpVerifying || forgotOtpSuccess}
                style={{
                  width: '100%',
                  padding: '15px',
                  background: btnBg,
                  color: btnText,
                  border: 'none',
                  borderRadius: '100px',
                  fontSize: '15.5px',
                  fontWeight: '600',
                  cursor: (forgotOtpCode.some(d => !d) || isForgotOtpVerifying || forgotOtpSuccess) ? 'default' : 'pointer',
                  opacity: (forgotOtpCode.some(d => !d) || isForgotOtpVerifying || forgotOtpSuccess) ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'background 0.2s, transform 0.1s, box-shadow 0.2s',
                  marginBottom: '32px',
                  outline: 'none',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
                }}
                onMouseEnter={e => {
                  if (forgotOtpCode.some(d => !d) || isForgotOtpVerifying || forgotOtpSuccess) return;
                  e.currentTarget.style.background = btnHover;
                  e.currentTarget.style.boxShadow = accentGlow;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = btnBg;
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.2)';
                }}
                onMouseDown={e => {
                  if (forgotOtpCode.some(d => !d) || isForgotOtpVerifying || forgotOtpSuccess) return;
                  e.currentTarget.style.transform = 'scale(0.985)';
                }}
                onMouseUp={e => {
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                {isForgotOtpVerifying ? (
                  <>
                    <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
                      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
                      <path d="M12 2a10 10 0 0 1 10 10" />
                    </svg>
                    <span>Verifying...</span>
                  </>
                ) : forgotOtpSuccess ? (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Verified!</span>
                  </>
                ) : (
                  'Continue'
                )}
              </button>
            </form>

            <div style={{ width: '100%', height: '1px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', marginBottom: '24px' }} />

            <p style={{ fontSize: '13.5px', textAlign: 'center', color: subColor, margin: 0 }}>
              Experiencing issues receiving the code?{' '}
              <a href="#resend" onClick={e => { e.preventDefault(); console.log('Resending forgot password OTP'); }}
                style={{ color: textColor, fontWeight: 600, textDecoration: 'underline', cursor: 'pointer' }}>
                Resend Code
              </a>
            </p>
          </div>
        )}

        {/* ════════════════ UPDATE PASSWORD VIEW ════════════════ */}
        {view === 'update_password' && (
          <div style={{ animation: 'slideFromRight 0.3s ease forwards' }}>
            <h3 style={{ fontSize: '28px', fontWeight: 700, textAlign: 'center', letterSpacing: '-0.025em', margin: '0 0 8px 0', color: textColor }}>
              Update Password
            </h3>
            <p style={{ fontSize: '14.5px', textAlign: 'center', color: subColor, margin: '0 0 38px 0' }}>
              Enter your new password below
            </p>

            <form onSubmit={handleUpdatePasswordSubmit} style={{ width: '100%' }}>
              {/* New Password */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>New Password</label>
                <div style={{ position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: newPasswordFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </span>
                  <input type={showNewPassword ? 'text' : 'password'} required placeholder="Create a strong password" className="nexus-input"
                    value={newPassword} onChange={e => setNewPassword(e.target.value)}
                    onFocus={() => setNewPasswordFocused(true)} onBlur={() => setNewPasswordFocused(false)}
                    style={inputStyle(newPasswordFocused, theme, { paddingLeft: '46px', paddingRight: '46px', borderRadius: '14px' })}
                  />
                  <button type="button" onClick={() => setShowNewPassword(!showNewPassword)} style={{ position: 'absolute', top: '50%', right: '16px', transform: 'translateY(-50%)', background: 'none', border: 'none', color: iconColor, cursor: 'pointer', padding: 0, display: 'flex' }}
                    onMouseEnter={e => (e.currentTarget.style.color = textColor)} onMouseLeave={e => (e.currentTarget.style.color = iconColor)}>
                    {showNewPassword
                      ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                      : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
                  </button>
                </div>
              </div>

              {/* Password strength indicator requirements container */}
              <div
                style={{
                  maxHeight: (newPasswordFocused || newPassword) ? '270px' : '0px',
                  opacity: (newPasswordFocused || newPassword) ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.35s ease, margin-top 0.35s ease, margin-bottom 0.35s ease',
                  marginTop: (newPasswordFocused || newPassword) ? '12px' : '0px',
                  marginBottom: (newPasswordFocused || newPassword) ? '24px' : '0px',
                }}
              >
                {/* Strength bar track */}
                <div style={{
                  width: '100%',
                  height: '6px',
                  background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)',
                  borderRadius: '100px',
                  marginBottom: '16px',
                  overflow: 'hidden',
                  position: 'relative',
                }}>
                  <div style={{
                    width: `${(newMetCount / 5) * 100}%`,
                    height: '100%',
                    background: newPassword === '' 
                      ? (isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)') 
                      : (newMetCount === 5 ? '#22c55e' : '#f97316'),
                    borderRadius: '100px',
                    transition: 'width 0.3s ease-out, background-color 0.3s ease',
                  }} />
                </div>

                {/* Status text */}
                <div style={{ 
                  fontSize: '15.5px', 
                  fontWeight: 600, 
                  color: textColor, 
                  marginBottom: '12px',
                  fontFamily: "'Inter', sans-serif"
                }}>
                  {newPassword === '' 
                    ? 'Enter a password. Must contain:' 
                    : (newMetCount === 5 ? 'Strong password.' : 'Weak password. Must contain:')
                  }
                </div>

                {/* Requirement list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '4px' }}>
                  {[
                    { label: 'At least 8 characters', met: newHasMinLength },
                    { label: 'At least 1 number', met: newHasNumber },
                    { label: 'At least 1 lowercase letter', met: newHasLowercase },
                    { label: 'At least 1 uppercase letter', met: newHasUppercase },
                    { label: 'At least 1 special character', met: newHasSpecialChar },
                  ].map((req, i) => (
                    <div key={i} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '10px', 
                      fontSize: '14.5px',
                      color: req.met 
                        ? (isDark ? '#4ade80' : '#15803d') 
                        : (isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)'),
                      transition: 'color 0.2s',
                    }}>
                      {req.met ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                          <line x1="18" x2="6" y1="6" y2="18" />
                          <line x1="6" x2="18" y1="6" y2="18" />
                        </svg>
                      )}
                      <span>{req.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Confirm New Password (collapsible container) */}
              <div
                style={{
                  maxHeight: (newMetCount === 5) ? '120px' : '0px',
                  opacity: (newMetCount === 5) ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.35s ease, margin-bottom 0.35s ease',
                  marginBottom: (newMetCount === 5) ? '32px' : '0px',
                }}
              >
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: labelColor, marginBottom: '8px' }}>Confirm New Password</label>
                <div style={{ position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: confirmNewPasswordFocused ? iconFocused : iconColor, display: 'flex', pointerEvents: 'none', transition: 'color 0.2s' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </span>
                  <input type={showConfirmNewPassword ? 'text' : 'password'} required placeholder="Confirm your new password" className="nexus-input"
                    value={confirmNewPassword} onChange={e => setConfirmNewPassword(e.target.value)}
                    onFocus={() => setConfirmNewPasswordFocused(true)} onBlur={() => setConfirmNewPasswordFocused(false)}
                    style={inputStyle(confirmNewPasswordFocused, theme, { paddingLeft: '46px', paddingRight: '46px', borderRadius: '14px' })}
                  />
                  <button type="button" onClick={() => setShowConfirmNewPassword(!showConfirmNewPassword)} style={{ position: 'absolute', top: '50%', right: '16px', transform: 'translateY(-50%)', background: 'none', border: 'none', color: iconColor, cursor: 'pointer', padding: 0, display: 'flex' }}
                    onMouseEnter={e => (e.currentTarget.style.color = textColor)} onMouseLeave={e => (e.currentTarget.style.color = iconColor)}>
                    {showConfirmNewPassword
                      ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                      : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>}
                  </button>
                </div>
              </div>

              {/* Update Password button */}
              <button type="submit"
                disabled={newMetCount < 5 || !newPasswordsMatch}
                style={{
                  width: '100%',
                  padding: '15px',
                  border: 'none',
                  borderRadius: '100px',
                  background: updateBtnBg,
                  color: updateBtnText,
                  fontSize: '15.5px',
                  fontWeight: 600,
                  cursor: (newMetCount < 5 || !newPasswordsMatch) ? 'default' : 'pointer',
                  opacity: (newMetCount < 5 || !newPasswordsMatch) ? 0.6 : 1,
                  transition: 'background 0.2s, transform 0.1s, box-shadow 0.2s',
                  outline: 'none',
                  boxShadow: updateBtnShadow,
                }}
                onMouseEnter={e => {
                  if (newMetCount < 5 || !newPasswordsMatch) return;
                  e.currentTarget.style.background = updateBtnHover;
                  e.currentTarget.style.boxShadow = updateBtnHoverShadow;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = updateBtnBg;
                  e.currentTarget.style.boxShadow = updateBtnShadow;
                }}
                onMouseDown={e => {
                  if (newMetCount < 5 || !newPasswordsMatch) return;
                  e.currentTarget.style.transform = 'scale(0.985)';
                }}
                onMouseUp={e => {
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                Update Password
              </button>
            </form>
          </div>
        )}

        {/* ════════════════ WELCOME SCREEN VIEW ════════════════ */}
        {view === 'welcome_screen' && (
          <div style={{ animation: 'slideFromRight 0.3s ease forwards', padding: '36px 0 24px 0' }}>
            {/* Concentric Green Circle Badge with "1" */}
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '32px' }}>
              <div style={{
                width: '120px',
                height: '120px',
                borderRadius: '50%',
                border: '4px solid #10b981',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                boxShadow: '0 0 32px rgba(16, 185, 129, 0.15)'
              }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                  fontSize: '24px',
                  fontWeight: 700,
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
                }}>
                  1
                </div>
              </div>
            </div>

            <h3 style={{ fontSize: '32px', fontWeight: 700, textAlign: 'center', margin: '0 0 16px 0', letterSpacing: '-0.025em', color: textColor, minHeight: '40px' }}>
              {typedTitle}
            </h3>
            <p style={{ fontSize: '15.5px', textAlign: 'center', color: subColor, margin: '0', lineHeight: 1.6, minHeight: '50px' }}>
              {typedSubtitle}
              {typedSubtitle.length > 0 && typedSubtitle.length < 'Experience the future of digital interaction with our premium platform'.length && (
                <span style={{ animation: 'blink 1s step-end infinite', fontWeight: 400 }}>|</span>
              )}
            </p>
          </div>
        )}
      </div>

      {/* ── OTP Verification Popup (Slide up button) ── */}
      {showOtpPopup && (
        <>
          {/* Transparent backdrop click catcher */}
          <div
            onClick={() => setShowOtpPopup(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 1100,
            }}
          />

          {/* Centered Popup Card matching the screenshot */}
          <div
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 1101,
              animation: 'slideUpFromBottom 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setShowOtpPopup(false);
                setShowOtpCard(true);
              }}
              style={{
                background: '#ffffff',
                border: '1px solid #d1d5db',
                borderRadius: '12px',
                color: '#000000',
                fontSize: '16px',
                fontWeight: '500',
                padding: '12px 28px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'all 0.2s ease',
                outline: 'none',
                boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
                fontFamily: "'Inter', sans-serif",
                minWidth: '140px',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = '#f9fafb';
                e.currentTarget.style.borderColor = '#9ca3af';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = '#ffffff';
                e.currentTarget.style.borderColor = '#d1d5db';
              }}
              onMouseDown={e => {
                e.currentTarget.style.transform = 'scale(0.96)';
              }}
              onMouseUp={e => {
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              Verify OTP
            </button>
          </div>
        </>
      )}

      {/* ── OTP Verification Modal Card ── */}
      {showOtpCard && (
        <>
          {/* Sibling click catcher backdrop to dismiss */}
          <div
            onClick={() => setShowOtpCard(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 1100,
            }}
          />

          {/* Centered OTP Verification Modal Card */}
          <div
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 1101,
              width: '90%',
              maxWidth: '380px',
              background: isDark ? '#1a1a24' : '#ffffff',
              border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.08)',
              borderRadius: '24px',
              padding: '40px 32px 32px 32px',
              boxShadow: isDark 
                ? '0 24px 64px rgba(0,0,0,0.85), inset 0 1px 0 rgba(255,255,255,0.06)' 
                : '0 24px 64px rgba(0,0,0,0.15)',
              color: textColor,
              fontFamily: "'Inter', sans-serif",
              boxSizing: 'border-box',
              animation: 'modalEntrance 0.3s cubic-bezier(0.34,1.56,0.64,1) forwards',
              textAlign: 'left',
            }}
          >
            {/* Close button */}
            <button
              type="button"
              onClick={() => setShowOtpCard(false)}
              aria-label="Close"
              style={{
                position: 'absolute', top: '24px', right: '24px',
                background: 'none', border: 'none',
                color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)',
                cursor: 'pointer', padding: '6px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                borderRadius: '50%', transition: 'color 0.2s, background 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = textColor;
                e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
                e.currentTarget.style.background = 'none';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/>
              </svg>
            </button>

            {/* Header */}
            <h3 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 16px 0', letterSpacing: '-0.02em', color: textColor }}>
              OTP Verification
            </h3>

            {/* Email send text */}
            <p style={{ fontSize: '15px', color: isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)', margin: '0 0 28px 0', lineHeight: 1.5 }}>
              Enter the 4-digit code sent to<br />
              <strong style={{ color: textColor, fontWeight: 700 }}>{signupEmail || 'example@email.com'}</strong>.
            </p>

            {/* Step label */}
            <p style={{ fontSize: '13.5px', color: isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)', margin: '0 0 16px 0', textAlign: 'center' }}>
              Step 1 of 1: Verify your account
            </p>

            {/* 4 Square inputs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '24px' }}>
              {otpCode.map((digit, index) => (
                <input
                  key={index}
                  id={`otp-input-${index}`}
                  type="text"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(index, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(index, e)}
                  style={{
                    width: '100%',
                    height: '60px',
                    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
                    border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.15)',
                    borderRadius: '12px',
                    textAlign: 'center',
                    fontSize: '22px',
                    fontWeight: '600',
                    color: textColor,
                    outline: 'none',
                    transition: 'border-color 0.2s',
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';
                  }}
                />
              ))}
            </div>

            {/* Resend OTP description countdown */}
            <p style={{ fontSize: '13.5px', color: isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)', margin: '0 0 24px 0', textAlign: 'center' }}>
              You can resend OTP in <strong style={{ color: textColor }}>{formatTime(timer)}</strong>
            </p>

            {/* Verify OTP Button (Primary black/dark button) */}
            <button
              type="button"
              onClick={() => {
                if (isOtpVerifying || otpSuccess) return;
                setIsOtpVerifying(true);
                setTimeout(() => {
                  setIsOtpVerifying(false);
                  setOtpSuccess(true);
                  setTimeout(() => {
                    setIsOtpVerified(true);
                    setShowOtpCard(false);
                    setOtpSuccess(false);
                    // Focus password field after verification completes
                    const passInput = document.getElementById('signup-password-input');
                    if (passInput) {
                      (passInput as HTMLInputElement).focus();
                    }
                  }, 800);
                }, 1200);
              }}
              style={{
                width: '100%',
                padding: '14px',
                background: isDark ? '#ffffff' : '#1a1a1a',
                color: isDark ? '#000000' : '#ffffff',
                border: 'none',
                borderRadius: '10px',
                fontSize: '16px',
                fontWeight: '600',
                cursor: (isOtpVerifying || otpSuccess) ? 'default' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'background 0.2s, transform 0.1s',
                marginBottom: '16px',
                outline: 'none',
              }}
              onMouseEnter={e => {
                if (isOtpVerifying || otpSuccess) return;
                e.currentTarget.style.background = isDark ? '#e5e7eb' : '#2d2d2d';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = isDark ? '#ffffff' : '#1a1a1a';
              }}
              onMouseDown={e => {
                if (isOtpVerifying || otpSuccess) return;
                e.currentTarget.style.transform = 'scale(0.98)';
              }}
              onMouseUp={e => {
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              {isOtpVerifying ? (
                <>
                  <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
                    <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
                    <path d="M12 2a10 10 0 0 1 10 10" />
                  </svg>
                  <span>Verifying...</span>
                </>
              ) : otpSuccess ? (
                <>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="green" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span style={{ color: 'green' }}>Verified!</span>
                </>
              ) : (
                'Verify OTP'
              )}
            </button>

            {/* Bottom Resend OTP Status Bar container */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.05)',
                borderRadius: '10px',
                fontSize: '14px',
              }}
            >
              <span style={{ color: isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)', fontWeight: 500 }}>Resend OTP</span>
              <span style={{ color: isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)' }}>{formatTime(timer)}</span>
            </div>

          </div>
        </>
      )}

    </>
  );
}

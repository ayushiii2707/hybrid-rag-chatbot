interface NavbarProps {
  sectionLabel: string;
}

export default function Navbar({ sectionLabel }: NavbarProps) {
  return (
    <nav
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 24px',
        height: '52px',
        pointerEvents: 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(10,10,20,0.72)',
          backdropFilter: 'blur(14px)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: '100px',
          padding: '6px 8px 6px 10px',
          boxShadow: '0 2px 24px rgba(0,0,0,0.5)',
        }}
      >
        {/* Logo icon */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '4px' }}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="8" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" />
            <circle cx="9" cy="9" r="3.5" fill="rgba(255,255,255,0.7)" />
          </svg>
          <span style={{
            fontSize: '10px',
            fontWeight: 600,
            letterSpacing: '0.12em',
            color: 'rgba(255,255,255,0.45)',
            textTransform: 'uppercase',
            minWidth: '68px',
            fontFamily: 'inherit',
          }}>
            # {sectionLabel}
          </span>
        </div>

        <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.12)', marginRight: '4px' }} />

        {['Product', 'Solutions', 'Pricing', 'Docs'].map((item) => (
          <button
            key={item}
            style={{
              background: 'none',
              border: 'none',
              color: 'rgba(255,255,255,0.7)',
              fontSize: '13px',
              fontWeight: 400,
              cursor: 'pointer',
              padding: '4px 10px',
              borderRadius: '6px',
              fontFamily: 'inherit',
              letterSpacing: '-0.01em',
              transition: 'color 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
          >
            {item}
          </button>
        ))}

        <button
          style={{
            background: 'none',
            border: 'none',
            color: 'rgba(255,255,255,0.55)',
            fontSize: '13px',
            fontWeight: 400,
            cursor: 'pointer',
            padding: '4px 10px',
            borderRadius: '6px',
            fontFamily: 'inherit',
            letterSpacing: '-0.01em',
          }}
        >
          Sign in
        </button>

        <button
          style={{
            background: 'rgba(255,255,255,0.95)',
            border: 'none',
            color: '#0a0a14',
            fontSize: '12.5px',
            fontWeight: 600,
            cursor: 'pointer',
            padding: '6px 14px',
            borderRadius: '100px',
            fontFamily: 'inherit',
            letterSpacing: '-0.01em',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          Get started
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2.5 6h7M6.5 3.5l3 2.5-3 2.5" stroke="#0a0a14" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </nav>
  );
}

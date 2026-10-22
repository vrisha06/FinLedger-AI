import React from 'react';

export type MotifType = 'balance' | 'flow' | 'seal' | 'immutable' | 'passbook';

interface LedgerMotifProps {
  type: MotifType;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  inverted?: boolean;
}

export const LedgerMotif: React.FC<LedgerMotifProps> = ({
  type,
  className = '',
  size = 'md',
  inverted = false,
}) => {
  const sizeMap = {
    sm: { width: 32, height: 32 },
    md: { width: 56, height: 56 },
    lg: { width: 88, height: 88 },
    xl: { width: 140, height: 140 },
  };

  const { width, height } = sizeMap[size];
  const primaryStroke = inverted ? '#E0EADF' : '#174B3A';
  const secondaryStroke = inverted ? '#C7D8BF' : '#AD6945';
  const accentFill = inverted ? 'rgba(224, 234, 223, 0.12)' : 'rgba(23, 75, 58, 0.06)';
  const ruleStroke = inverted ? 'rgba(224, 234, 223, 0.3)' : 'rgba(217, 215, 201, 0.9)';

  if (type === 'balance') {
    // Elegant Balanced-Ledger T-Account & Precision Scale
    return (
      <svg
        width={width}
        height={height}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 ${className}`}
        aria-hidden="true"
      >
        {/* Central fulcrum & balance beam */}
        <line x1="20" y1="44" x2="100" y2="44" stroke={primaryStroke} strokeWidth="2.5" strokeLinecap="round" />
        <line x1="60" y1="20" x2="60" y2="88" stroke={primaryStroke} strokeWidth="2" />
        <circle cx="60" cy="44" r="4.5" fill={primaryStroke} />

        {/* Left Pan (DEBIT) */}
        <line x1="28" y1="44" x2="20" y2="68" stroke={secondaryStroke} strokeWidth="1.2" />
        <line x1="28" y1="44" x2="36" y2="68" stroke={secondaryStroke} strokeWidth="1.2" />
        <path d="M 12 68 Q 28 80 44 68 Z" fill={accentFill} stroke={secondaryStroke} strokeWidth="1.5" />
        <text x="28" y="64" fontSize="7" fontFamily="monospace" fontWeight="bold" fill={secondaryStroke} textAnchor="middle">
          DR
        </text>

        {/* Right Pan (CREDIT) */}
        <line x1="92" y1="44" x2="84" y2="68" stroke={primaryStroke} strokeWidth="1.2" />
        <line x1="92" y1="44" x2="100" y2="68" stroke={primaryStroke} strokeWidth="1.2" />
        <path d="M 76 68 Q 92 80 108 68 Z" fill={accentFill} stroke={primaryStroke} strokeWidth="1.5" />
        <text x="92" y="64" fontSize="7" fontFamily="monospace" fontWeight="bold" fill={primaryStroke} textAnchor="middle">
          CR
        </text>

        {/* Base Pedestal */}
        <path d="M 44 94 L 76 94 L 70 88 L 50 88 Z" fill={accentFill} stroke={primaryStroke} strokeWidth="1.5" />
        <line x1="36" y1="94" x2="84" y2="94" stroke={primaryStroke} strokeWidth="2" strokeLinecap="round" />

        {/* Equality equation seal */}
        <text x="60" y="112" fontSize="8" fontFamily="serif" fontStyle="italic" fill={secondaryStroke} textAnchor="middle">
          Σ Debits = Σ Credits
        </text>
      </svg>
    );
  }

  if (type === 'flow') {
    // Directed money-flow & temporal ledger network
    return (
      <svg
        width={width}
        height={height}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 ${className}`}
        aria-hidden="true"
      >
        {/* Curved flow arcs */}
        <path
          d="M 20 60 C 20 30, 60 25, 60 60 C 60 95, 100 90, 100 60"
          stroke={primaryStroke}
          strokeWidth="2"
          strokeDasharray="4 3"
        />
        <circle cx="20" cy="60" r="7" fill={accentFill} stroke={primaryStroke} strokeWidth="2" />
        <circle cx="60" cy="60" r="10" fill={accentFill} stroke={secondaryStroke} strokeWidth="2" />
        <circle cx="100" cy="60" r="7" fill={accentFill} stroke={primaryStroke} strokeWidth="2" />

        {/* Inner indicators */}
        <circle cx="20" cy="60" r="2.5" fill={primaryStroke} />
        <circle cx="60" cy="60" r="4" fill={secondaryStroke} />
        <circle cx="100" cy="60" r="2.5" fill={primaryStroke} />

        {/* Flow vectors */}
        <polygon points="40,35 44,40 38,42" fill={secondaryStroke} />
        <polygon points="80,85 84,80 78,78" fill={primaryStroke} />

        <text x="60" y="110" fontSize="7" fontFamily="monospace" letterSpacing="1" fill={primaryStroke} textAnchor="middle">
          TEMPORAL POSTINGS
        </text>
      </svg>
    );
  }

  if (type === 'seal') {
    // Official institutional ledger seal / mark
    return (
      <svg
        width={width}
        height={height}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 ${className}`}
        aria-hidden="true"
      >
        {/* Outer serrated or fine concentric circles */}
        <circle cx="60" cy="60" r="54" stroke={primaryStroke} strokeWidth="1.5" strokeDasharray="3 2" />
        <circle cx="60" cy="60" r="49" stroke={primaryStroke} strokeWidth="2" />
        <circle cx="60" cy="60" r="44" stroke={ruleStroke} strokeWidth="1" />

        {/* Center monogram / icon */}
        <rect x="42" y="42" width="36" height="36" rx="4" fill={accentFill} stroke={primaryStroke} strokeWidth="1.5" />
        <text x="60" y="66" fontSize="18" fontFamily="serif" fontWeight="bold" fill={primaryStroke} textAnchor="middle">
          FL
        </text>

        {/* Top/Bottom seal text */}
        <path id="sealPathTop" d="M 24 60 A 36 36 0 0 1 96 60" fill="none" />
        <text fontSize="6.5" fontFamily="monospace" letterSpacing="1.8" fill={secondaryStroke} textAnchor="middle">
          <textPath href="#sealPathTop" startOffset="50%">
            POSTGRESQL AUDIT
          </textPath>
        </text>

        <path id="sealPathBottom" d="M 96 60 A 36 36 0 0 1 24 60" fill="none" />
        <text fontSize="6.5" fontFamily="monospace" letterSpacing="1.8" fill={secondaryStroke} textAnchor="middle">
          <textPath href="#sealPathBottom" startOffset="50%">
            IMMUTABLE LEDGER
          </textPath>
        </text>
      </svg>
    );
  }

  if (type === 'immutable') {
    // Cryptographic tamper-evident hash chain & append-only seal
    return (
      <svg
        width={width}
        height={height}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 ${className}`}
        aria-hidden="true"
      >
        {/* Shield / Vault Contour */}
        <path
          d="M 60 18 L 92 30 V 62 C 92 84, 60 102, 60 102 C 60 102, 28 84, 28 62 V 30 Z"
          fill={accentFill}
          stroke={primaryStroke}
          strokeWidth="2"
        />
        {/* Padlock Shackle and Body */}
        <path d="M 48 54 V 44 C 48 37.37, 53.37 32, 60 32 C 66.63 32, 72 37.37, 72 44 V 54" stroke={secondaryStroke} strokeWidth="2.5" strokeLinecap="round" />
        <rect x="42" y="54" width="36" height="26" rx="3" fill={primaryStroke} stroke={primaryStroke} strokeWidth="1.5" />
        <circle cx="60" cy="65" r="3" fill={inverted ? '#103B2E' : '#FFFEFA'} />
        <line x1="60" y1="68" x2="60" y2="74" stroke={inverted ? '#103B2E' : '#FFFEFA'} strokeWidth="2" strokeLinecap="round" />

        <text x="60" y="114" fontSize="7" fontFamily="monospace" letterSpacing="1" fill={secondaryStroke} textAnchor="middle">
          BEFORE TRIGGER ENFORCED
        </text>
      </svg>
    );
  }

  // Passbook motif
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <rect x="22" y="18" width="76" height="84" rx="4" fill={accentFill} stroke={primaryStroke} strokeWidth="2" />
      <line x1="30" y1="32" x2="90" y2="32" stroke={secondaryStroke} strokeWidth="2" />
      <line x1="30" y1="44" x2="75" y2="44" stroke={ruleStroke} strokeWidth="1" />
      <line x1="30" y1="56" x2="85" y2="56" stroke={ruleStroke} strokeWidth="1" />
      <line x1="30" y1="68" x2="70" y2="68" stroke={ruleStroke} strokeWidth="1" />
      <line x1="30" y1="80" x2="88" y2="80" stroke={ruleStroke} strokeWidth="1" />
      {/* Stamp circle in corner */}
      <circle cx="78" cy="74" r="14" stroke={secondaryStroke} strokeWidth="1.2" strokeDasharray="2 1.5" />
      <text x="78" y="77" fontSize="7" fontFamily="monospace" fill={secondaryStroke} textAnchor="middle">
        POSTED
      </text>
    </svg>
  );
};

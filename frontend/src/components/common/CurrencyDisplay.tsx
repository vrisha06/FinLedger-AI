import React from 'react';
import { formatINR } from '../../utils/formatters';

interface CurrencyDisplayProps {
  amount: string | number | null | undefined;
  className?: string;
  sign?: 'auto' | 'plus' | 'minus' | 'none';
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  colored?: boolean;
}

export const CurrencyDisplay: React.FC<CurrencyDisplayProps> = ({
  amount,
  className = '',
  sign = 'none',
  size = 'md',
  colored = false,
}) => {
  const num = typeof amount === 'string' ? parseFloat(amount) : Number(amount || 0);
  const formatted = formatINR(Math.abs(num));

  const sizeStyles = {
    sm: 'text-xs font-medium',
    md: 'text-sm font-semibold',
    lg: 'text-lg font-bold',
    xl: 'text-2xl font-serif font-semibold tracking-tight',
    '2xl': 'text-3xl sm:text-4xl font-serif font-semibold tracking-tight',
  };

  let signText = '';
  let colorClass = 'text-ink-950 [.theme-forensic_&]:text-slate-100';

  if (num === 0) {
    // Zero carries no direction: never render "-₹0.00" or "+₹0.00"
  } else if (sign === 'plus' || (sign === 'auto' && num > 0)) {
    signText = '+';
    if (colored) colorClass = 'text-forest-800 [.theme-forensic_&]:text-emerald-400';
  } else if (sign === 'minus' || num < 0) {
    // A negative amount always shows its sign (e.g. the clearing account), whatever `sign` says
    signText = '-';
    if (colored) colorClass = 'text-copper-700 [.theme-forensic_&]:text-rose-400';
  }

  return (
    <span className={`tabular-nums whitespace-nowrap ${sizeStyles[size]} ${colorClass} ${className}`}>
      {signText}
      {formatted}
    </span>
  );
};

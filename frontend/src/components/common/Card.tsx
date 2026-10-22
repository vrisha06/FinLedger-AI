import React from 'react';

export type CardVariant =
  | 'forest'
  | 'evergreen'
  | 'forensic'
  | 'mist'
  | 'sage'
  | 'selected'
  | 'outlined'
  | 'paper'
  | 'parchment'
  | 'clay'
  | 'passbook';

interface CardProps {
  children: React.ReactNode;
  title?: string | React.ReactNode;
  subtitle?: string | React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  variant?: CardVariant;
  glow?: 'emerald' | 'amber' | 'rose' | 'none';
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  action,
  className = '',
  variant = 'mist',
  glow = 'none',
}) => {
  // Border accent indication
  const borderStyles = {
    emerald: 'border-forest-600/90 [.theme-forensic_&]:border-emerald-500/50',
    amber: 'border-amber-600/80 [.theme-forensic_&]:border-amber-500/50',
    rose: 'border-rose-600/80 [.theme-forensic_&]:border-rose-500/50',
    none: 'border-eucalyptus-300 [.theme-forensic_&]:border-forensic-700',
  };

  const variantStyles: Record<CardVariant, string> = {
    forest: 'bg-gradient-to-br from-forest-900 via-forest-800 to-forest-900 text-white border-forest-950 shadow-hero',
    evergreen: 'bg-forest-700 text-white border-forest-900 shadow-md',
    forensic: 'bg-forensic-850 text-slate-100 border-forensic-700 shadow-sm',
    mist: 'bg-mist-100 text-ink-900 border-eucalyptus-300 shadow-atelier',
    sage: 'bg-sage-200 text-forest-950 border-eucalyptus-400 shadow-atelier',
    selected: 'bg-forest-800 text-white border-2 border-eucalyptus-300 border-l-4 border-l-sage-200 shadow-hero',
    outlined: 'bg-mist-50 text-ink-900 border-2 border-forest-700 shadow-sm',
    paper: 'bg-surface border-eucalyptus-300 text-ink-900 shadow-atelier',
    parchment: 'bg-parchment border-eucalyptus-300 text-ink-900',
    clay: 'bg-clay-100 border-copper-300 text-copper-950',
    passbook: 'bg-mist-50 border-eucalyptus-300 text-ink-900 passbook-ruled shadow-atelier',
  };

  const headerBgStyles: Record<CardVariant, string> = {
    forest: 'bg-forest-950 border-b border-forest-800 text-white',
    evergreen: 'bg-forest-800 border-b border-forest-900 text-white',
    forensic: 'bg-forensic-900 border-b border-forensic-700 text-white',
    mist: 'bg-forest-900 border-b border-forest-950 text-white',
    sage: 'bg-forest-800 border-b border-forest-900 text-white',
    selected: 'bg-forest-950 border-b border-forest-900 text-white',
    outlined: 'bg-forest-800 border-b border-forest-900 text-white',
    paper: 'bg-mist-100 border-b border-eucalyptus-300 text-forest-950',
    parchment: 'bg-sage-200 border-b border-eucalyptus-300 text-forest-950',
    clay: 'bg-clay-200 border-b border-copper-300 text-copper-950',
    passbook: 'bg-forest-900 border-b border-forest-950 text-white',
  };

  const isDarkHeader = ['forest', 'evergreen', 'forensic', 'mist', 'sage', 'selected', 'outlined', 'passbook'].includes(variant);

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${variantStyles[variant]} ${borderStyles[glow]} ${className} [.theme-forensic_&]:bg-forensic-850 [.theme-forensic_&]:border-forensic-700 [.theme-forensic_&]:text-slate-100 [.theme-forensic_&]:shadow-none`}
    >
      {(title || action) && (
        <div
          className={`px-5 py-3.5 flex items-center justify-between gap-4 ${headerBgStyles[variant]} [.theme-forensic_&]:bg-forensic-900 [.theme-forensic_&]:border-forensic-700`}
        >
          <div>
            {typeof title === 'string' ? (
              <h3 className={`text-base font-serif font-semibold ${isDarkHeader ? 'text-white' : 'text-forest-950'} [.theme-forensic_&]:font-sans [.theme-forensic_&]:text-sm [.theme-forensic_&]:text-slate-200`}>
                {title}
              </h3>
            ) : (
              title
            )}
            {subtitle && (
              <p className={`text-xs mt-0.5 ${isDarkHeader ? 'text-sage-100' : 'text-forest-800'} [.theme-forensic_&]:text-slate-400`}>
                {subtitle}
              </p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className="p-4 sm:p-5">{children}</div>
    </div>
  );
};

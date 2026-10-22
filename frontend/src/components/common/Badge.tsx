import React from 'react';

export type BadgeVariant =
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'neutral'
  | 'purple'
  | 'copper'
  | 'forest'
  | 'evergreen'
  | 'sage'
  | 'mist'
  | 'gold'
  | 'clay';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    success:
      'bg-forest-50 text-forest-800 border-forest-200 [.theme-forensic_&]:bg-emerald-950/70 [.theme-forensic_&]:text-emerald-300 [.theme-forensic_&]:border-emerald-700/60',
    warning:
      'bg-amber-50 text-amber-900 border-amber-200 [.theme-forensic_&]:bg-amber-950/70 [.theme-forensic_&]:text-amber-300 [.theme-forensic_&]:border-amber-700/60',
    danger:
      'bg-rose-50 text-rose-900 border-rose-200 [.theme-forensic_&]:bg-rose-950/70 [.theme-forensic_&]:text-rose-300 [.theme-forensic_&]:border-rose-700/60',
    info:
      'bg-sky-50 text-sky-900 border-sky-200 [.theme-forensic_&]:bg-sky-950/70 [.theme-forensic_&]:text-sky-300 [.theme-forensic_&]:border-sky-700/60',
    neutral:
      'bg-paper-200 text-ink-700 border-hairline [.theme-forensic_&]:bg-[#18202b] [.theme-forensic_&]:text-slate-300 [.theme-forensic_&]:border-[#2a3648]',
    purple:
      'bg-purple-50 text-purple-900 border-purple-200 [.theme-forensic_&]:bg-purple-950/70 [.theme-forensic_&]:text-purple-300 [.theme-forensic_&]:border-purple-700/60',
    copper:
      'bg-copper-50 text-copper-800 border-copper-200 [.theme-forensic_&]:bg-orange-950/70 [.theme-forensic_&]:text-orange-300 [.theme-forensic_&]:border-orange-700/60',
    forest:
      'bg-forest-800 text-white border-forest-950 font-bold [.theme-forensic_&]:bg-emerald-900 [.theme-forensic_&]:text-white [.theme-forensic_&]:border-emerald-700',
    evergreen:
      'bg-forest-700 text-white border-forest-900 font-bold [.theme-forensic_&]:bg-emerald-800 [.theme-forensic_&]:text-white [.theme-forensic_&]:border-emerald-600',
    sage:
      'bg-sage-200 text-forest-950 border-eucalyptus-400 font-bold [.theme-forensic_&]:bg-emerald-950/50 [.theme-forensic_&]:text-emerald-300 [.theme-forensic_&]:border-emerald-800',
    mist:
      'bg-mist-100 text-forest-900 border-eucalyptus-300 font-bold [.theme-forensic_&]:bg-emerald-950/60 [.theme-forensic_&]:text-emerald-200 [.theme-forensic_&]:border-emerald-800',
    gold:
      'bg-[#F8F3E5] text-[#95611C] border-[#DFD0A8] [.theme-forensic_&]:bg-amber-950/60 [.theme-forensic_&]:text-amber-300 [.theme-forensic_&]:border-amber-700',
    clay:
      'bg-clay-100 text-copper-900 border-copper-200 [.theme-forensic_&]:bg-orange-950/60 [.theme-forensic_&]:text-orange-300 [.theme-forensic_&]:border-orange-800',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-1.5 py-0.5 font-semibold',
    md: 'text-xs px-2 py-0.5 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center rounded border tracking-wide uppercase whitespace-nowrap ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};

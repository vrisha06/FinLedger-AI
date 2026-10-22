import React from 'react';
import { formatDate } from '../../utils/formatters';

interface DateDisplayProps {
  date: string | null | undefined;
  className?: string;
}

export const DateDisplay: React.FC<DateDisplayProps> = ({ date, className = '' }) => {
  return (
    <span className={`text-ink-500 [.theme-forensic_&]:text-slate-400 text-xs tabular-nums whitespace-nowrap ${className}`}>
      {formatDate(date)}
    </span>
  );
};

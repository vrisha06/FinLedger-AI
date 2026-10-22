import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center border border-dashed border-hairline rounded-md bg-paper-50 [.theme-forensic_&]:border-forensic-700 [.theme-forensic_&]:bg-forensic-850 ${className}`}
    >
      <div className="p-3 bg-paper-200 rounded-full text-ink-600 mb-3 [.theme-forensic_&]:bg-forensic-750 [.theme-forensic_&]:text-slate-400">
        {icon || <Inbox className="w-6 h-6" />}
      </div>
      <h4 className="text-sm font-serif font-semibold text-ink-900 [.theme-forensic_&]:font-sans [.theme-forensic_&]:text-slate-200">
        {title}
      </h4>
      <p className="text-xs text-ink-500 max-w-sm mt-1 mb-4 font-sans [.theme-forensic_&]:text-slate-400">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};

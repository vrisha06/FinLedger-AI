import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, action }) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-hairline [.theme-forensic_&]:border-forensic-700">
      <div>
        <h1 className="text-2xl sm:text-3xl font-serif font-semibold tracking-tight text-ink-950 [.theme-forensic_&]:font-sans [.theme-forensic_&]:text-xl [.theme-forensic_&]:font-bold [.theme-forensic_&]:text-slate-100">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-ink-600 font-sans mt-1.5 max-w-3xl leading-relaxed [.theme-forensic_&]:text-slate-400">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};

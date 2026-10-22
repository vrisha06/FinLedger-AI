import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`p-4 rounded-md bg-rose-50 border border-rose-200 text-rose-900 flex items-start justify-between gap-3 [.theme-forensic_&]:bg-rose-950/40 [.theme-forensic_&]:border-rose-800/60 [.theme-forensic_&]:text-rose-200 ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-rose-600 [.theme-forensic_&]:text-rose-400 shrink-0 mt-0.5" />
        <p role="alert" className="text-sm text-rose-800 [.theme-forensic_&]:text-rose-200 font-sans">
          {message}
        </p>
      </div>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="shrink-0 text-rose-800 border-rose-300 hover:bg-rose-100 [.theme-forensic_&]:text-rose-300 [.theme-forensic_&]:border-rose-500/30 [.theme-forensic_&]:hover:bg-rose-500/20"
        >
          Retry
        </Button>
      )}
    </div>
  );
};

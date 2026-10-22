import React, { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'md',
}) => {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Move focus into the dialog on open and hand it back to the trigger on close
  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthStyles = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-ink-950/60 backdrop-blur-[1px] transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div
        className={`relative w-full ${maxWidthStyles[maxWidth]} bg-mist-50 border-2 border-forest-800 rounded-lg p-5 sm:p-6 shadow-hero z-10 text-ink-900 focus:outline-none [.theme-forensic_&]:bg-forensic-850 [.theme-forensic_&]:border-forensic-700 [.theme-forensic_&]:text-slate-100`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={dialogRef}
      >
        <div className="flex items-start justify-between gap-4 -mx-5 -mt-5 sm:-mx-6 sm:-mt-6 mb-5 px-5 py-4 bg-forest-900 border-b border-forest-950 rounded-t-md text-white [.theme-forensic_&]:bg-forensic-900 [.theme-forensic_&]:border-forensic-700">
          <div>
            <h3 id={titleId} className="text-base sm:text-lg font-serif font-bold text-white [.theme-forensic_&]:text-slate-100 [.theme-forensic_&]:font-sans">
              {title}
            </h3>
            {description && (
              <p className="text-xs text-sage-100 [.theme-forensic_&]:text-slate-400 mt-1 leading-relaxed">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded text-sage-200 hover:text-white hover:bg-forest-800 transition-colors [.theme-forensic_&]:text-slate-400 [.theme-forensic_&]:hover:text-white [.theme-forensic_&]:hover:bg-forensic-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>{children}</div>
      </div>
    </div>
  );
};

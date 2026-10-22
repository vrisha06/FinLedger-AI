import React from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost' | 'evergreen' | 'sage';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-sans font-medium rounded transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed select-none text-xs sm:text-sm whitespace-nowrap cursor-pointer';

  // Explicit CSS class mapping backed by @layer components in index.css
  const variantStyles: Record<ButtonVariant, string> = {
    primary:
      'btn-primary bg-forest-800 text-white hover:bg-forest-700 active:bg-forest-900 border border-forest-950 shadow-sm focus:ring-forest-600',
    evergreen:
      'bg-forest-700 text-white hover:bg-forest-600 active:bg-forest-800 border border-forest-900 shadow-sm focus:ring-forest-600 font-semibold',
    secondary:
      'btn-secondary bg-mist-100 text-forest-950 hover:bg-sage-200 active:bg-sage-300 border border-eucalyptus-300 shadow-xs focus:ring-forest-600 font-semibold',
    sage:
      'bg-sage-200 text-forest-950 hover:bg-sage-300 active:bg-sage-400 border border-eucalyptus-400 focus:ring-forest-600 font-semibold',
    danger:
      'btn-danger bg-semantic-danger text-white hover:bg-rose-700 active:bg-rose-800 border border-rose-900 focus:ring-rose-500',
    outline:
      'btn-outline bg-transparent text-forest-900 hover:bg-mist-100 border border-forest-700 focus:ring-forest-600 font-semibold',
    ghost:
      'btn-ghost bg-transparent text-forest-800 hover:text-forest-950 hover:bg-mist-100 border border-transparent focus:ring-forest-600 font-medium',
  };

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-xs sm:text-sm px-4 py-2 gap-2',
    lg: 'text-sm px-5 py-2.5 gap-2.5',
  };

  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-current shrink-0" />
      ) : (
        leftIcon && <span className="shrink-0">{leftIcon}</span>
      )}
      <span className="font-medium">{children}</span>
      {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
    </button>
  );
};

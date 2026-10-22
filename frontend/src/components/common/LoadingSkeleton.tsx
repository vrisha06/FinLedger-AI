import React from 'react';

interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  rows = 3,
  className = '',
}) => {
  return (
    <div className={`space-y-3 animate-pulse ${className}`}>
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className="h-9 bg-paper-200 border border-hairline-subtle rounded w-full [.theme-forensic_&]:bg-forensic-750 [.theme-forensic_&]:border-forensic-700"
        />
      ))}
    </div>
  );
};

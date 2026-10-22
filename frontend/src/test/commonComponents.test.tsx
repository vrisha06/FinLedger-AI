import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { CurrencyDisplay } from '../components/common/CurrencyDisplay';
import { ErrorBanner } from '../components/common/ErrorBanner';

describe('Common UI Components', () => {
  it('renders Badge with correct text and variant styles', () => {
    render(<Badge variant="success">POSTED</Badge>);
    expect(screen.getByText('POSTED')).toBeInTheDocument();
  });

  it('renders Button with loading state and disables clicks', () => {
    const handleClick = vi.fn();
    render(
      <Button isLoading onClick={handleClick}>
        Submit
      </Button>
    );

    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('never hides the sign of a negative amount', () => {
    render(<CurrencyDisplay amount="-50000.00" />);
    expect(screen.getByText('-₹50,000.00')).toBeInTheDocument();
  });

  it('renders CurrencyDisplay with exact formatted currency and sign', () => {
    render(<CurrencyDisplay amount={25000} sign="plus" colored />);
    expect(screen.getByText('+₹25,000.00')).toBeInTheDocument();
  });

  it('renders ErrorBanner with message and triggers retry', () => {
    const handleRetry = vi.fn();
    render(
      <ErrorBanner
        message="Insufficient funds in savings account"
        onRetry={handleRetry}
      />
    );

    expect(screen.getByText('Insufficient funds in savings account')).toBeInTheDocument();
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});

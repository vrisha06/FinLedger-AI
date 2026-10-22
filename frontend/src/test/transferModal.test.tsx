import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AxiosError, AxiosHeaders } from 'axios';
import { TransferModal } from '../components/customer/TransferModal';
import { Account } from '../types/api';
import { transfersApi } from '../api/transfers';

const previewSpy = vi.spyOn(transfersApi, 'previewTransfer');
const createSpy = vi.spyOn(transfersApi, 'createTransfer');

const mockAccounts: Account[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    customer_id: 'cust-1',
    account_number: 'INR-SAV-123456',
    account_type: 'SAVINGS',
    currency: 'INR',
    cached_balance: '50000.00',
    status: 'ACTIVE',
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const fillAndReview = (amount: string, recipient: string) => {
  fireEvent.change(screen.getByLabelText('Amount'), { target: { value: amount } });
  fireEvent.change(screen.getByLabelText('To account number'), { target: { value: recipient } });
  fireEvent.click(screen.getByRole('button', { name: /review transfer/i }));
};

const httpError = (status: number | null) => {
  const err = new AxiosError('failed');
  if (status !== null) {
    err.response = {
      status,
      data: { detail: 'Insufficient funds' },
      statusText: '',
      headers: {},
      config: { headers: new AxiosHeaders() },
    };
  }
  return err;
};

describe('TransferModal Component', () => {
  beforeEach(() => {
    previewSpy.mockReset().mockResolvedValue({
      source_account_id: '11111111-1111-1111-1111-111111111111',
      source_account_number: 'INR-SAV-123456',
      source_available_balance: '50000.00',
      destination_account_id: '33333333-3333-3333-3333-333333333333',
      recipient_legal_name: 'Aarav Sharma',
      masked_account_number: 'ACC-SAV-••••77',
      account_type: 'SAVINGS',
      is_first_time_recipient: true,
      prior_transfers_count: 0,
      amount: '15000.00',
      currency: 'INR',
      validation_status: 'VERIFIED_ELIGIBLE',
      advisory_warnings: ['First-Time Recipient: You have not transferred funds to this beneficiary previously.'],
      verification_provider: 'Internal FinLedger-AI Account Holder Verification',
    });
    createSpy.mockReset();
  });

  it('validates strictly positive amount and rejects zero or negative amounts', async () => {
    render(<TransferModal isOpen={true} onClose={vi.fn()} accounts={mockAccounts} />);
    fillAndReview('0', 'INR-SAV-999999');

    await waitFor(() => {
      expect(screen.getByText(/Enter an amount greater than ₹0.00/i)).toBeInTheDocument();
    });
    expect(previewSpy).not.toHaveBeenCalled();
  });

  it('rejects same-account transfer attempts', async () => {
    render(<TransferModal isOpen={true} onClose={vi.fn()} accounts={mockAccounts} />);
    fillAndReview('5000.00', mockAccounts[0].account_number.toLowerCase());

    await waitFor(() => {
      expect(screen.getByText(/source and recipient must be different accounts/i)).toBeInTheDocument();
    });
    expect(previewSpy).not.toHaveBeenCalled();
  });

  it('navigates to review step with valid inputs and displays idempotency key', async () => {
    render(<TransferModal isOpen={true} onClose={vi.fn()} accounts={mockAccounts} />);
    fillAndReview('15000', 'inr-sav-999999');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Send ₹15,000.00/i })).toBeInTheDocument();
    });
    expect(previewSpy).toHaveBeenCalledWith({
      source_account_id: mockAccounts[0].id,
      destination_account_number: 'INR-SAV-999999',
      amount: '15000.00',
    });
    expect(screen.getByText(/Idempotency key/i)).toBeInTheDocument();
    expect(screen.getAllByText(/₹15,000.00/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/PayeeGuard check/i)).toBeInTheDocument();
    expect(screen.getByText(/Aarav Sharma/i)).toBeInTheDocument();
    expect(screen.getByText(/ACC-SAV-••••77/i)).toBeInTheDocument();
    expect(screen.getAllByText(/First-Time Recipient/i).length).toBeGreaterThanOrEqual(1);
  });

  it('uses a fresh idempotency key after a definitive rejection', async () => {
    createSpy.mockRejectedValueOnce(httpError(400)).mockRejectedValueOnce(httpError(400));
    render(<TransferModal isOpen={true} onClose={vi.fn()} accounts={mockAccounts} />);
    fillAndReview('15000', 'INR-SAV-999999');
    await screen.findByRole('button', { name: /Send ₹15,000.00/i });

    fireEvent.click(screen.getByRole('button', { name: /Send ₹15,000.00/i }));
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }));
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(2));

    const [firstKey, secondKey] = createSpy.mock.calls.map((call) => call[1]);
    expect(firstKey).not.toEqual(secondKey);
  });

  it('keeps the same idempotency key after an ambiguous network failure', async () => {
    createSpy.mockRejectedValueOnce(httpError(null)).mockRejectedValueOnce(httpError(null));
    render(<TransferModal isOpen={true} onClose={vi.fn()} accounts={mockAccounts} />);
    fillAndReview('15000', 'INR-SAV-999999');
    await screen.findByRole('button', { name: /Send ₹15,000.00/i });

    fireEvent.click(screen.getByRole('button', { name: /Send ₹15,000.00/i }));
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }));
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(2));

    const [firstKey, secondKey] = createSpy.mock.calls.map((call) => call[1]);
    expect(firstKey).toEqual(secondKey);
  });
});

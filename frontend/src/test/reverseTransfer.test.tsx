import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ReverseTransferPanel } from '../components/staff/ReverseTransferPanel';
import { transfersApi } from '../api/transfers';
import { TransferRequest } from '../types/api';

const posted: TransferRequest = {
  id: 'tx-1',
  idempotency_key: 'k',
  source_account_id: 'a1',
  destination_account_id: 'a2',
  amount: '2500.00',
  currency: 'INR',
  status: 'POSTED',
  created_at: new Date().toISOString(),
};

describe('ReverseTransferPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('requires a reason and an explicit confirmation before posting a reversal', async () => {
    vi.spyOn(transfersApi, 'getTransfer').mockResolvedValue(posted);
    const reverseSpy = vi.spyOn(transfersApi, 'reverseTransfer').mockResolvedValue({ ...posted, id: 'rev-1' });
    const onReversed = vi.fn();
    render(<ReverseTransferPanel transferId="tx-1" onReversed={onReversed} />);

    const start = await screen.findByRole('button', { name: /reverse transfer/i });
    expect(start).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/reason for the correction/i), { target: { value: 'Dispute upheld after review' } });
    fireEvent.click(screen.getByRole('button', { name: /reverse transfer/i }));
    expect(reverseSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /confirm reversal/i }));
    await waitFor(() => expect(reverseSpy).toHaveBeenCalledWith('tx-1', 'Dispute upheld after review'));
    expect(onReversed).toHaveBeenCalled();
    expect(await screen.findByText(/has been reversed/i)).toBeInTheDocument();
  });

  it('does not offer a reversal for transfers that are already reversed', async () => {
    vi.spyOn(transfersApi, 'getTransfer').mockResolvedValue({ ...posted, status: 'REVERSED' });
    render(<ReverseTransferPanel transferId="tx-1" />);
    expect(await screen.findByText(/has been reversed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reverse transfer/i })).toBeNull();
  });
});

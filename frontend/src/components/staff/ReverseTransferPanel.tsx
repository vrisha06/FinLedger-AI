import React, { useEffect, useState } from 'react';
import { Button } from '../common/Button';
import { CurrencyDisplay } from '../common/CurrencyDisplay';
import { ErrorBanner } from '../common/ErrorBanner';
import { transfersApi } from '../../api/transfers';
import { getErrorMessage } from '../../api/client';
import { TransferRequest } from '../../types/api';

interface ReverseTransferPanelProps {
  transferId: string;
  onReversed?: (reversal: TransferRequest) => void;
}

const MIN_REASON = 10; // backend TransferReversalRequest.reason min_length

/**
 * Admin-only correction: posts a new balanced CORRECTION_REVERSAL in the opposite direction.
 * The original transfer's ledger entries are never edited.
 */
export const ReverseTransferPanel: React.FC<ReverseTransferPanelProps> = ({ transferId, onReversed }) => {
  const [transfer, setTransfer] = useState<TransferRequest | null>(null);
  const [reason, setReason] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTransfer(null);
    setConfirming(false);
    setError(null);
    transfersApi.getTransfer(transferId).then(setTransfer).catch((err) => setError(getErrorMessage(err)));
  }, [transferId]);

  const submit = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const reversal = await transfersApi.reverseTransfer(transferId, reason.trim());
      setTransfer((t) => (t ? { ...t, status: 'REVERSED' } : t));
      setConfirming(false);
      setReason('');
      onReversed?.(reversal);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
      setConfirming(false);
    } finally {
      setIsSaving(false);
    }
  };

  if (!transfer) {
    return error ? <ErrorBanner message={error} /> : null;
  }

  if (transfer.status === 'REVERSED') {
    return (
      <p className="text-sm text-slate-300">
        This transfer has been reversed. The correcting entry is in the ledger and the audit trail.
      </p>
    );
  }

  if (transfer.status !== 'POSTED') {
    return <p className="text-sm text-slate-400">Only posted transfers can be reversed. This one was declined.</p>;
  }

  return (
    <div className="space-y-3 text-sm">
      {error && <ErrorBanner message={error} />}
      <p className="text-slate-300">
        Posts a new entry moving <CurrencyDisplay amount={transfer.amount} size="sm" className="text-slate-100" /> back
        from the recipient to the sender. The original entries stay as they are, and this can&apos;t be undone.
      </p>
      <label htmlFor={`reverse-reason-${transferId}`} className="block text-slate-300">
        Reason for the correction
      </label>
      <textarea
        id={`reverse-reason-${transferId}`}
        rows={2}
        value={reason}
        onChange={(e) => {
          setReason(e.target.value);
          setConfirming(false);
        }}
        placeholder="For example: dispute upheld, customer did not authorise this payment."
        className="w-full bg-forensic-900 border border-forensic-700 rounded px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 resize-none"
      />
      <div className="flex justify-end gap-2">
        {confirming ? (
          <>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={submit} isLoading={isSaving}>
              Confirm reversal
            </Button>
          </>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            disabled={reason.trim().length < MIN_REASON}
            onClick={() => setConfirming(true)}
          >
            Reverse transfer
          </Button>
        )}
      </div>
    </div>
  );
};

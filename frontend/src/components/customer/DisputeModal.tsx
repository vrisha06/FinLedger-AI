import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ErrorBanner } from '../common/ErrorBanner';
import { CurrencyDisplay } from '../common/CurrencyDisplay';
import { disputesApi } from '../../api/disputes';
import { getErrorMessage } from '../../api/client';
import { DisputeCategory } from '../../types/api';
import { CheckCircle2 } from 'lucide-react';

export const DISPUTE_CATEGORY_LABELS: Record<DisputeCategory, string> = {
  UNAUTHORIZED: "I didn't make this transfer",
  INCORRECT_AMOUNT: 'The amount is wrong',
  NOT_RECEIVED: "The recipient didn't receive it",
  SUSPECTED_FRAUD: 'I think I was tricked or scammed',
  OTHER: 'Something else',
};

const MIN_DESCRIPTION = 10; // backend DisputeCreateRequest.description min_length

interface DisputeModalProps {
  isOpen: boolean;
  onClose: () => void;
  transferId: string;
  transferAmount?: string | number;
  onDisputeCreated?: () => void;
}

const inputClass =
  'w-full bg-surface border border-hairline rounded px-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 transition-colors';

export const DisputeModal: React.FC<DisputeModalProps> = ({
  isOpen,
  onClose,
  transferId,
  transferAmount,
  onDisputeCreated,
}) => {
  const [category, setCategory] = useState<DisputeCategory>('UNAUTHORIZED');
  const [description, setDescription] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim().length < MIN_DESCRIPTION) {
      setError(`Tell us what happened in at least ${MIN_DESCRIPTION} characters.`);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await disputesApi.createDispute({ transfer_request_id: transferId, category, description: description.trim() });
      setIsSuccess(true);
      onDisputeCreated?.();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setDescription('');
    setCategory('UNAUTHORIZED');
    setError(null);
    setIsSuccess(false);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isSuccess ? 'Dispute opened' : 'Dispute a transfer'}
      description={
        isSuccess
          ? 'Our investigations team will review it. You can follow its progress on the Disputes page.'
          : "Tell us what's wrong. Opening a dispute doesn't change your balance; any correction is posted as a new, balanced entry."
      }
      maxWidth="md"
    >
      {error && <ErrorBanner message={error} className="mb-4" />}

      {isSuccess ? (
        <div className="space-y-4">
          <div className="p-5 rounded-md bg-surface border border-hairline flex items-center gap-3">
            <CheckCircle2 className="w-6 h-6 text-forest-800 shrink-0" aria-hidden="true" />
            <p className="text-sm text-ink-800">{DISPUTE_CATEGORY_LABELS[category]}</p>
          </div>
          <div className="flex justify-end">
            <Button variant="primary" size="sm" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <dl className="p-4 rounded-md bg-surface border border-hairline text-sm space-y-1.5">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Transfer</dt>
              <dd className="font-mono text-xs text-ink-950 truncate max-w-[240px]" title={transferId}>
                {transferId}
              </dd>
            </div>
            {transferAmount !== undefined && (
              <div className="flex justify-between gap-4">
                <dt className="text-ink-600">Amount</dt>
                <dd>
                  <CurrencyDisplay amount={transferAmount} size="sm" />
                </dd>
              </div>
            )}
          </dl>

          <div>
            <label htmlFor="dispute-category" className="block text-sm font-medium text-ink-800 mb-1">
              What&apos;s the problem?
            </label>
            <select
              id="dispute-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as DisputeCategory)}
              className={inputClass}
            >
              {(Object.keys(DISPUTE_CATEGORY_LABELS) as DisputeCategory[]).map((key) => (
                <option key={key} value={key}>
                  {DISPUTE_CATEGORY_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="dispute-description" className="block text-sm font-medium text-ink-800 mb-1">
              What happened?
            </label>
            <textarea
              id="dispute-description"
              rows={4}
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="For example: I don't recognise the recipient and didn't approve this payment."
              className={`${inputClass} resize-none`}
              required
            />
          </div>

          <div className="pt-3 border-t border-hairline flex items-center justify-end gap-2.5">
            <Button variant="secondary" size="sm" type="button" onClick={handleClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isLoading}>
              Open dispute
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};

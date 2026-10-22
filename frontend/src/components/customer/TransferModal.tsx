import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { CurrencyDisplay } from '../common/CurrencyDisplay';
import { ErrorBanner } from '../common/ErrorBanner';
import { Account, TransferRequest, PayeePreviewResponse } from '../../types/api';
import { transfersApi } from '../../api/transfers';
import { generateUUID, parseAmountInput } from '../../utils/formatters';
import { getErrorMessage, isDefinitiveRejection } from '../../api/client';
import { ArrowRight, ArrowLeft, CheckCircle2, ShieldCheck, UserCheck, AlertTriangle } from 'lucide-react';

interface TransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  accounts: Account[];
  onTransferSuccess?: () => void;
}

type TransferStep = 1 | 2 | 3;

const STEPS: Record<TransferStep, string> = {
  1: 'Details',
  2: 'Check and confirm',
  3: 'Receipt',
};

const inputClass =
  'w-full bg-surface border border-hairline rounded px-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 transition-colors';

export const TransferModal: React.FC<TransferModalProps> = ({ isOpen, onClose, accounts, onTransferSuccess }) => {
  const eligibleSources = accounts.filter(
    (a) => a.status === 'ACTIVE' && a.account_type !== 'INTERNAL_CLEARING' && a.account_type !== 'INVESTMENT'
  );

  const [step, setStep] = useState<TransferStep>(1);
  const [sourceAccountId, setSourceAccountId] = useState<string>('');
  const [recipientNumber, setRecipientNumber] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [memo, setMemo] = useState<string>('');

  // One key per transfer attempt: replays of the same attempt can never post twice
  const [idempotencyKey, setIdempotencyKey] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<TransferRequest | null>(null);
  const [previewData, setPreviewData] = useState<PayeePreviewResponse | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (eligibleSources.length > 0 && !sourceAccountId) {
        setSourceAccountId(eligibleSources[0].id);
      }
      setIdempotencyKey(generateUUID());
      setStep(1);
      setError(null);
      setReceipt(null);
      setPreviewData(null);
    }
  }, [isOpen]);

  const selectedSource = accounts.find((a) => a.id === sourceAccountId) || eligibleSources[0];
  const ownOtherAccounts = eligibleSources.filter((a) => a.id !== selectedSource?.id);
  const canonicalAmount = parseAmountInput(amount);

  const handleProceedToReview = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);

    if (!canonicalAmount) {
      setError('Enter an amount greater than ₹0.00, with at most two decimal places.');
      return;
    }

    const recipient = recipientNumber.trim().toUpperCase();
    if (!recipient) {
      setError("Enter the recipient's account number.");
      return;
    }

    if (selectedSource && recipient === selectedSource.account_number.toUpperCase()) {
      setError('Choose a different account to send to. The source and recipient must be different accounts.');
      return;
    }

    setIsPreviewLoading(true);
    try {
      // PayeeGuard resolves the number, confirms the account holder and checks funds before anything moves
      const preview = await transfersApi.previewTransfer({
        source_account_id: selectedSource.id,
        destination_account_number: recipient,
        amount: canonicalAmount,
      });
      setPreviewData(preview);
      setStep(2);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleExecuteTransfer = async () => {
    if (!previewData || !canonicalAmount) return;
    setIsLoading(true);
    setError(null);

    try {
      const result = await transfersApi.createTransfer(
        {
          source_account_id: selectedSource.id,
          destination_account_id: previewData.destination_account_id,
          amount: canonicalAmount,
          currency: 'INR',
          memo: memo.trim() || undefined,
        },
        idempotencyKey
      );

      setReceipt(result);
      setStep(3);
      onTransferSuccess?.();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
      // A rejected attempt is recorded under its key; a corrected retry is a new attempt.
      // Ambiguous failures (network, 5xx) keep the key so retrying is always safe.
      if (isDefinitiveRejection(err)) {
        setIdempotencyKey(generateUUID());
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetForNewTransfer = () => {
    setIdempotencyKey(generateUUID());
    setAmount('');
    setMemo('');
    setRecipientNumber('');
    setStep(1);
    setError(null);
    setReceipt(null);
    setPreviewData(null);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={step === 3 ? 'Transfer sent' : 'Send money'}
      description={`Step ${step} of 3: ${STEPS[step]}`}
      maxWidth="lg"
    >
      <ol className="mb-5 grid grid-cols-3 gap-2" aria-label="Transfer progress">
        {([1, 2, 3] as TransferStep[]).map((n) => (
          <li key={n} aria-current={n === step ? 'step' : undefined}>
            <span className={`block h-1 rounded-full ${n <= step ? 'bg-forest-800' : 'bg-parchment-300'}`} />
            <span className={`block mt-1.5 text-xs ${n === step ? 'font-semibold text-forest-900' : 'text-ink-500'}`}>
              {STEPS[n]}
            </span>
          </li>
        ))}
      </ol>

      {error && <ErrorBanner message={error} className="mb-4" />}

      {step === 1 && (
        <form onSubmit={handleProceedToReview} noValidate className="space-y-4">
          <div>
            <label htmlFor="transfer-source" className="block text-sm font-medium text-ink-800 mb-1">
              From
            </label>
            <select
              id="transfer-source"
              value={selectedSource?.id || ''}
              onChange={(e) => setSourceAccountId(e.target.value)}
              className={inputClass}
            >
              {eligibleSources.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.account_number}, available ₹
                  {Number(acc.cached_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="transfer-recipient" className="block text-sm font-medium text-ink-800 mb-1">
              To account number
            </label>
            <input
              id="transfer-recipient"
              type="text"
              autoComplete="off"
              value={recipientNumber}
              onChange={(e) => setRecipientNumber(e.target.value)}
              placeholder="INR-SAV-1A2B3C4D"
              className={`${inputClass} font-mono uppercase placeholder:normal-case`}
              aria-describedby="transfer-recipient-hint"
            />
            <p id="transfer-recipient-hint" className="text-xs text-ink-500 mt-1">
              We&apos;ll show you the account holder&apos;s name before any money moves.
            </p>
            {ownOtherAccounts.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-600">
                <span>Your accounts:</span>
                {ownOtherAccounts.map((acc) => (
                  <button
                    key={acc.id}
                    type="button"
                    onClick={() => setRecipientNumber(acc.account_number)}
                    className="font-mono px-2 py-0.5 rounded border border-hairline bg-parchment-50 hover:border-forest-700 cursor-pointer"
                  >
                    {acc.account_number}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="transfer-amount" className="block text-sm font-medium text-ink-800 mb-1">
              Amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-ink-500 text-sm" aria-hidden="true">₹</span>
              <input
                id="transfer-amount"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className={`${inputClass} pl-7 tabular-nums`}
              />
            </div>
          </div>

          <div>
            <label htmlFor="transfer-memo" className="block text-sm font-medium text-ink-800 mb-1">
              Note <span className="font-normal text-ink-500">(optional)</span>
            </label>
            <input
              id="transfer-memo"
              type="text"
              maxLength={255}
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="What's this for?"
              className={inputClass}
            />
          </div>

          <div className="pt-3 border-t border-hairline flex items-center justify-end gap-3">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              isLoading={isPreviewLoading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Review transfer
            </Button>
          </div>
        </form>
      )}

      {step === 2 && previewData && (
        <div className="space-y-4">
          <section className="p-4 rounded-md bg-forest-900 text-white space-y-3" aria-label="PayeeGuard check">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-semibold">
                <ShieldCheck className="w-4 h-4 text-forest-300" aria-hidden="true" /> PayeeGuard check
              </span>
              <span className="text-xs text-forest-200">
                {previewData.validation_status === 'VERIFIED_ELIGIBLE' ? 'Account verified' : previewData.validation_status}
              </span>
            </div>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <span className="block text-xs text-forest-200">You are paying</span>
                <span className="flex items-center gap-1.5 text-lg font-serif font-semibold">
                  <UserCheck className="w-4 h-4 text-forest-300 shrink-0" aria-hidden="true" />
                  {previewData.recipient_legal_name}
                </span>
              </div>
              <span className="font-mono text-sm text-sage-100">{previewData.masked_account_number}</span>
            </div>
            <p className="text-xs text-forest-100">
              {previewData.is_first_time_recipient
                ? "You haven't sent money to this account before."
                : `You've sent money to this account ${previewData.prior_transfers_count} ${previewData.prior_transfers_count === 1 ? 'time' : 'times'} before.`}
            </p>

            {previewData.advisory_warnings.length > 0 && (
              <div className="p-3 rounded bg-amber-950/60 border border-amber-500/50 text-amber-100 text-xs space-y-1" role="note">
                <span className="flex items-center gap-1 font-semibold text-amber-200">
                  <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" /> Before you send
                </span>
                <ul className="list-disc pl-4 space-y-0.5">
                  {previewData.advisory_warnings.map((warn) => (
                    <li key={warn}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <dl className="p-4 rounded-md bg-surface border border-hairline space-y-2.5 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">From</dt>
              <dd className="font-mono text-ink-950">{selectedSource?.account_number}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Amount</dt>
              <dd>
                <CurrencyDisplay amount={canonicalAmount ?? '0'} size="lg" className="text-forest-950" />
              </dd>
            </div>
            {memo && (
              <div className="flex justify-between gap-4">
                <dt className="text-ink-600">Note</dt>
                <dd className="text-ink-950 text-right">{memo}</dd>
              </div>
            )}
            <div className="flex justify-between gap-4 pt-2 border-t border-hairline-subtle text-xs">
              <dt className="text-ink-500">Idempotency key</dt>
              <dd className="font-mono text-ink-700 truncate max-w-[240px]" title={idempotencyKey}>
                {idempotencyKey}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-ink-500">
            If your connection drops, confirming again is safe: the key above makes sure this transfer posts once.
          </p>

          <div className="pt-3 border-t border-hairline flex items-center justify-between gap-3">
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={() => setStep(1)}
              leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
              disabled={isLoading}
            >
              Back
            </Button>
            <Button variant="primary" size="sm" onClick={handleExecuteTransfer} isLoading={isLoading}>
              {error ? 'Try again' : `Send ₹${Number(canonicalAmount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            </Button>
          </div>
        </div>
      )}

      {step === 3 && receipt && (
        <div className="space-y-4">
          <div className="p-6 rounded-md ledger-hero-green flex flex-col items-center gap-2 text-center">
            <CheckCircle2 className="w-8 h-8 text-forest-300" aria-hidden="true" />
            <CurrencyDisplay amount={receipt.amount} size="2xl" className="text-white" />
            <p className="text-sm text-sage-100">
              sent to {previewData?.recipient_legal_name ?? 'the recipient'}. The debit and credit were posted together.
            </p>
          </div>

          <dl className="p-4 rounded-md bg-surface border border-hairline space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Reference</dt>
              <dd className="font-mono text-xs text-ink-950 truncate max-w-[260px]" title={receipt.id}>
                {receipt.id}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Status</dt>
              <dd className="text-forest-800 font-semibold">{receipt.status === 'POSTED' ? 'Posted' : receipt.status}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Posted at</dt>
              <dd className="text-ink-950">
                {receipt.posted_at ? new Date(receipt.posted_at).toLocaleString('en-IN') : 'Just now'}
              </dd>
            </div>
          </dl>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-hairline">
            <Button variant="secondary" size="sm" onClick={handleResetForNewTransfer}>
              Send another
            </Button>
            <Button variant="primary" size="sm" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

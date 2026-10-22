import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ErrorBanner } from '../common/ErrorBanner';
import { Account } from '../../types/api';
import { accountsApi } from '../../api/accounts';
import { getErrorMessage } from '../../api/client';
import { parseAmountInput } from '../../utils/formatters';
import { ArrowDownCircle, CheckCircle2 } from 'lucide-react';
import { CurrencyDisplay } from '../common/CurrencyDisplay';

interface DepositModalProps {
  isOpen: boolean;
  onClose: () => void;
  account: Account | null;
  onDepositSuccess?: () => void;
}

const inputClass =
  'w-full bg-surface border border-hairline rounded px-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 transition-colors';

export const DepositModal: React.FC<DepositModalProps> = ({ isOpen, onClose, account, onDepositSuccess }) => {
  const [amount, setAmount] = useState<string>('50000.00');
  const [description, setDescription] = useState<string>('Opening deposit');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [depositedAmount, setDepositedAmount] = useState<string | null>(null);

  const handleDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account) return;

    setError(null);
    const canonical = parseAmountInput(amount);
    if (!canonical) {
      setError('Enter an amount greater than ₹0.00, with at most two decimal places.');
      return;
    }

    setIsLoading(true);
    try {
      await accountsApi.depositOpeningFunds(account.id, canonical, description.trim() || undefined);
      setDepositedAmount(canonical);
      onDepositSuccess?.();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setDepositedAmount(null);
    setError(null);
    onClose();
  };

  if (!account) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={depositedAmount ? 'Deposit added' : 'Add an opening deposit'}
      description="For this demo, deposits are drawn from the bank's internal clearing account, so the books stay balanced."
    >
      {error && <ErrorBanner message={error} className="mb-4" />}

      {depositedAmount ? (
        <div className="space-y-4">
          <div className="p-6 rounded-md ledger-hero-green flex flex-col items-center gap-2 text-center">
            <CheckCircle2 className="w-8 h-8 text-forest-300" aria-hidden="true" />
            <CurrencyDisplay amount={depositedAmount} size="2xl" className="text-white" />
            <p className="text-sm text-sage-100">
              added to <span className="font-mono">{account.account_number}</span>
            </p>
          </div>
          <p className="text-sm text-ink-700">
            The ledger recorded a debit on <span className="font-mono">INR-SYS-CLEARING</span> and a matching credit on
            your account, in a single transaction.
          </p>
          <div className="pt-2 flex justify-end">
            <Button variant="primary" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleDeposit} noValidate className="space-y-4">
          <dl className="p-4 rounded-md bg-surface border border-hairline text-sm space-y-1.5">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Into</dt>
              <dd className="font-mono text-ink-950">{account.account_number}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Current balance</dt>
              <dd>
                <CurrencyDisplay amount={account.cached_balance} size="sm" />
              </dd>
            </div>
          </dl>

          <div>
            <label htmlFor="deposit-amount" className="block text-sm font-medium text-ink-800 mb-1">
              Amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-ink-500 text-sm" aria-hidden="true">₹</span>
              <input
                id="deposit-amount"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className={`${inputClass} pl-7 tabular-nums`}
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="deposit-description" className="block text-sm font-medium text-ink-800 mb-1">
              Description
            </label>
            <input
              id="deposit-description"
              type="text"
              maxLength={255}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={inputClass}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-hairline">
            <Button variant="secondary" type="button" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              size="sm"
              isLoading={isLoading}
              leftIcon={<ArrowDownCircle className="w-4 h-4" />}
            >
              Add deposit
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};

import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { CurrencyDisplay } from '../common/CurrencyDisplay';
import { ErrorBanner } from '../common/ErrorBanner';
import { Account, FinancialProduct, Investment } from '../../types/api';
import { investmentsApi } from '../../api/investments';
import { formatINR, formatPercent, generateUUID, parseAmountInput } from '../../utils/formatters';
import { getErrorMessage, isDefinitiveRejection } from '../../api/client';
import { CheckCircle2 } from 'lucide-react';

interface InvestmentPurchaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: FinancialProduct | null;
  accounts: Account[];
  onPurchaseSuccess?: () => void;
}

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  FIXED_DEPOSIT: 'Fixed deposit',
  RECURRING_DEPOSIT: 'Recurring deposit',
  MUTUAL_FUND: 'Mutual fund',
  TREASURY_BILL: 'Treasury bill',
};

const inputClass =
  'w-full bg-surface border border-hairline rounded px-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 transition-colors';

export const InvestmentPurchaseModal: React.FC<InvestmentPurchaseModalProps> = ({
  isOpen,
  onClose,
  product,
  accounts,
  onPurchaseSuccess,
}) => {
  const eligibleSources = accounts.filter((a) => a.status === 'ACTIVE' && a.account_type === 'SAVINGS');

  const [sourceAccountId, setSourceAccountId] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  // One key per purchase attempt: a replay returns the original investment instead of buying twice
  const [idempotencyKey, setIdempotencyKey] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Investment | null>(null);

  useEffect(() => {
    if (isOpen && product) {
      if (eligibleSources.length > 0 && !sourceAccountId) {
        setSourceAccountId(eligibleSources[0].id);
      }
      setAmount(String(product.min_amount));
      setIdempotencyKey(generateUUID());
      setError(null);
      setResult(null);
    }
  }, [isOpen, product]);

  const handlePurchase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!product) return;

    setError(null);
    const canonical = parseAmountInput(amount);
    if (!canonical || Number(canonical) < Number(product.min_amount)) {
      setError(`Enter at least ${formatINR(product.min_amount)}, with at most two decimal places.`);
      return;
    }
    if (!sourceAccountId) {
      setError('Choose the savings account to pay from.');
      return;
    }

    setIsLoading(true);
    try {
      const inv = await investmentsApi.purchaseInvestment(
        { product_id: product.id, source_account_id: sourceAccountId, amount: canonical },
        idempotencyKey
      );
      setResult(inv);
      onPurchaseSuccess?.();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
      // Rejected attempts are recorded under their key; ambiguous failures keep it so retrying stays safe
      if (isDefinitiveRejection(err)) {
        setIdempotencyKey(generateUUID());
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setError(null);
    setResult(null);
    onClose();
  };

  if (!product) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={result ? 'Investment confirmed' : `Invest in ${product.name}`}
      description={
        result
          ? 'The money moved from your savings into your investment holding account in one ledger transaction.'
          : `${formatPercent(product.annual_yield_rate)} a year for ${product.term_months} months.`
      }
      maxWidth="lg"
    >
      {error && <ErrorBanner message={error} className="mb-4" />}

      {result ? (
        <div className="space-y-4">
          <div className="p-6 rounded-md ledger-hero-green flex flex-col items-center gap-2 text-center">
            <CheckCircle2 className="w-8 h-8 text-forest-300" aria-hidden="true" />
            <CurrencyDisplay amount={result.invested_amount} size="2xl" className="text-white" />
            <p className="text-sm text-sage-100">invested in {product.name}</p>
          </div>

          <dl className="p-4 rounded-md bg-surface border border-hairline space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Reference</dt>
              <dd className="font-mono text-xs text-ink-950 truncate max-w-[260px]" title={result.id}>
                {result.id}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Annual yield</dt>
              <dd className="text-forest-800 font-semibold tabular-nums">{formatPercent(product.annual_yield_rate)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Status</dt>
              <dd className="text-forest-800 font-semibold">{result.status === 'ACTIVE' ? 'Active' : result.status}</dd>
            </div>
          </dl>

          <div className="pt-3 border-t border-hairline flex justify-end">
            <Button variant="primary" size="sm" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handlePurchase} noValidate className="space-y-4">
          <dl className="p-4 rounded-md bg-surface border border-hairline space-y-1.5 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Product</dt>
              <dd className="text-ink-950">
                {PRODUCT_TYPE_LABELS[product.product_type] ?? product.product_type}{' '}
                <span className="font-mono text-xs text-ink-500">{product.code}</span>
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-600">Minimum</dt>
              <dd>
                <CurrencyDisplay amount={product.min_amount} size="sm" />
              </dd>
            </div>
          </dl>

          <div>
            <label htmlFor="invest-source" className="block text-sm font-medium text-ink-800 mb-1">
              Pay from
            </label>
            {eligibleSources.length === 0 ? (
              <p className="text-sm text-ink-600">Open a savings account and add a deposit first.</p>
            ) : (
              <select
                id="invest-source"
                value={sourceAccountId}
                onChange={(e) => setSourceAccountId(e.target.value)}
                className={inputClass}
                required
              >
                {eligibleSources.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.account_number}, available {formatINR(acc.cached_balance)}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label htmlFor="invest-amount" className="block text-sm font-medium text-ink-800 mb-1">
              Amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-ink-500 text-sm" aria-hidden="true">₹</span>
              <input
                id="invest-amount"
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

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-hairline">
            <Button variant="secondary" size="sm" type="button" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              isLoading={isLoading}
              disabled={eligibleSources.length === 0}
            >
              {error ? 'Try again' : 'Invest'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};

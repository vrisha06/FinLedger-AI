import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { InvestmentPurchaseModal } from '../../components/customer/InvestmentPurchaseModal';
import { Account, FinancialProduct, ProductType } from '../../types/api';
import { productsApi } from '../../api/products';
import { accountsApi } from '../../api/accounts';
import { formatPercent } from '../../utils/formatters';
import { getErrorMessage } from '../../api/client';
import { Sparkles } from 'lucide-react';

export const ProductsPage: React.FC = () => {
  const [products, setProducts] = useState<FinancialProduct[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedType, setSelectedType] = useState<string>('ALL');

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedProduct, setSelectedProduct] = useState<FinancialProduct | null>(null);
  const [purchaseModalOpen, setPurchaseModalOpen] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [prods, accs] = await Promise.all([
        productsApi.listProducts(
          selectedType === 'ALL' ? undefined : (selectedType as ProductType),
          true
        ),
        accountsApi.listAccounts(),
      ]);
      setProducts(prods);
      setAccounts(accs);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedType]);

  const categories = [
    { label: 'All', value: 'ALL' },
    { label: 'Fixed deposits', value: 'FIXED_DEPOSIT' },
    { label: 'Recurring deposits', value: 'RECURRING_DEPOSIT' },
    { label: 'Mutual funds', value: 'MUTUAL_FUND' },
    { label: 'Treasury bills', value: 'TREASURY_BILL' },
  ];

  // Plain, accurate one-liners: what each product type means for the customer
  const PRODUCT_SUMMARY: Record<string, string> = {
    FIXED_DEPOSIT: 'A lump sum held for a fixed term at a fixed annual rate.',
    RECURRING_DEPOSIT: 'Build savings over a fixed term at a fixed annual rate.',
    MUTUAL_FUND: 'A pooled fund. The rate shown is the expected annual return.',
    TREASURY_BILL: 'Short-term government-backed security held to maturity.',
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Investment products"
        description="Investing moves money from your savings into your investment holding account in one balanced ledger transaction. This is a simulation: returns shown are nominal and are not paid out."
      />

      <div role="group" aria-label="Filter by product type" className="flex flex-wrap items-center gap-2">
        {categories.map((cat) => {
          const isActive = selectedType === cat.value;
          return (
            <button
              key={cat.value}
              type="button"
              aria-pressed={isActive}
              onClick={() => setSelectedType(cat.value)}
              className={`px-3.5 py-1.5 rounded-full text-sm border transition-colors cursor-pointer whitespace-nowrap ${
                isActive
                  ? 'bg-forest-800 text-white border-forest-950'
                  : 'bg-surface text-ink-800 border-hairline hover:border-forest-700'
              }`}
            >
              {cat.label}
            </button>
          );
        })}
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : products.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="w-6 h-6 text-forest-700" />}
          title="No products in this category"
          description="Try another filter, or choose All to see every product."
        />
      ) : (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {products.map((prod) => (
            <li
              key={prod.id}
              className="bg-surface border border-hairline rounded-lg p-5 flex flex-col gap-5 shadow-atelier"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-xs text-ink-500">
                  <span>{categories.find((c) => c.value === prod.product_type)?.label.replace(/s$/, '') ?? prod.product_type}</span>
                  <span className="font-mono">{prod.code}</span>
                </div>
                <h2 className="font-serif text-xl font-semibold text-forest-950 leading-snug">{prod.name}</h2>
                <p className="text-sm text-ink-600 leading-relaxed min-h-[3.25em]">{PRODUCT_SUMMARY[prod.product_type]}</p>
              </div>

              <dl className="grid grid-cols-3 gap-3 py-4 border-y border-hairline-subtle">
                <div>
                  <dt className="text-xs text-ink-500">Per year</dt>
                  <dd className="font-serif text-2xl font-semibold text-forest-800 tabular-nums">
                    {formatPercent(prod.annual_yield_rate)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-500">Term</dt>
                  <dd className="text-lg font-semibold text-ink-950 tabular-nums">{prod.term_months} mo</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-500">Minimum</dt>
                  <dd>
                    <CurrencyDisplay amount={prod.min_amount} size="md" className="text-ink-950" />
                  </dd>
                </div>
              </dl>

              <Button
                variant="primary"
                size="sm"
                className="w-full mt-auto"
                onClick={() => {
                  setSelectedProduct(prod);
                  setPurchaseModalOpen(true);
                }}
              >
                Invest
              </Button>
            </li>
          ))}
        </ul>
      )}

      <InvestmentPurchaseModal
        isOpen={purchaseModalOpen}
        onClose={() => setPurchaseModalOpen(false)}
        product={selectedProduct}
        accounts={accounts}
        onPurchaseSuccess={fetchData}
      />
    </div>
  );
};

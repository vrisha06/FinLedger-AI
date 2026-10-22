import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { PageHeader } from '../../components/common/PageHeader';
import { PortfolioSummary } from '../../types/api';
import { investmentsApi } from '../../api/investments';
import { getErrorMessage } from '../../api/client';
import { formatDateOnly, formatPercent } from '../../utils/formatters';
import { Link } from 'react-router-dom';
import { PieChart, Sparkles } from 'lucide-react';

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  FIXED_DEPOSIT: 'Fixed deposits',
  RECURRING_DEPOSIT: 'Recurring deposits',
  MUTUAL_FUND: 'Mutual funds',
  TREASURY_BILL: 'Treasury bills',
};

export const PortfolioPage: React.FC = () => {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setPortfolio(await investmentsApi.getPortfolio());
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const holdings = portfolio?.holdings ?? [];
  const totalInvested = Number(portfolio?.total_invested ?? 0);
  // Display-only estimate: the backend computes nominal accrual per holding; nothing is paid out yet
  const estimatedInterest = holdings.reduce((sum, h) => sum + Number(h.nominal_accrued_yield || 0), 0);
  const allocation = Object.entries(portfolio?.allocation_by_product_type ?? {});

  return (
    <div className="space-y-8">
      <PageHeader
        title="Portfolio"
        description="What you've invested and when each holding matures. Interest is estimated from the product's annual rate and isn't paid out in this simulation."
        action={
          <Link to="/products">
            <Button variant="primary" size="sm" leftIcon={<Sparkles className="w-4 h-4" />}>
              Explore products
            </Button>
          </Link>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : holdings.length === 0 ? (
        <EmptyState
          icon={<PieChart className="w-6 h-6 text-forest-700" />}
          title="You don't hold any investments yet"
          description="Choose a product to invest in. The amount moves from your savings into your investment holding account in one balanced transaction."
          action={
            <Link to="/products">
              <Button variant="primary" size="sm">
                Browse products
              </Button>
            </Link>
          }
        />
      ) : (
        <>
          <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-5 rounded-lg bg-surface border border-hairline shadow-atelier">
              <dt className="text-sm text-ink-600">Invested</dt>
              <dd className="mt-1">
                <CurrencyDisplay amount={totalInvested} size="xl" className="text-forest-950" />
              </dd>
            </div>
            <div className="p-5 rounded-lg bg-surface border border-hairline shadow-atelier">
              <dt className="text-sm text-ink-600">Estimated interest so far</dt>
              <dd className="mt-1">
                <CurrencyDisplay amount={estimatedInterest} size="xl" sign="plus" colored />
              </dd>
            </div>
            <div className="p-5 rounded-lg bg-surface border border-hairline shadow-atelier">
              <dt className="text-sm text-ink-600">Holdings</dt>
              <dd className="mt-1 font-serif text-2xl font-semibold text-forest-950">{holdings.length}</dd>
            </div>
          </dl>

          {allocation.length > 1 && (
            <Card variant="paper" title="By product type">
              <ul className="space-y-3">
                {allocation.map(([type, amount]) => {
                  const pct = totalInvested > 0 ? (Number(amount) / totalInvested) * 100 : 0;
                  return (
                    <li key={type} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 items-center text-sm">
                      <span className="text-ink-800">{PRODUCT_TYPE_LABELS[type] ?? type}</span>
                      <span className="text-ink-600 tabular-nums">
                        <CurrencyDisplay amount={amount} size="sm" /> ({pct.toFixed(0)}%)
                      </span>
                      <span className="col-span-2 h-1.5 rounded-full bg-parchment-200 overflow-hidden">
                        <span className="block h-full bg-forest-800" style={{ width: `${pct}%` }} />
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}

          <Card variant="paper" title="Holdings">
            <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink-500 border-b border-hairline">
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5">Product</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Rate</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Invested</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Estimated interest</th>
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5 text-right">Matures</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline-subtle">
                  {holdings.map((h) => (
                    <tr key={h.investment_id}>
                      <td className="py-3 px-4 sm:px-5">
                        <span className="block text-ink-950">{h.product_name}</span>
                        <span className="block font-mono text-xs text-ink-500">{h.product_code}</span>
                      </td>
                      <td className="py-3 px-4 text-right tabular-nums text-ink-800">
                        {formatPercent(h.annual_yield_rate)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <CurrencyDisplay amount={h.invested_amount} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <CurrencyDisplay amount={h.nominal_accrued_yield} size="sm" sign="plus" colored />
                      </td>
                      <td className="py-3 px-4 sm:px-5 text-right text-ink-700 whitespace-nowrap">
                        {formatDateOnly(h.maturity_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

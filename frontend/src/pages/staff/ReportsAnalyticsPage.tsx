import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { PageHeader } from '../../components/common/PageHeader';
import { CreateProductModal } from '../../components/staff/CreateProductModal';
import {
  BalanceDistributionReport,
  DailyVolumeReport,
  ProductsSummaryReport,
} from '../../types/api';
import { reportsApi } from '../../api/reports';
import { getErrorMessage } from '../../api/client';
import { formatPercent } from '../../utils/formatters';
import { Plus } from 'lucide-react';

export const ReportsAnalyticsPage: React.FC = () => {
  const [dailyVolume, setDailyVolume] = useState<DailyVolumeReport | null>(null);
  const [balanceDist, setBalanceDist] = useState<BalanceDistributionReport | null>(null);
  const [productsSummary, setProductsSummary] = useState<ProductsSummaryReport | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createProductOpen, setCreateProductOpen] = useState(false);

  const fetchReports = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [vol, dist, prods] = await Promise.all([
        reportsApi.getDailyVolume(14),
        reportsApi.getBalanceDistribution(),
        reportsApi.getProductsSummary(),
      ]);
      setDailyVolume(vol);
      setBalanceDist(dist);
      setProductsSummary(prods);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleProductCreated = () => {
    fetchReports();
  };

  const records = dailyVolume?.daily_records ?? [];
  const activeDays = records.filter((r) => r.transfer_count > 0 || r.investment_count > 0);
  const tiers = balanceDist
    ? [
        { label: 'Under ₹1,000', count: balanceDist.tier_under_1k_count },
        { label: '₹1,000 to ₹10,000', count: balanceDist.tier_1k_to_10k_count },
        { label: '₹10,000 to ₹50,000', count: balanceDist.tier_10k_to_50k_count },
        { label: '₹50,000 to ₹1,00,000', count: balanceDist.tier_50k_to_100k_count },
        { label: '₹1,00,000 and above', count: balanceDist.tier_above_100k_count },
      ]
    : [];
  const customerAccounts = tiers.reduce((n, t) => n + t.count, 0);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Reports"
        description="Figures are aggregated by PostgreSQL queries over committed postings, not estimated in the browser."
        action={
          <Button variant="primary" size="sm" onClick={() => setCreateProductOpen(true)} leftIcon={<Plus className="w-3.5 h-3.5" />}>
            Add product
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchReports} />}

      <Card variant="forensic" title="Daily activity, last 14 days" subtitle="Days with no activity are hidden. Dates are UTC.">
        {isLoading ? (
          <LoadingSkeleton rows={4} />
        ) : activeDays.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No transfers or investments in the last 14 days.</p>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-forensic-700">
                  <th scope="col" className="font-medium py-2 px-4 sm:px-5">Date</th>
                  <th scope="col" className="font-medium py-2 px-4 text-right">Transfers</th>
                  <th scope="col" className="font-medium py-2 px-4 text-right">Transfer volume</th>
                  <th scope="col" className="font-medium py-2 px-4 text-right">Investments</th>
                  <th scope="col" className="font-medium py-2 px-4 text-right">Investment volume</th>
                  <th scope="col" className="font-medium py-2 px-4 sm:px-5 text-right">Day total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-forensic-700">
                {activeDays.map((rec) => (
                  <tr key={rec.date}>
                    <td className="py-2.5 px-4 sm:px-5 text-slate-100 tabular-nums">{rec.date}</td>
                    <td className="py-2.5 px-4 text-right tabular-nums text-slate-300">{rec.transfer_count}</td>
                    <td className="py-2.5 px-4 text-right">
                      <CurrencyDisplay amount={rec.transfer_volume} size="sm" />
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums text-slate-300">{rec.investment_count}</td>
                    <td className="py-2.5 px-4 text-right">
                      <CurrencyDisplay amount={rec.investment_volume} size="sm" />
                    </td>
                    <td className="py-2.5 px-4 sm:px-5 text-right font-semibold">
                      <CurrencyDisplay amount={rec.total_day_volume} size="sm" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          variant="forensic"
          title="Customer balances"
          subtitle={
            balanceDist
              ? `${customerAccounts} customer accounts holding ${Number(balanceDist.total_customer_liabilities).toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}`
              : undefined
          }
        >
          {isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : !balanceDist ? (
            <p className="py-6 text-center text-sm text-slate-400">No balance data available.</p>
          ) : (
            <ul className="space-y-3">
              {tiers.map((tier) => {
                const pct = customerAccounts > 0 ? (tier.count / customerAccounts) * 100 : 0;
                return (
                  <li key={tier.label} className="text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-200">{tier.label}</span>
                      <span className="text-slate-400 tabular-nums">
                        {tier.count} {tier.count === 1 ? 'account' : 'accounts'}
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-forensic-950 overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
              <li className="pt-3 border-t border-forensic-700 flex justify-between gap-4 text-sm">
                <span className="text-slate-400">Clearing account balance</span>
                <CurrencyDisplay amount={balanceDist.system_clearing_balance} size="sm" />
              </li>
            </ul>
          )}
        </Card>

        <Card variant="forensic" title="Products" subtitle="Purchases and money invested per product.">
          {isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : !productsSummary || productsSummary.products.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">No products yet.</p>
          ) : (
            <ul className="divide-y divide-forensic-700 -my-2">
              {productsSummary.products.map((prod) => (
                <li key={prod.product_id} className="py-3 flex items-start justify-between gap-4 text-sm">
                  <div>
                    <span className="block text-slate-100">{prod.name}</span>
                    <span className="block text-xs text-slate-400">
                      <span className="font-mono">{prod.code}</span>, {formatPercent(prod.annual_yield_rate)} for{' '}
                      {prod.term_months} months{prod.is_active ? '' : ', inactive'}
                    </span>
                  </div>
                  <div className="text-right shrink-0">
                    <CurrencyDisplay amount={prod.total_invested_volume} size="sm" />
                    <span className="block text-xs text-slate-400 tabular-nums">
                      {prod.active_subscriptions} active
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <CreateProductModal
        isOpen={createProductOpen}
        onClose={() => setCreateProductOpen(false)}
        onProductCreated={handleProductCreated}
      />
    </div>
  );
};

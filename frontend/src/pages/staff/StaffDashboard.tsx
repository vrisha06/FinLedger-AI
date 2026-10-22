import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { PageHeader } from '../../components/common/PageHeader';
import { Link } from 'react-router-dom';
import { DailyVolumeReport, FraudAlert, ReconciliationReport } from '../../types/api';
import { reportsApi } from '../../api/reports';
import { fraudApi } from '../../api/fraud';
import { auditApi } from '../../api/audit';
import { getErrorMessage } from '../../api/client';
import { ArrowRight } from 'lucide-react';

const QUEUE_PREVIEW = 10;

const RISK_BADGE: Record<string, { label: string; variant: 'danger' | 'warning' | 'success' }> = {
  HIGH_RISK: { label: 'High risk', variant: 'danger' },
  MEDIUM_RISK: { label: 'Medium risk', variant: 'warning' },
  LOW_RISK: { label: 'Low risk', variant: 'success' },
};

export const StaffDashboard: React.FC = () => {
  const [dailyVolume, setDailyVolume] = useState<DailyVolumeReport | null>(null);
  const [pendingAlerts, setPendingAlerts] = useState<FraudAlert[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationReport | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [vol, alerts, recon] = await Promise.all([
        reportsApi.getDailyVolume(14),
        fraudApi.listAlerts({ review_status: 'PENDING', limit: QUEUE_PREVIEW }),
        auditApi.getReconciliation(),
      ]);
      setDailyVolume(vol);
      setPendingAlerts(alerts);
      setReconciliation(recon);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Window totals are summed from the API's per-day records (display only)
  const records = dailyVolume?.daily_records ?? [];
  const transferCount = records.reduce((n, r) => n + r.transfer_count, 0);
  const transferVolume = records.reduce((n, r) => n + Number(r.transfer_volume), 0);
  const investmentCount = records.reduce((n, r) => n + r.investment_count, 0);
  const investmentVolume = records.reduce((n, r) => n + Number(r.investment_volume), 0);
  const pendingLabel = pendingAlerts.length >= QUEUE_PREVIEW ? `${QUEUE_PREVIEW}+` : String(pendingAlerts.length);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Overview"
        description="Alerts waiting for a decision, recent activity and the state of the ledger. Fraud scores are advisory: they never block or reverse a transfer."
        action={
          <Link to="/staff/fraud">
            <Button variant="primary" size="sm">
              Review alerts ({pendingLabel})
            </Button>
          </Link>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {isLoading ? (
        <LoadingSkeleton rows={2} />
      ) : (
        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-forensic-850 border border-forensic-700 rounded-lg p-4">
            <dt className="text-sm text-slate-400">Alerts awaiting review</dt>
            <dd className="mt-1 text-3xl font-semibold tabular-nums text-rose-300">{pendingLabel}</dd>
          </div>
          <div className="bg-forensic-850 border border-forensic-700 rounded-lg p-4">
            <dt className="text-sm text-slate-400">Transfers, last 14 days</dt>
            <dd className="mt-1">
              <CurrencyDisplay amount={transferVolume} size="xl" />
              <span className="block text-xs text-slate-400 mt-0.5">
                {transferCount} posted {transferCount === 1 ? 'transfer' : 'transfers'}
              </span>
            </dd>
          </div>
          <div className="bg-forensic-850 border border-forensic-700 rounded-lg p-4">
            <dt className="text-sm text-slate-400">Investments, last 14 days</dt>
            <dd className="mt-1">
              <CurrencyDisplay amount={investmentVolume} size="xl" />
              <span className="block text-xs text-slate-400 mt-0.5">
                {investmentCount} {investmentCount === 1 ? 'purchase' : 'purchases'}
              </span>
            </dd>
          </div>
          <div className="bg-forensic-850 border border-forensic-700 rounded-lg p-4">
            <dt className="text-sm text-slate-400">Ledger reconciliation</dt>
            <dd className="mt-1.5">
              <Badge variant={reconciliation?.is_balanced ? 'success' : 'danger'} size="sm">
                {reconciliation?.is_balanced ? 'Balanced' : `${reconciliation?.discrepancy_count ?? '?'} discrepancies`}
              </Badge>
              <span className="block text-xs text-slate-400 mt-1.5">
                {reconciliation?.total_accounts_checked ?? 0} accounts checked just now
              </span>
            </dd>
          </div>
        </dl>
      )}

      <Card
        variant="forensic"
        title="Waiting for review"
        subtitle="Highest scores first. Scores come from the rule baseline, plus the Random Forest model when one is loaded."
        action={
          <Link to="/staff/fraud" className="text-sm text-emerald-300 hover:text-emerald-200 flex items-center gap-1">
            All alerts <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
          </Link>
        }
      >
        {isLoading ? (
          <LoadingSkeleton rows={4} />
        ) : pendingAlerts.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No alerts are waiting. New transfers are scored as they post.</p>
        ) : (
          <ul className="divide-y divide-forensic-700 -my-2">
            {pendingAlerts.slice(0, 5).map((alert) => {
              const risk = RISK_BADGE[alert.decision] ?? { label: alert.decision, variant: 'warning' as const };
              return (
                <li key={alert.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={risk.variant} size="sm">
                        {risk.label}
                      </Badge>
                      <span className="text-sm text-slate-200 tabular-nums">
                        Score {Number(alert.risk_score).toFixed(2)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-1 truncate">{alert.explanation}</p>
                  </div>
                  <Link to="/staff/fraud" className="shrink-0">
                    <Button variant="secondary" size="sm">
                      Review
                    </Button>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Badge, BadgeVariant } from '../../components/common/Badge';
import { Card } from '../../components/common/Card';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { ForensicDossierDrawer } from '../../components/staff/ForensicDossierDrawer';
import { FraudAlert, FraudReviewStatus, FraudRiskDecision } from '../../types/api';
import { fraudApi } from '../../api/fraud';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ShieldAlert, RefreshCw } from 'lucide-react';

const STATUS_FILTERS: Array<[string, string]> = [
  ['ALL', 'All'],
  ['PENDING', 'Pending'],
  ['CLEARED', 'Cleared'],
  ['ESCALATED', 'Escalated'],
  ['CONFIRMED_FRAUD', 'Confirmed fraud'],
];

const DECISION: Record<string, { label: string; variant: BadgeVariant }> = {
  HIGH_RISK: { label: 'High', variant: 'danger' },
  MEDIUM_RISK: { label: 'Medium', variant: 'warning' },
  LOW_RISK: { label: 'Low', variant: 'success' },
};

const STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  PENDING: { label: 'Pending', variant: 'warning' },
  CLEARED: { label: 'Cleared', variant: 'success' },
  CONFIRMED_FRAUD: { label: 'Fraud', variant: 'danger' },
  ESCALATED: { label: 'Escalated', variant: 'purple' },
};

export const FraudTriagePage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string>('PENDING');
  const [decisionFilter, setDecisionFilter] = useState<string>('ALL');
  const [minRiskScore, setMinRiskScore] = useState<number>(0.0);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<FraudAlert | null>(null);

  const fetchAlerts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setAlerts(
        await fraudApi.listAlerts({
          review_status: reviewStatusFilter === 'ALL' ? undefined : (reviewStatusFilter as FraudReviewStatus),
          decision: decisionFilter === 'ALL' ? undefined : (decisionFilter as FraudRiskDecision),
          min_risk_score: minRiskScore > 0 ? minRiskScore : undefined,
          limit: 100,
        })
      );
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [reviewStatusFilter, decisionFilter, minRiskScore]);

  const selectClass =
    'bg-forensic-900 border border-forensic-700 rounded px-2.5 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500';

  return (
    <div className="space-y-8">
      <PageHeader
        title="Fraud alerts"
        description="Every posted transfer is scored after it commits. Scores help you prioritise; only your decision changes an alert's status, and no decision moves money."
        action={
          <Button variant="secondary" size="sm" onClick={fetchAlerts} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>
            Refresh
          </Button>
        }
      />

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div role="group" aria-label="Filter by review status" className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={reviewStatusFilter === value}
              onClick={() => setReviewStatusFilter(value)}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors cursor-pointer ${
                reviewStatusFilter === value
                  ? 'bg-forest-800 border-emerald-600 text-white'
                  : 'bg-forensic-900 border-forensic-700 text-slate-300 hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
          <label className="flex items-center gap-2">
            Risk
            <select value={decisionFilter} onChange={(e) => setDecisionFilter(e.target.value)} className={selectClass}>
              <option value="ALL">Any</option>
              <option value="HIGH_RISK">High</option>
              <option value="MEDIUM_RISK">Medium</option>
              <option value="LOW_RISK">Low</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            Score at least
            <select value={minRiskScore} onChange={(e) => setMinRiskScore(Number(e.target.value))} className={selectClass}>
              <option value="0">Any</option>
              <option value="0.3">0.30</option>
              <option value="0.5">0.50</option>
              <option value="0.7">0.70</option>
            </select>
          </label>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchAlerts} />}

      <Card variant="forensic" title={`Alerts (${alerts.length})`} subtitle="Highest score first.">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : alerts.length === 0 ? (
          <EmptyState
            icon={<ShieldAlert className="w-6 h-6" />}
            title="No alerts match"
            description={reviewStatusFilter === 'PENDING' ? 'Nothing is waiting for review.' : 'Try a different filter.'}
          />
        ) : (
          <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-forensic-700">
                  <th scope="col" className="font-medium py-2 px-4 sm:px-5">Score</th>
                  <th scope="col" className="font-medium py-2 px-4">Risk</th>
                  <th scope="col" className="font-medium py-2 px-4">Status</th>
                  <th scope="col" className="font-medium py-2 px-4">Why it was flagged</th>
                  <th scope="col" className="font-medium py-2 px-4">Scored</th>
                  <th scope="col" className="py-2 px-4 sm:px-5">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-forensic-700">
                {alerts.map((alert) => {
                  const decision = DECISION[alert.decision] ?? { label: alert.decision, variant: 'neutral' as BadgeVariant };
                  const status = STATUS[alert.review_status] ?? { label: alert.review_status, variant: 'neutral' as BadgeVariant };
                  return (
                    <tr key={alert.id} className="align-top">
                      <td className="py-3 px-4 sm:px-5 tabular-nums font-semibold text-slate-100">
                        {Number(alert.risk_score).toFixed(2)}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={decision.variant} size="sm">{decision.label}</Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={status.variant} size="sm">{status.label}</Badge>
                      </td>
                      <td className="py-3 px-4 max-w-sm">
                        <p className="text-slate-300 line-clamp-2">{alert.explanation}</p>
                        {alert.rule_flags.length > 0 && (
                          <p className="mt-1 font-mono text-xs text-amber-300">{alert.rule_flags.join(', ')}</p>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <DateDisplay date={alert.created_at} />
                      </td>
                      <td className="py-3 px-4 sm:px-5 text-right">
                        <Button variant="secondary" size="sm" onClick={() => setSelectedAlert(alert)}>
                          Open dossier
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ForensicDossierDrawer
        isOpen={selectedAlert !== null}
        onClose={() => setSelectedAlert(null)}
        alertId={selectedAlert?.id ?? null}
        onAlertReviewed={fetchAlerts}
        canReverse={isAdmin}
      />
    </div>
  );
};

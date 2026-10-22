import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { Button } from '../../components/common/Button';
import { fraudApi } from '../../api/fraud';
import { AIHealthResponse } from '../../types/api';
import { getErrorMessage } from '../../api/client';
import { AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';

export const AIHealthPage: React.FC = () => {
  const [health, setHealth] = useState<AIHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setHealth(await fraudApi.getHealth());
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const triage = health?.triage_metrics;
  const drift = health?.feature_drift_indicators;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Model health"
        description="Which fraud model is running, how its alerts are being handled, and whether recent transfers still look like the data it was trained on."
        action={
          <Button variant="secondary" size="sm" onClick={fetchHealth} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>
            Refresh
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchHealth} />}

      {isLoading || !health || !triage || !drift ? (
        !error && (
          <div className="flex items-center justify-center p-16">
            <LoadingSpinner size="lg" />
          </div>
        )
      ) : (
        <>
          {health.is_fallback && (
            <div className="p-4 rounded-lg bg-amber-950/40 border border-amber-500/40 text-sm text-amber-100 flex gap-3" role="status">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-semibold">Running on the rule baseline</p>
                <p className="text-amber-200/90 mt-0.5">
                  No trained Random Forest artifact is loaded, so transfers are scored with the transparent rule
                  baseline. Train one with <code className="font-mono">python -m ml.train</code> from the backend
                  folder and restart the API.
                </p>
              </div>
            </div>
          )}

          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-forensic-850 border border-forensic-700">
              <dt className="text-sm text-slate-400">Active model</dt>
              <dd className="mt-1.5 flex items-center gap-2 text-slate-100 font-semibold">
                {health.model_loaded ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400" aria-hidden="true" />
                )}
                {health.model_loaded ? 'Random Forest' : 'Rule baseline'}
              </dd>
              <dd className="font-mono text-xs text-slate-400 mt-1">{health.active_model_version}</dd>
            </div>
            <div className="p-4 rounded-lg bg-forensic-850 border border-forensic-700">
              <dt className="text-sm text-slate-400">Alert threshold</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                {health.decision_threshold.toFixed(2)}
              </dd>
              <dd className="text-xs text-slate-400">Scores at or above this are high risk</dd>
            </div>
            <div className="p-4 rounded-lg bg-forensic-850 border border-forensic-700">
              <dt className="text-sm text-slate-400">Waiting for review</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">{triage.pending_review}</dd>
              <dd className="text-xs text-slate-400">
                {triage.pending_percentage.toFixed(0)}% of {triage.total_predictions} scored transfers
              </dd>
            </div>
            <div className="p-4 rounded-lg bg-forensic-850 border border-forensic-700">
              <dt className="text-sm text-slate-400">Artifact fingerprint</dt>
              <dd className="mt-1.5 font-mono text-xs text-slate-300 break-all">{health.artifact_fingerprint}</dd>
              <dd className="text-xs text-slate-400 mt-1">SHA-256 of the loaded model file</dd>
            </div>
          </dl>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card variant="forensic" title="Review outcomes" subtitle="Decisions staff have made on scored transfers.">
              <dl className="grid grid-cols-2 gap-4 text-sm">
                {[
                  ['Pending', triage.pending_review],
                  ['Cleared', triage.cleared],
                  ['Confirmed fraud', triage.confirmed_fraud],
                  ['Escalated', triage.escalated],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-slate-400">{label}</dt>
                    <dd className="text-xl font-semibold tabular-nums text-slate-100">{value}</dd>
                  </div>
                ))}
              </dl>
            </Card>

            <Card variant="forensic" title="Input drift" subtitle={drift.interpretation}>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">Status</dt>
                  <dd>
                    <Badge variant={drift.distribution_status === 'STABLE' ? 'success' : 'warning'} size="sm">
                      {drift.distribution_status === 'STABLE' ? 'Stable' : drift.distribution_status}
                    </Badge>
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">Recent transfers checked</dt>
                  <dd className="tabular-nums text-slate-100">{drift.recent_sample_size}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">Their average amount</dt>
                  <dd className="tabular-nums text-slate-100">
                    ₹{Number(drift.recent_mean_amount_inr).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">Compared against</dt>
                  <dd className="text-slate-100 text-right">{drift.reference_window}</dd>
                </div>
              </dl>
            </Card>
          </div>

          {health.feature_schema.length > 0 && (
            <Card
              variant="forensic"
              title="Model inputs"
              subtitle={`${health.feature_schema.length} features computed for every transfer`}
            >
              <ul className="flex flex-wrap gap-2">
                {health.feature_schema.map((col) => (
                  <li key={col} className="px-2 py-1 rounded bg-forensic-900 border border-forensic-700 font-mono text-xs text-slate-300">
                    {col}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card variant="forensic" title="Known limitations">
            <ul className="space-y-2 text-sm text-slate-300 list-disc pl-5">
              {health.known_limitations.map((lim) => (
                <li key={lim} className="leading-relaxed">
                  {lim}
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
};

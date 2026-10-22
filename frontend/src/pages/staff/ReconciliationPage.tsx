import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { ReconciliationReport } from '../../types/api';
import { auditApi } from '../../api/audit';
import { getErrorMessage } from '../../api/client';
import { Scale, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';

export const ReconciliationPage: React.FC = () => {
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runReconciliation = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.getReconciliation();
      setReport(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    runReconciliation();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reconciliation"
        description="Checks every account: the stored balance must equal its credits minus its debits, recomputed from the ledger right now."
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={runReconciliation}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Run Live Audit
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={runReconciliation} />}

      {/* Reconciliation Invariant Explanation */}
      <div className="p-4 rounded-xl bg-forensic-850 border border-forensic-700 text-xs text-sage-200 flex items-start gap-3 shadow-sm">
        <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-white font-mono">
            Closed-Ledger Conservation Law
          </h4>
          <p className="text-sage-300 leading-relaxed text-[11px]">
            In a double-entry banking ledger, money cannot be created or destroyed. The sum of all customer
            liabilities plus the internal clearing account (<code className="text-emerald-400 font-mono">INR-SYS-CLEARING</code>)
            must strictly equal zero (<code className="text-emerald-400 font-mono">Global Net Ledger Delta == INR 0.00</code>).
          </p>
        </div>
      </div>

      {/* KPI Audit Summary Cards */}
      {isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : report ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card variant="forensic">
            <div className="flex items-center justify-between text-sage-400 mb-2">
              <span className="text-[11px] font-bold font-mono">Audit Integrity</span>
              {report.is_balanced ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-400" />
              )}
            </div>
            <div className="mt-1">
              <Badge variant={report.is_balanced ? 'evergreen' : 'danger'} size="md">
                {report.is_balanced ? 'Zero Discrepancies' : `${report.discrepancy_count} Mismatch(es)`}
              </Badge>
            </div>
            <p className="text-[11px] text-sage-400 mt-2 font-mono">
              Audited: <DateDisplay date={report.reconciled_at} />
            </p>
          </Card>

          <Card variant="forensic">
            <div className="flex items-center justify-between text-sage-400 mb-2">
              <span className="text-[11px] font-bold font-mono">Audited Accounts</span>
              <Scale className="w-4 h-4 text-emerald-400" />
            </div>
            <span className="text-2xl font-bold text-white font-mono tabular-nums">
              {report.total_accounts_checked}
            </span>
            <p className="text-[11px] text-sage-400 mt-2 font-mono">
              All active customer & clearing accounts
            </p>
          </Card>

          <Card variant="forensic">
            <div className="flex items-center justify-between text-sage-400 mb-2">
              <span className="text-[11px] font-bold font-mono">System Clearing Balance</span>
              <Scale className="w-4 h-4 text-sage-300" />
            </div>
            <CurrencyDisplay amount={report.system_clearing_balance} size="xl" colored />
            <p className="text-[11px] text-sage-400 mt-2 font-mono">
              INR-SYS-CLEARING internal ledger balance
            </p>
          </Card>

          <Card variant="forensic">
            <div className="flex items-center justify-between text-sage-400 mb-2">
              <span className="text-[11px] font-bold font-mono">Global Net Ledger Delta</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <CurrencyDisplay amount={report.global_net_ledger_delta} size="xl" colored />
            <p className="text-[11px] text-sage-400 mt-2 font-mono">
              Customer Liabilities: <CurrencyDisplay amount={report.total_customer_liabilities} size="sm" />
            </p>
          </Card>
        </div>
      ) : null}

      {/* Discrepancies Table / Clean State */}
      <Card
        title="Discrepancy Investigation Register"
        subtitle="Accounts where cached balance deviates from sum of posted ledger entries"
        variant="forensic"
      >
        {isLoading ? (
          <LoadingSkeleton rows={3} />
        ) : !report || report.discrepancies.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 className="w-8 h-8 text-emerald-400" />}
            title="Every account reconciles"
            description="Each stored balance matches the sum of its posted ledger entries exactly."
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-forensic-700">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-forensic-900 text-[11px] text-rose-300 border-b border-forensic-700 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Account Number</th>
                  <th className="py-2.5 px-3">Account ID</th>
                  <th className="py-2.5 px-3 text-right">Cached Balance</th>
                  <th className="py-2.5 px-3 text-right">Derived Ledger Sum</th>
                  <th className="py-2.5 px-3 text-right">Discrepancy Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-forensic-750">
                {report.discrepancies.map((item) => (
                  <tr key={item.account_id} className="hover:bg-rose-500/10 transition-colors">
                    <td className="py-3 px-3 font-bold text-white">{item.account_number}</td>
                    <td className="py-3 px-3 text-sage-300">{item.account_id}</td>
                    <td className="py-3 px-3 text-right tabular-nums">
                      <CurrencyDisplay amount={item.cached_balance} size="sm" />
                    </td>
                    <td className="py-3 px-3 text-right tabular-nums">
                      <CurrencyDisplay amount={item.derived_balance} size="sm" />
                    </td>
                    <td className="py-3 px-3 text-right text-rose-400 font-bold tabular-nums">
                      <CurrencyDisplay amount={item.discrepancy} size="sm" colored sign="auto" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

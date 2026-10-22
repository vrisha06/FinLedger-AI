import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Modal } from '../../components/common/Modal';
import { PageHeader } from '../../components/common/PageHeader';
import { AuditLog } from '../../types/api';
import { auditApi } from '../../api/audit';
import { getErrorMessage } from '../../api/client';
import { RefreshCw, Eye, Terminal } from 'lucide-react';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionFilter, setActionFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const fetchLogs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.listLogs({
        action: actionFilter.trim() || undefined,
        limit: 100,
      });
      setLogs(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [actionFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit trail"
        description="Every security and money event, in order. Rows are append-only: PostgreSQL triggers reject any UPDATE, DELETE or TRUNCATE."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchLogs}
            leftIcon={<RefreshCw className="w-3.5 h-3.5 text-stone-400" />}
          >
            Refresh Logs
          </Button>
        }
      />

      {/* Action quick filters */}
      <div className="p-4 rounded-xl bg-forensic-850 border border-forensic-700 flex flex-wrap items-center gap-2 text-xs shadow-sm">
        <span className="font-bold text-sage-300 mr-1 text-[11px] font-mono">Show:</span>
        {[
          'ALL',
          'AUTH_LOGIN_SUCCESS',
          'AUTH_LOGIN_FAILURE',
          'TRANSFER_POSTED',
          'TRANSFER_FAILED',
          'TRANSFER_REVERSED',
          'INVESTMENT_PURCHASE_FAILED',
          'FRAUD_ALERT_REVIEW',
          'DISPUTE_CREATED',
        ].map((act) => (
          <button
            key={act}
            onClick={() => setActionFilter(act === 'ALL' ? '' : act)}
            className={`px-2.5 py-1 rounded font-mono text-[11px] font-semibold transition-all border ${
              (act === 'ALL' && !actionFilter) || actionFilter === act
                ? 'bg-forest-800 border-forest-600 text-white font-bold shadow-xs'
                : 'bg-forensic-900 border-forensic-700 text-sage-300 hover:text-white hover:bg-forensic-800'
            }`}
          >
            {act}
          </button>
        ))}
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchLogs} />}

      {/* Audit Logs Table */}
      <Card
        title={`Audit Records (${logs.length})`}
        subtitle="Chronological audit events with user actor and forensic client metadata"
        variant="forensic"
      >
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-xs text-sage-400 font-mono">
            No audit records matching query parameters.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-forensic-700">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-forensic-900 text-[11px] text-sage-300 border-b border-forensic-700 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Log ID</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Entity Type</th>
                  <th className="py-2.5 px-3">Entity ID</th>
                  <th className="py-2.5 px-3">Actor UUID</th>
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-forensic-750">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-forensic-800/70 transition-colors">
                    <td className="py-3 px-3 text-sage-400 font-bold tabular-nums">#{log.id}</td>
                    <td className="py-3 px-3 font-sans">
                      <Badge
                        variant={
                          log.action.includes('FAILURE') || log.action.includes('FAILED')
                            ? 'danger'
                            : log.action.includes('SUCCESS')
                            ? 'evergreen'
                            : log.action.includes('REVIEW')
                            ? 'purple'
                            : 'neutral'
                        }
                        size="sm"
                      >
                        {log.action}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-sage-200 font-mono">{log.entity_type}</td>
                    <td className="py-3 px-3 text-sage-300 truncate max-w-[120px]">
                      {log.entity_id}
                    </td>
                    <td className="py-3 px-3 text-sage-300 truncate max-w-[120px]">
                      {log.actor_user_id || 'SYSTEM'}
                    </td>
                    <td className="py-3 px-3 text-sage-400 text-[11px]">
                      <DateDisplay date={log.created_at} />
                    </td>
                    <td className="py-3 px-3 text-right font-sans">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedLog(log)}
                        leftIcon={<Eye className="w-3.5 h-3.5 text-sage-300" />}
                        className="text-xs font-semibold"
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* JSON Metadata Inspector Modal */}
      {selectedLog && (
        <Modal
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          title={`Audit Log #${selectedLog.id} Forensic Details`}
          description={`Action: ${selectedLog.action} • Entity: ${selectedLog.entity_type} (${selectedLog.entity_id})`}
          maxWidth="lg"
        >
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-forensic-900 border border-forensic-700 grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-sage-400 block mb-0.5 text-[11px] font-mono font-bold">Actor User ID</span>
                <span className="font-mono text-white">
                  {selectedLog.actor_user_id || 'SYSTEM_INTERNAL'}
                </span>
              </div>
              <div>
                <span className="text-sage-400 block mb-0.5 text-[11px] font-mono font-bold">Recorded Timestamp</span>
                <DateDisplay date={selectedLog.created_at} />
              </div>
              <div>
                <span className="text-sage-400 block mb-0.5 text-[11px] font-mono font-bold">Client IP Address</span>
                <span className="font-mono text-white">
                  {selectedLog.ip_address || '127.0.0.1'}
                </span>
              </div>
              <div>
                <span className="text-sage-400 block mb-0.5 text-[11px] font-mono font-bold">User Agent</span>
                <span className="font-mono text-sage-200 truncate block text-[11px]">
                  {selectedLog.user_agent || 'FinLedger-AI/System'}
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold text-white mb-1.5 flex items-center gap-1.5 font-mono">
                <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                Appended Metadata Payload (JSON)
              </h4>
              <pre className="p-4 rounded-xl bg-forensic-950 border border-forensic-700 text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-60">
                {JSON.stringify(selectedLog.metadata_json, null, 2)}
              </pre>
            </div>

            <div className="pt-2 flex justify-end border-t border-forensic-700">
              <Button variant="primary" onClick={() => setSelectedLog(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

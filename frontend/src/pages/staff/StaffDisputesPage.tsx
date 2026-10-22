import React, { useState, useEffect } from 'react';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { PageHeader } from '../../components/common/PageHeader';
import { DISPUTE_CATEGORY_LABELS } from '../../components/customer/DisputeModal';
import { ReverseTransferPanel } from '../../components/staff/ReverseTransferPanel';
import { useAuth } from '../../context/AuthContext';
import { DisputeCategory, DisputeResponse } from '../../types/api';
import { disputesApi } from '../../api/disputes';
import { getErrorMessage } from '../../api/client';
import { formatDate } from '../../utils/formatters';
import { LifeBuoy } from 'lucide-react';

// Staff transitions accepted by DisputeStatusUpdateRequest (app/schemas/dispute.py)
type StaffDisputeStatus = 'INVESTIGATING' | 'RESOLVED' | 'REJECTED';

const STATUS: Record<string, { label: string; variant: 'warning' | 'info' | 'danger' | 'success' | 'neutral' }> = {
  OPEN: { label: 'Open', variant: 'warning' },
  INVESTIGATING: { label: 'Investigating', variant: 'info' },
  NEEDS_INFO: { label: 'Needs info', variant: 'danger' },
  RESOLVED: { label: 'Resolved', variant: 'success' },
  REJECTED: { label: 'Rejected', variant: 'neutral' },
};

const NEXT_STEPS: Record<StaffDisputeStatus, string> = {
  INVESTIGATING: 'Start investigating',
  RESOLVED: 'Resolve in the customer’s favour',
  REJECTED: 'Reject the claim',
};

const fieldClass =
  'w-full bg-forensic-900 border border-forensic-700 rounded px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500';

export const StaffDisputesPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [disputes, setDisputes] = useState<DisputeResponse[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nextStatus, setNextStatus] = useState<StaffDisputeStatus>('INVESTIGATING');
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const fetchDisputes = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await disputesApi.listDisputes();
      setDisputes(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDisputes();
  }, []);

  const selected = disputes.find((d) => d.id === selectedId) ?? null;
  const isClosed = selected?.status === 'RESOLVED' || selected?.status === 'REJECTED';

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    if (notes.trim().length < 3) {
      setError('Explain the decision (at least 3 characters). The customer sees it in their case history.');
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const updated = await disputesApi.updateStatus(selected.id, { status: nextStatus, notes: notes.trim() });
      setDisputes((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      setNotes('');
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const categoryLabel = (c: string) => DISPUTE_CATEGORY_LABELS[c as DisputeCategory] ?? c;
  const statusBadge = (s: string) => {
    const st = STATUS[s] ?? { label: s, variant: 'neutral' as const };
    return (
      <Badge variant={st.variant} size="sm">
        {st.label}
      </Badge>
    );
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Disputes"
        description="Customer claims about transfers. Every status change is recorded permanently with your note. A decision here never moves money by itself."
      />

      {error && <ErrorBanner message={error} onRetry={fetchDisputes} />}

      {isLoading ? (
        <div className="flex items-center justify-center p-16">
          <LoadingSpinner size="lg" />
        </div>
      ) : disputes.length === 0 ? (
        <EmptyState
          icon={<LifeBuoy className="w-6 h-6" />}
          title="No disputes"
          description="When a customer disputes a transfer it will appear here for review."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section aria-label="All disputes" className="space-y-3">
            {disputes.map((d) => (
              <button
                key={d.id}
                type="button"
                aria-pressed={d.id === selectedId}
                onClick={() => setSelectedId(d.id)}
                className={`w-full text-left p-4 rounded-lg border space-y-1.5 transition-colors cursor-pointer ${
                  d.id === selectedId ? 'bg-forensic-800 border-emerald-600' : 'bg-forensic-850 border-forensic-700 hover:border-emerald-700'
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-100">{categoryLabel(d.category)}</span>
                  {statusBadge(d.status)}
                </span>
                <span className="block text-sm text-slate-400 line-clamp-2">{d.description}</span>
                <span className="block text-xs text-slate-500">Opened {formatDate(d.created_at)}</span>
              </button>
            ))}
          </section>

          {selected && (
            <div className="lg:col-span-2 space-y-6">
              <Card variant="forensic" title={categoryLabel(selected.category)} subtitle={`Opened ${formatDate(selected.created_at)}`} action={statusBadge(selected.status)}>
                <div className="space-y-5 text-sm">
                  <dl className="space-y-1.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-slate-400">Transfer</dt>
                      <dd className="font-mono text-xs text-slate-200 truncate max-w-[280px]" title={selected.transfer_request_id}>
                        {selected.transfer_request_id}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-slate-400">Customer</dt>
                      <dd className="font-mono text-xs text-slate-200 truncate max-w-[280px]">{selected.customer_id}</dd>
                    </div>
                  </dl>
                  <blockquote className="p-4 rounded bg-forensic-900 border-l-4 border-emerald-600 text-slate-200 leading-relaxed">
                    {selected.description}
                  </blockquote>

                  <section aria-label="Case history">
                    <h3 className="font-semibold text-slate-100 mb-3">Case history</h3>
                    <ol className="border-l border-forensic-700 ml-1.5 space-y-4">
                      {selected.events.map((evt) => (
                        <li key={evt.id} className="pl-5 relative">
                          <span className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-emerald-400" aria-hidden="true" />
                          <p className="text-xs text-slate-400">
                            {evt.actor_role === 'CUSTOMER' ? 'Customer' : 'Staff'}, {formatDate(evt.created_at)}
                            {evt.to_status && evt.from_status !== evt.to_status ? `, status ${STATUS[evt.to_status]?.label ?? evt.to_status}` : ''}
                          </p>
                          <p className="text-slate-200 leading-relaxed">{evt.notes || evt.event_type}</p>
                        </li>
                      ))}
                    </ol>
                  </section>
                </div>
              </Card>

              {!isClosed && (
                <Card variant="forensic" title="Update the case">
                  <form onSubmit={handleUpdate} className="space-y-3">
                    <div role="radiogroup" aria-label="New status" className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {(Object.keys(NEXT_STEPS) as StaffDisputeStatus[]).map((s) => (
                        <button
                          key={s}
                          type="button"
                          role="radio"
                          aria-checked={nextStatus === s}
                          onClick={() => setNextStatus(s)}
                          className={`p-2.5 rounded text-sm border transition-colors cursor-pointer ${
                            nextStatus === s ? 'bg-forest-800 border-emerald-600 text-white' : 'bg-forensic-900 border-forensic-700 text-slate-300 hover:border-emerald-700'
                          }`}
                        >
                          {NEXT_STEPS[s]}
                        </button>
                      ))}
                    </div>
                    <label htmlFor="dispute-staff-notes" className="block text-sm text-slate-300">
                      Note to the customer
                    </label>
                    <textarea
                      id="dispute-staff-notes"
                      rows={3}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="What you checked and what happens next."
                      className={`${fieldClass} resize-none`}
                    />
                    {nextStatus === 'RESOLVED' && (
                      <p className="text-xs text-amber-200">
                        Resolving records the outcome only. To return the money, an admin reverses the transfer below.
                      </p>
                    )}
                    <div className="flex justify-end">
                      <Button type="submit" variant="primary" size="sm" isLoading={isSaving}>
                        Save decision
                      </Button>
                    </div>
                  </form>
                </Card>
              )}

              {isAdmin ? (
                <Card variant="forensic" title="Correct the ledger" subtitle="Admins only. Use when the claim is upheld and the money should go back.">
                  <ReverseTransferPanel transferId={selected.transfer_request_id} />
                </Card>
              ) : (
                <p className="text-sm text-slate-400">
                  If the claim is upheld, ask an admin to reverse the transfer. Reversals post a new correcting entry.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

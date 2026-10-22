import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { PageHeader } from '../../components/common/PageHeader';
import { DISPUTE_CATEGORY_LABELS } from '../../components/customer/DisputeModal';
import { DisputeCategory, DisputeResponse } from '../../types/api';
import { disputesApi } from '../../api/disputes';
import { getErrorMessage } from '../../api/client';
import { formatDate, formatDateOnly } from '../../utils/formatters';
import { Link } from 'react-router-dom';
import { ShieldAlert, Send } from 'lucide-react';

export const DisputesPage: React.FC = () => {
  const [disputes, setDisputes] = useState<DisputeResponse[]>([]);
  const [selectedDispute, setSelectedDispute] = useState<DisputeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noteContent, setNoteContent] = useState('');
  const [isSubmittingNote, setIsSubmittingNote] = useState(false);

  const fetchDisputes = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await disputesApi.listDisputes();
      setDisputes(data);
      if (data.length > 0 && !selectedDispute) {
        setSelectedDispute(data[0]);
      } else if (selectedDispute) {
        const updated = data.find((d: DisputeResponse) => d.id === selectedDispute.id);
        if (updated) setSelectedDispute(updated);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDisputes();
  }, []);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDispute || !noteContent.trim()) return;

    setIsSubmittingNote(true);
    try {
      const updated = await disputesApi.addNote(selectedDispute.id, { notes: noteContent.trim() });
      setSelectedDispute(updated);
      setNoteContent('');
      fetchDisputes();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmittingNote(false);
    }
  };

  const STATUS: Record<string, { label: string; variant: 'warning' | 'info' | 'danger' | 'success' | 'neutral' }> = {
    OPEN: { label: 'Open', variant: 'warning' },
    INVESTIGATING: { label: 'Under review', variant: 'info' },
    NEEDS_INFO: { label: 'Needs your reply', variant: 'danger' },
    RESOLVED: { label: 'Resolved', variant: 'success' },
    REJECTED: { label: 'Closed', variant: 'neutral' },
  };

  const statusBadge = (status: string) => {
    const s = STATUS[status] ?? { label: status, variant: 'neutral' as const };
    return (
      <Badge variant={s.variant} size="sm">
        {s.label}
      </Badge>
    );
  };

  const categoryLabel = (category: string) =>
    DISPUTE_CATEGORY_LABELS[category as DisputeCategory] ?? category;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Disputes"
        description="Questions you've raised about transfers. Every update is added to the case history and can't be edited later."
        action={
          <Link to="/transfers">
            <Button variant="secondary" size="sm">
              Dispute a transfer
            </Button>
          </Link>
        }
      />

      {error && <ErrorBanner message={error} />}

      {isLoading ? (
        <div className="flex items-center justify-center p-16">
          <LoadingSpinner size="lg" />
        </div>
      ) : disputes.length === 0 ? (
        <EmptyState
          icon={<ShieldAlert className="w-6 h-6 text-copper-700" />}
          title="No disputes"
          description="If you don't recognise a transfer or something looks wrong, open it from your transfer history and choose Dispute."
          action={
            <Link to="/transfers">
              <Button variant="primary" size="sm">
                Go to transfers
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section aria-label="Your disputes" className="space-y-3">
            {disputes.map((disp) => {
              const isSelected = selectedDispute?.id === disp.id;
              return (
                <button
                  type="button"
                  key={disp.id}
                  aria-pressed={isSelected}
                  onClick={() => setSelectedDispute(disp)}
                  className={`w-full text-left p-4 rounded-lg border transition-colors space-y-2 cursor-pointer ${
                    isSelected
                      ? 'bg-forest-800 text-white border-forest-950'
                      : 'bg-surface text-ink-900 border-hairline hover:border-forest-700'
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-semibold ${isSelected ? 'text-white' : 'text-forest-950'}`}>
                      {categoryLabel(disp.category)}
                    </span>
                    {statusBadge(disp.status)}
                  </span>
                  <span className={`block line-clamp-2 text-sm ${isSelected ? 'text-sage-100' : 'text-ink-600'}`}>
                    {disp.description}
                  </span>
                  <span className={`block text-xs ${isSelected ? 'text-sage-200' : 'text-ink-500'}`}>
                    Opened {formatDateOnly(disp.created_at)}
                  </span>
                </button>
              );
            })}
          </section>

          <div className="lg:col-span-2">
            {selectedDispute && (
              <Card
                variant="paper"
                title={categoryLabel(selectedDispute.category)}
                subtitle={`Opened ${formatDate(selectedDispute.created_at)}`}
                action={statusBadge(selectedDispute.status)}
              >
                <div className="space-y-6">
                  <dl className="text-sm space-y-1.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-ink-600">Transfer</dt>
                      <dd className="font-mono text-xs text-ink-950 truncate max-w-[260px]" title={selectedDispute.transfer_request_id}>
                        {selectedDispute.transfer_request_id}
                      </dd>
                    </div>
                    {selectedDispute.transfer_amount && (
                      <div className="flex justify-between gap-4">
                        <dt className="text-ink-600">Amount</dt>
                        <dd>
                          <CurrencyDisplay amount={selectedDispute.transfer_amount} size="sm" />
                        </dd>
                      </div>
                    )}
                  </dl>

                  <blockquote className="p-4 rounded-md bg-parchment-50 border-l-4 border-forest-800 text-sm text-ink-900 leading-relaxed">
                    {selectedDispute.description}
                  </blockquote>

                  {selectedDispute.resolution_notes && (
                    <div className="p-4 rounded-md bg-sage-100 border border-moss-300 text-sm">
                      <h3 className="font-semibold text-forest-900">Outcome</h3>
                      <p className="mt-1 text-ink-900 leading-relaxed">{selectedDispute.resolution_notes}</p>
                    </div>
                  )}

                  <section aria-label="Case history">
                    <h3 className="text-sm font-semibold text-ink-900 mb-3">Case history</h3>
                    {selectedDispute.events.length === 0 ? (
                      <p className="text-sm text-ink-600">No updates yet.</p>
                    ) : (
                      <ol className="relative border-l border-hairline ml-1.5 space-y-4">
                        {selectedDispute.events.map((evt) => (
                          <li key={evt.id} className="pl-5 relative">
                            <span
                              className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-forest-800"
                              aria-hidden="true"
                            />
                            <p className="text-xs text-ink-500">
                              {evt.actor_role === 'CUSTOMER' ? 'You' : 'FinLedger team'}, {formatDate(evt.created_at)}
                            </p>
                            <p className="text-sm text-ink-900 leading-relaxed mt-0.5">
                              {evt.notes ||
                                (evt.to_status ? `Status changed to ${STATUS[evt.to_status]?.label ?? evt.to_status}.` : 'Case updated.')}
                            </p>
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>

                  <form onSubmit={handleAddNote} className="space-y-2 pt-4 border-t border-hairline">
                    <label htmlFor="dispute-note" className="block text-sm font-medium text-ink-800">
                      Add information
                    </label>
                    <textarea
                      id="dispute-note"
                      rows={3}
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      placeholder="Anything that helps us investigate, such as when you noticed it or who you expected to pay."
                      className="w-full bg-surface border border-hairline rounded px-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 transition-colors resize-none"
                      required
                    />
                    <div className="flex justify-end">
                      <Button
                        type="submit"
                        variant="primary"
                        size="sm"
                        isLoading={isSubmittingNote}
                        leftIcon={<Send className="w-3.5 h-3.5" />}
                      >
                        Add to case
                      </Button>
                    </div>
                  </form>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

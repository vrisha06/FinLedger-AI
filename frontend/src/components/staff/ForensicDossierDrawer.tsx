import React, { useState, useEffect, useId } from 'react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { CurrencyDisplay } from '../common/CurrencyDisplay';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorBanner } from '../common/ErrorBanner';
import { fraudApi } from '../../api/fraud';
import { DossierAccount, ForensicDossierResponse, ForensicTimelineItem, InvestigationNoteType } from '../../types/api';
import { getErrorMessage } from '../../api/client';
import { formatDate } from '../../utils/formatters';
import { ReverseTransferPanel } from './ReverseTransferPanel';
import { X } from 'lucide-react';

interface ForensicDossierDrawerProps {
  alertId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onAlertReviewed?: () => void;
  /** Admins may post a CORRECTION_REVERSAL from the dossier */
  canReverse?: boolean;
}

type ReviewStatus = 'CLEARED' | 'CONFIRMED_FRAUD' | 'ESCALATED';

const NOTE_TYPES: Record<InvestigationNoteType, string> = {
  OBSERVATION: 'Observation',
  EVIDENCE: 'Evidence',
  CONCLUSION: 'Conclusion',
  ESCALATION: 'Escalation',
};

const DECISIONS: Record<ReviewStatus, string> = {
  CLEARED: 'Clear',
  ESCALATED: 'Escalate',
  CONFIRMED_FRAUD: 'Confirm fraud',
};

// Where each timeline entry comes from: facts vs model output vs human action
const TIMELINE_SOURCE: Record<ForensicTimelineItem['category'], { label: string; dot: string }> = {
  FACT: { label: 'Ledger fact', dot: 'bg-emerald-400' },
  HEURISTIC_RULE: { label: 'Rule', dot: 'bg-amber-400' },
  STATISTICAL_MODEL: { label: 'Model', dot: 'bg-purple-400' },
  GRAPH_TOPOLOGY: { label: 'LedgerGraph', dot: 'bg-sky-400' },
  INVESTIGATOR_ACTION: { label: 'Staff action', dot: 'bg-slate-200' },
};

const inputClass =
  'bg-forensic-950 border border-forensic-700 rounded px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500';

const AccountBlock: React.FC<{ label: string; account: DossierAccount }> = ({ label, account }) => (
  <div className="p-3 rounded-lg bg-forensic-850 border border-forensic-700 text-sm">
    <span className="block text-xs text-slate-400">{label}</span>
    <span className="block text-slate-100">{account.customer_legal_name}</span>
    <span className="block font-mono text-xs text-slate-300">{account.account_number}</span>
    <span className="block text-xs text-slate-400 mt-1">
      Balance now <CurrencyDisplay amount={account.cached_balance} size="sm" className="text-slate-200" />
    </span>
  </div>
);

export const ForensicDossierDrawer: React.FC<ForensicDossierDrawerProps> = ({ alertId, isOpen, onClose, onAlertReviewed, canReverse = false }) => {
  const titleId = useId();
  const [dossier, setDossier] = useState<ForensicDossierResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [noteType, setNoteType] = useState<InvestigationNoteType>('OBSERVATION');
  const [noteContent, setNoteContent] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);

  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>('CLEARED');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen && alertId) {
      loadDossier(alertId);
    } else {
      setDossier(null);
      setError(null);
    }
  }, [isOpen, alertId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  const loadDossier = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      setDossier(await fraudApi.getDossier(id));
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertId || noteContent.trim().length < 3) return;
    setIsAddingNote(true);
    setError(null);
    try {
      await fraudApi.addInvestigationNote(alertId, { note_type: noteType, content: noteContent.trim() });
      setNoteContent('');
      loadDossier(alertId);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleReviewDetermination = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertId) return;
    if (reviewNotes.trim().length < 3) {
      setError('Give a reason for the decision (at least 3 characters). It becomes part of the permanent record.');
      return;
    }
    setIsSubmittingReview(true);
    setError(null);
    try {
      await fraudApi.reviewAlert(alertId, { review_status: reviewStatus, review_notes: reviewNotes.trim() });
      setReviewNotes('');
      loadDossier(alertId);
      onAlertReviewed?.();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmittingReview(false);
    }
  };

  if (!isOpen) return null;

  const alert = dossier?.alert;
  const debits = dossier?.ledger_entries.filter((l) => l.entry_type === 'DEBIT').reduce((n, l) => n + Number(l.amount), 0) ?? 0;
  const credits = dossier?.ledger_entries.filter((l) => l.entry_type === 'CREDIT').reduce((n, l) => n + Number(l.amount), 0) ?? 0;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden theme-forensic">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-forensic-900 border-l border-forensic-700 shadow-2xl flex flex-col text-slate-100"
      >
        <div className="px-6 py-4 bg-forensic-850 border-b border-forensic-700 flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-slate-100">
              Forensic Investigation Dossier
            </h2>
            <p className="text-sm text-slate-400">Everything known about this transfer, with each item marked by where it came from.</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-forensic-800" aria-label="Close dossier">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-7">
          {error && <ErrorBanner message={error} />}

          {isLoading || !dossier || !alert ? (
            !error && (
              <div className="flex items-center justify-center p-16">
                <LoadingSpinner size="lg" />
              </div>
            )
          ) : (
            <>
              <section aria-label="Model assessment" className="space-y-3">
                <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-slate-400">Risk score</dt>
                    <dd className="text-lg font-semibold tabular-nums">{alert.risk_score}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">Assessment</dt>
                    <dd>{alert.decision.replace('_', ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">Review</dt>
                    <dd>{alert.review_status.replace('_', ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">Model</dt>
                    <dd className="font-mono text-xs truncate" title={alert.model_version}>{alert.model_version}</dd>
                  </div>
                </dl>
                <p className="text-sm text-slate-300 leading-relaxed">{alert.explanation}</p>
                {alert.rule_flags.length > 0 && (
                  <ul className="flex flex-wrap gap-1.5">
                    {alert.rule_flags.map((flag) => (
                      <li key={flag} className="text-xs px-2 py-0.5 rounded bg-forensic-850 border border-forensic-700 text-amber-300 font-mono">
                        {flag}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section aria-label="Transfer" className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-100">Transfer</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <AccountBlock label="From" account={dossier.source_account} />
                  <AccountBlock label="To" account={dossier.destination_account} />
                </div>
                <div className="rounded-lg border border-forensic-700 overflow-hidden">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Ledger entries for this transfer</caption>
                    <thead className="bg-forensic-850 text-left text-xs text-slate-400">
                      <tr>
                        <th scope="col" className="font-medium p-2.5">Account</th>
                        <th scope="col" className="font-medium p-2.5 text-right">Debit</th>
                        <th scope="col" className="font-medium p-2.5 text-right">Credit</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-forensic-700">
                      {dossier.ledger_entries.map((leg) => (
                        <tr key={leg.id}>
                          <td className="p-2.5 font-mono text-xs">{leg.account_number}</td>
                          <td className="p-2.5 text-right tabular-nums">{leg.entry_type === 'DEBIT' ? <CurrencyDisplay amount={leg.amount} size="sm" /> : ''}</td>
                          <td className="p-2.5 text-right tabular-nums">{leg.entry_type === 'CREDIT' ? <CurrencyDisplay amount={leg.amount} size="sm" /> : ''}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t border-forensic-700 text-xs">
                      <tr>
                        <th scope="row" className="p-2.5 text-left font-medium text-slate-400">Debits minus credits</th>
                        <td colSpan={2} className={`p-2.5 text-right tabular-nums font-semibold ${debits === credits ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {(debits - credits).toFixed(2)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </section>

              {dossier.graph_findings.length > 0 && (
                <section aria-label="LedgerGraph findings" className="space-y-2">
                  <h3 className="text-sm font-semibold text-slate-100">LedgerGraph findings</h3>
                  <ul className="space-y-2">
                    {dossier.graph_findings.map((gf) => (
                      <li key={gf.id} className="p-3 rounded-lg bg-forensic-850 border border-forensic-700 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold">{gf.pattern_type.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</span>
                          <Badge variant={gf.severity === 'CRITICAL' || gf.severity === 'HIGH' ? 'danger' : 'warning'} size="sm">
                            {gf.severity}
                          </Badge>
                        </div>
                        <p className="text-slate-300 mt-1">{gf.explanation}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section aria-label="Timeline" className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-100">Timeline</h3>
                <ol className="border-l border-forensic-700 ml-1.5 space-y-4">
                  {dossier.timeline.map((item, idx) => {
                    const src = TIMELINE_SOURCE[item.category] ?? { label: item.category, dot: 'bg-slate-400' };
                    return (
                      <li key={idx} className="pl-5 relative text-sm">
                        <span className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ${src.dot}`} aria-hidden="true" />
                        <p className="text-xs text-slate-400">
                          {src.label}, {formatDate(item.timestamp)}
                        </p>
                        <p className="font-medium text-slate-100">{item.title}</p>
                        <p className="text-slate-300">{item.detail}</p>
                      </li>
                    );
                  })}
                </ol>
              </section>

              {dossier.disputes.length > 0 && (
                <section aria-label="Customer disputes" className="space-y-2">
                  <h3 className="text-sm font-semibold text-slate-100">Customer disputes</h3>
                  <ul className="space-y-2">
                    {dossier.disputes.map((d) => (
                      <li key={d.id} className="p-3 rounded-lg bg-forensic-850 border border-forensic-700 text-sm">
                        <span className="text-xs text-slate-400">
                          {d.category}, {d.status.toLowerCase()}, {formatDate(d.created_at)}
                        </span>
                        <p className="text-slate-200 mt-0.5">{d.description}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section aria-label="Investigation notes" className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-100">Notes ({dossier.investigation_notes.length})</h3>
                {dossier.investigation_notes.length > 0 && (
                  <ul className="space-y-2">
                    {dossier.investigation_notes.map((note) => (
                      <li key={note.id} className="p-3 rounded-lg bg-forensic-850 border border-forensic-700 text-sm">
                        <span className="text-xs text-slate-400">
                          {NOTE_TYPES[note.note_type] ?? note.note_type}, {formatDate(note.created_at)}
                        </span>
                        <p className="text-slate-200 mt-0.5">{note.content}</p>
                      </li>
                    ))}
                  </ul>
                )}
                <form onSubmit={handleAddNote} className="flex flex-col sm:flex-row gap-2">
                  <label className="sr-only" htmlFor="note-type">Note type</label>
                  <select id="note-type" value={noteType} onChange={(e) => setNoteType(e.target.value as InvestigationNoteType)} className={inputClass}>
                    {(Object.keys(NOTE_TYPES) as InvestigationNoteType[]).map((t) => (
                      <option key={t} value={t}>{NOTE_TYPES[t]}</option>
                    ))}
                  </select>
                  <label className="sr-only" htmlFor="note-content">Note</label>
                  <input
                    id="note-content"
                    type="text"
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                    placeholder="What did you find?"
                    className={`${inputClass} flex-1`}
                  />
                  <Button variant="secondary" size="sm" type="submit" isLoading={isAddingNote} disabled={noteContent.trim().length < 3}>
                    Add note
                  </Button>
                </form>
              </section>

              {dossier.audit_events.length > 0 && (
                <section aria-label="Audit trail" className="space-y-2">
                  <h3 className="text-sm font-semibold text-slate-100">Audit trail</h3>
                  <ul className="text-sm divide-y divide-forensic-700">
                    {dossier.audit_events.map((ev) => (
                      <li key={ev.id} className="py-2 flex justify-between gap-4">
                        <span className="font-mono text-xs text-slate-200">{ev.action}</span>
                        <span className="text-xs text-slate-400 whitespace-nowrap">{formatDate(ev.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section aria-label="Decision" className="p-5 rounded-lg bg-forensic-850 border border-forensic-700 space-y-3">
                <h3 className="text-sm font-semibold text-slate-100">Decision</h3>
                <p className="text-sm text-slate-400">
                  Your decision updates the alert only. It never moves money or changes the customer&apos;s account.
                </p>
                <form onSubmit={handleReviewDetermination} className="space-y-3">
                  <div role="radiogroup" aria-label="Decision" className="grid grid-cols-3 gap-2">
                    {(Object.keys(DECISIONS) as ReviewStatus[]).map((st) => (
                      <button
                        key={st}
                        type="button"
                        role="radio"
                        aria-checked={reviewStatus === st}
                        onClick={() => setReviewStatus(st)}
                        className={`p-2.5 rounded text-sm border transition-colors cursor-pointer ${
                          reviewStatus === st
                            ? 'bg-forest-800 border-emerald-600 text-white'
                            : 'bg-forensic-900 border-forensic-700 text-slate-300 hover:border-emerald-700'
                        }`}
                      >
                        {DECISIONS[st]}
                      </button>
                    ))}
                  </div>
                  <label className="block text-sm text-slate-300" htmlFor="review-notes">
                    Reason
                  </label>
                  <textarea
                    id="review-notes"
                    rows={2}
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="What did you check, and why this decision?"
                    className={`${inputClass} w-full resize-none`}
                  />
                  <div className="flex justify-end">
                    <Button variant="primary" size="sm" type="submit" isLoading={isSubmittingReview}>
                      Commit Determination
                    </Button>
                  </div>
                </form>
              </section>

              {canReverse && (
                <section aria-label="Correct the ledger" className="p-5 rounded-lg bg-forensic-850 border border-forensic-700 space-y-3">
                  <h3 className="text-sm font-semibold text-slate-100">Correct the ledger</h3>
                  <ReverseTransferPanel transferId={dossier.transfer.id} onReversed={() => alertId && loadDossier(alertId)} />
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

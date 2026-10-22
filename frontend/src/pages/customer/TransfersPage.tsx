import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { DateDisplay } from '../../components/common/DateDisplay';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { PageHeader } from '../../components/common/PageHeader';
import { TransferModal } from '../../components/customer/TransferModal';
import { DisputeModal } from '../../components/customer/DisputeModal';
import { Account, TransferHistoryItem } from '../../types/api';
import { accountsApi } from '../../api/accounts';
import { transfersApi } from '../../api/transfers';
import { getErrorMessage } from '../../api/client';
import { ArrowRightLeft, ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE = 20;

export const TransfersPage: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transfers, setTransfers] = useState<TransferHistoryItem[]>([]);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [disputeTarget, setDisputeTarget] = useState<TransferHistoryItem | null>(null);

  const fetchData = async (pageNum = page) => {
    setIsLoading(true);
    setError(null);
    try {
      const [accs, history] = await Promise.all([
        accountsApi.listAccounts(),
        transfersApi.listTransfers(PAGE_SIZE, pageNum * PAGE_SIZE),
      ]);
      setAccounts(accs);
      setTransfers(history);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData(page);
  }, [page]);

  const myAccountIds = new Set(accounts.map((a) => a.id));

  const describe = (t: TransferHistoryItem) => {
    if (t.idempotency_key.startsWith('reversal-')) return { label: 'Correction: earlier transfer reversed', sign: myAccountIds.has(t.destination_account_id) ? ('plus' as const) : ('minus' as const) };
    const fromMine = myAccountIds.has(t.source_account_id);
    const toMine = myAccountIds.has(t.destination_account_id);
    if (t.destination_account_number.startsWith('INR-INV-')) return { label: 'Investment purchase', sign: 'minus' as const };
    if (fromMine && toMine) return { label: 'Between your accounts', sign: 'none' as const };
    if (fromMine) return { label: `To ${t.destination_account_number}`, sign: 'minus' as const };
    return { label: `From ${t.source_account_number}`, sign: 'plus' as const };
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Transfers"
        description="Everything you've sent and received, including attempts that were declined. Declined attempts never move money but are kept on record."
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={() => setTransferModalOpen(true)}
            leftIcon={<ArrowRightLeft className="w-4 h-4" />}
            disabled={accounts.length === 0}
          >
            New transfer
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={() => fetchData()} />}

      <Card
        variant="paper"
        title="History"
        action={
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-600">Page {page + 1}</span>
            <Button
              variant="secondary"
              size="sm"
              className="px-2"
              aria-label="Previous page"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="px-2"
              aria-label="Next page"
              onClick={() => setPage((p) => p + 1)}
              disabled={transfers.length < PAGE_SIZE || isLoading}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        }
      >
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : transfers.length === 0 ? (
          <EmptyState
            icon={<ArrowRightLeft className="w-6 h-6 text-forest-700" />}
            title="No transfers yet"
            description={
              accounts.length === 0
                ? 'Open an account and add a deposit before sending money.'
                : 'Send money to another account and it will show up here.'
            }
            action={
              accounts.length > 0 ? (
                <Button variant="primary" size="sm" onClick={() => setTransferModalOpen(true)}>
                  New transfer
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-500 border-b border-hairline">
                  <th scope="col" className="font-medium py-2 px-4 sm:px-5">Date</th>
                  <th scope="col" className="font-medium py-2 px-4">Details</th>
                  <th scope="col" className="font-medium py-2 px-4">Status</th>
                  <th scope="col" className="font-medium py-2 px-4 text-right">Amount</th>
                  <th scope="col" className="py-2 px-4 sm:px-5">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline-subtle">
                {transfers.map((t) => {
                  const { label, sign } = describe(t);
                  const failed = t.status === 'FAILED';
                  const reversed = t.status === 'REVERSED';
                  const isCorrection = t.idempotency_key.startsWith('reversal-');
                  return (
                    <tr key={t.id} className="align-top">
                      <td className="py-3 px-4 sm:px-5">
                        <DateDisplay date={t.posted_at || t.created_at} />
                      </td>
                      <td className="py-3 px-4">
                        <span className="block text-ink-900">{label}</span>
                        {failed && t.failure_reason && (
                          <span className="block text-xs text-rose-800 mt-0.5 max-w-sm">{t.failure_reason}</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={failed ? 'danger' : reversed ? 'warning' : 'success'} size="sm">
                          {failed ? 'Declined' : reversed ? 'Reversed' : 'Posted'}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <CurrencyDisplay
                          amount={t.amount}
                          size="sm"
                          sign={failed || reversed ? 'none' : sign}
                          colored={!failed && !reversed}
                          className={failed || reversed ? 'text-ink-400 line-through' : ''}
                        />
                      </td>
                      <td className="py-3 px-4 sm:px-5 text-right">
                        {!failed && !reversed && !isCorrection && (
                          <Button variant="ghost" size="sm" onClick={() => setDisputeTarget(t)}>
                            Dispute
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <TransferModal
        isOpen={transferModalOpen}
        onClose={() => setTransferModalOpen(false)}
        accounts={accounts}
        onTransferSuccess={() => fetchData()}
      />

      {disputeTarget && (
        <DisputeModal
          isOpen={true}
          onClose={() => setDisputeTarget(null)}
          transferId={disputeTarget.id}
          transferAmount={disputeTarget.amount}
        />
      )}
    </div>
  );
};

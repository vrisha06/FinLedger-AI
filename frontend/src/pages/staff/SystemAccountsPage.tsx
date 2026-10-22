import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Modal } from '../../components/common/Modal';
import { PageHeader } from '../../components/common/PageHeader';
import { Account, LedgerEntry } from '../../types/api';
import { accountsApi } from '../../api/accounts';
import { getErrorMessage } from '../../api/client';
import { Search, RefreshCw, FileText } from 'lucide-react';

export const SystemAccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [customerFilter, setCustomerFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [inspectAccount, setInspectAccount] = useState<Account | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([]);
  const [isLoadingLedger, setIsLoadingLedger] = useState(false);

  const fetchAccounts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await accountsApi.listAccounts(customerFilter.trim() || undefined);
      setAccounts(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleInspectLedger = async (acc: Account) => {
    setInspectAccount(acc);
    setIsLoadingLedger(true);
    try {
      const entries = await accountsApi.getAccountLedger(acc.id, 50, 0);
      setLedgerEntries(entries);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoadingLedger(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Every account in the system, including the internal clearing account. Open one to see its postings."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchAccounts}
            leftIcon={<RefreshCw className="w-3.5 h-3.5 text-stone-400" />}
          >
            Refresh
          </Button>
        }
      />

      {/* Filter by Customer UUID */}
      <div className="p-4 rounded-xl bg-forensic-850 border border-forensic-700 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            fetchAccounts();
          }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-2.5 w-4 h-4 text-sage-400" />
            <input
              type="text"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
              placeholder="Filter by customer ID"
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg pl-10 pr-3.5 py-2 text-xs font-mono text-white placeholder:text-sage-400/60 focus:outline-none focus:border-forest-500"
            />
          </div>
          <Button variant="primary" type="submit" size="sm" className="font-semibold shadow-xs">
            Filter
          </Button>
          {customerFilter && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setCustomerFilter('');
                accountsApi.listAccounts().then(setAccounts).catch(() => {});
              }}
              className="font-semibold"
            >
              Clear
            </Button>
          )}
        </form>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchAccounts} />}

      {/* Accounts Table */}
      <Card
        title={`All accounts (${accounts.length})`}
        subtitle="Stored balance and row version, straight from the accounts table. The clearing account is negative by design: it funds every deposit."
        variant="forensic"
      >
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : accounts.length === 0 ? (
          <div className="p-8 text-center text-xs text-sage-400 font-mono">
            No accounts found matching search criteria.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-forensic-700">
            <table className="w-full text-left text-xs">
              <thead className="bg-forensic-900 text-[11px] text-sage-300 border-b border-forensic-700 font-bold font-mono">
                <tr>
                  <th className="py-2.5 px-3">Account Number</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Customer Reference</th>
                  <th className="py-2.5 px-3 text-right">Cached Balance</th>
                  <th className="py-2.5 px-3 text-center">Version</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-forensic-750 font-mono">
                {accounts.map((acc) => (
                  <tr key={acc.id} className="hover:bg-forensic-800/70 transition-colors">
                    <td className="py-3 px-3">
                      <span className="font-bold text-white block">
                        {acc.account_number}
                      </span>
                      <span className="text-[11px] text-sage-400 truncate max-w-[150px] block">
                        ID: {acc.id}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-sans">
                      <Badge
                        variant={
                          acc.account_type === 'SAVINGS'
                            ? 'evergreen'
                            : acc.account_type === 'INVESTMENT'
                            ? 'purple'
                            : acc.account_type === 'INTERNAL_CLEARING'
                            ? 'info'
                            : 'neutral'
                        }
                        size="sm"
                      >
                        {acc.account_type}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-sage-200 text-[11px] truncate max-w-[120px]">
                      {acc.customer_id || 'SYSTEM'}
                    </td>
                    <td className="py-3 px-3 text-right tabular-nums">
                      <CurrencyDisplay amount={acc.cached_balance} size="sm" colored />
                    </td>
                    <td className="py-3 px-3 text-center text-sage-300 font-semibold tabular-nums">
                      v{acc.version}
                    </td>
                    <td className="py-3 px-3 text-center font-sans">
                      <Badge variant={acc.status === 'ACTIVE' ? 'evergreen' : 'danger'} size="sm">
                        {acc.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-right font-sans">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleInspectLedger(acc)}
                        leftIcon={<FileText className="w-3.5 h-3.5 text-sage-300" />}
                        className="text-xs font-semibold"
                      >
                        Ledger
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Ledger Inspection Modal */}
      {inspectAccount && (
        <Modal
          isOpen={!!inspectAccount}
          onClose={() => setInspectAccount(null)}
          title={`Ledger Postings: ${inspectAccount.account_number}`}
          description={`Double-entry postings recorded for Account UUID: ${inspectAccount.id}`}
          maxWidth="xl"
        >
          {isLoadingLedger ? (
            <LoadingSkeleton rows={4} />
          ) : ledgerEntries.length === 0 ? (
            <p className="p-6 text-center text-xs text-sage-400 font-mono">
              Zero ledger entries recorded for this account.
            </p>
          ) : (
            <div className="overflow-x-auto border border-forensic-700 rounded-lg">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-forensic-900 text-[11px] text-sage-300 border-b border-forensic-700 font-bold">
                  <tr>
                    <th className="py-2.5 px-3">Seq #</th>
                    <th className="py-2.5 px-3">Leg</th>
                    <th className="py-2.5 px-3">Transaction ID</th>
                    <th className="py-2.5 px-3 text-right">Amount</th>
                    <th className="py-2.5 px-3 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-forensic-750">
                  {ledgerEntries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-forensic-800/70 transition-colors">
                      <td className="py-2.5 px-3 text-sage-400 font-bold tabular-nums">
                        #{entry.sequence_num}
                      </td>
                      <td className="py-2.5 px-3 font-sans">
                        <Badge
                          variant={entry.entry_type === 'CREDIT' ? 'evergreen' : 'danger'}
                          size="sm"
                        >
                          {entry.entry_type}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-sage-200 text-[11px] truncate max-w-[120px]">
                        {entry.transaction_id}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        <CurrencyDisplay
                          amount={entry.amount}
                          sign={entry.entry_type === 'CREDIT' ? 'plus' : 'minus'}
                          colored
                          size="sm"
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right text-sage-300">
                        <DateDisplay date={entry.created_at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 pt-3 border-t border-forensic-700 flex justify-end">
            <Button variant="primary" onClick={() => setInspectAccount(null)}>
              Close
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { DepositModal } from '../../components/customer/DepositModal';
import { Account, LedgerEntry } from '../../types/api';
import { accountsApi } from '../../api/accounts';
import { getErrorMessage } from '../../api/client';
import { Wallet, ArrowDownCircle, RefreshCw, ChevronLeft, ChevronRight, Scale, Plus } from 'lucide-react';

export const AccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([]);

  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true);
  const [isLoadingLedger, setIsLoadingLedger] = useState(false);
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(0);
  const pageSize = 15;

  const [depositModalOpen, setDepositModalOpen] = useState(false);
  const [depositAccount, setDepositAccount] = useState<Account | null>(null);

  const fetchAccounts = async () => {
    setIsLoadingAccounts(true);
    setError(null);
    try {
      const data = await accountsApi.listAccounts();
      setAccounts(data);
      if (data.length > 0 && !selectedAccountId) {
        setSelectedAccountId(data[0].id);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  const handleCreateAccount = async (accountType: 'SAVINGS' | 'CURRENT' = 'SAVINGS') => {
    setIsCreatingAccount(true);
    setError(null);
    try {
      const newAcc = await accountsApi.createAccount(accountType);
      await fetchAccounts();
      setSelectedAccountId(newAcc.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsCreatingAccount(false);
    }
  };

  const fetchLedger = async (accId: string, pageNum: number) => {
    if (!accId) return;
    setIsLoadingLedger(true);
    setError(null);
    try {
      const entries = await accountsApi.getAccountLedger(accId, pageSize, pageNum * pageSize);
      setLedgerEntries(entries);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoadingLedger(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      fetchLedger(selectedAccountId, page);
    }
  }, [selectedAccountId, page]);

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

  // Compute page-level debit & credit sums strictly for visible entries
  const pageDebits = ledgerEntries
    .filter((e) => e.entry_type === 'DEBIT')
    .reduce((sum, e) => sum + parseFloat(String(e.amount)), 0);

  const pageCredits = ledgerEntries
    .filter((e) => e.entry_type === 'CREDIT')
    .reduce((sum, e) => sum + parseFloat(String(e.amount)), 0);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Accounts & statements"
        description="Choose an account to see every posting made to it. Entries are permanent; corrections appear as new entries."
        action={
          <div className="flex items-center gap-2 flex-wrap">
            {selectedAccount && selectedAccount.account_type === 'SAVINGS' && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setDepositAccount(selectedAccount);
                  setDepositModalOpen(true);
                }}
                leftIcon={<ArrowDownCircle className="w-4 h-4" />}
              >
                Deposit funds
              </Button>
            )}
            {accounts.length > 0 && (
              <Button
                variant="primary"
                size="sm"
                isLoading={isCreatingAccount}
                onClick={() => handleCreateAccount('CURRENT')}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                Open current account
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                fetchAccounts();
                if (selectedAccountId) fetchLedger(selectedAccountId, page);
              }}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchAccounts} />}

      {isLoadingAccounts ? (
        <LoadingSkeleton rows={2} />
      ) : accounts.length === 0 ? (
        <EmptyState
          icon={<Wallet className="w-6 h-6 text-forest-800" />}
          title="You don't have an account yet"
          description="Open a savings account to get started. You can add an opening deposit straight after."
          action={
            <Button
              variant="primary"
              size="md"
              isLoading={isCreatingAccount}
              onClick={() => handleCreateAccount('SAVINGS')}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Open savings account
            </Button>
          }
        />
      ) : (
        <section aria-label="Your accounts">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((acc) => {
              const isSelected = acc.id === selectedAccountId;
              return (
                <button
                  type="button"
                  key={acc.id}
                  aria-pressed={isSelected}
                  onClick={() => {
                    setSelectedAccountId(acc.id);
                    setPage(0);
                  }}
                  className={`p-5 rounded-lg text-left border transition-colors flex flex-col gap-4 cursor-pointer ${
                    isSelected
                      ? 'bg-forest-800 text-white border-forest-950 shadow-hero'
                      : 'bg-surface text-ink-900 border-hairline hover:border-forest-700 shadow-atelier'
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className={`font-mono text-sm font-semibold ${isSelected ? 'text-white' : 'text-forest-950'}`}>
                      {acc.account_number}
                    </span>
                    <span className={`text-xs ${isSelected ? 'text-sage-100' : 'text-ink-500'}`}>
                      {acc.account_type === 'SAVINGS' ? 'Savings' : acc.account_type === 'CURRENT' ? 'Current' : acc.account_type}
                      {acc.status !== 'ACTIVE' && `, ${acc.status.toLowerCase()}`}
                    </span>
                  </span>
                  <span>
                    <span className={`block text-xs ${isSelected ? 'text-sage-100' : 'text-ink-500'}`}>Balance</span>
                    <CurrencyDisplay
                      amount={acc.cached_balance}
                      size="xl"
                      className={isSelected ? 'text-white' : 'text-forest-950'}
                    />
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {selectedAccount && (
        <Card
          variant="paper"
          title={`Statement for ${selectedAccount.account_number}`}
          subtitle="Newest first."
          action={
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-600">Page {page + 1}</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || isLoadingLedger}
                className="px-2"
                aria-label="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={ledgerEntries.length < pageSize || isLoadingLedger}
                className="px-2"
                aria-label="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          }
        >
          {isLoadingLedger ? (
            <LoadingSkeleton rows={5} />
          ) : ledgerEntries.length === 0 ? (
            <EmptyState
              icon={<Scale className="w-6 h-6 text-forest-800" />}
              title="No postings yet"
              description="Deposits and transfers into or out of this account will be listed here."
            />
          ) : (
            <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink-500 border-b border-hairline">
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5">Date</th>
                    <th scope="col" className="font-medium py-2 px-4">Entry</th>
                    <th scope="col" className="font-medium py-2 px-4">Transaction ID</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Money out</th>
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5 text-right">Money in</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline-subtle">
                  {ledgerEntries.map((entry) => {
                    const isCredit = entry.entry_type === 'CREDIT';
                    return (
                      <tr key={entry.id}>
                        <td className="py-3 px-4 sm:px-5">
                          <DateDisplay date={entry.created_at} />
                        </td>
                        <td className="py-3 px-4 text-ink-800">{isCredit ? 'Credit' : 'Debit'}</td>
                        <td className="py-3 px-4 font-mono text-xs text-ink-600 max-w-[180px] truncate" title={entry.transaction_id}>
                          {entry.transaction_id}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {!isCredit ? (
                            <CurrencyDisplay amount={entry.amount} sign="minus" colored size="sm" />
                          ) : (
                            <span className="text-ink-300">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4 sm:px-5 text-right">
                          {isCredit ? (
                            <CurrencyDisplay amount={entry.amount} sign="plus" colored size="sm" />
                          ) : (
                            <span className="text-ink-300">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t border-hairline bg-parchment-50">
                    <th scope="row" colSpan={3} className="py-3 px-4 sm:px-5 text-left text-xs font-medium text-ink-600">
                      Totals for this page ({ledgerEntries.length} {ledgerEntries.length === 1 ? 'entry' : 'entries'})
                    </th>
                    <td className="py-3 px-4 text-right">
                      <CurrencyDisplay amount={pageDebits} sign="minus" colored size="sm" />
                    </td>
                    <td className="py-3 px-4 sm:px-5 text-right">
                      <CurrencyDisplay amount={pageCredits} sign="plus" colored size="sm" />
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </Card>
      )}

      <DepositModal
        isOpen={depositModalOpen}
        onClose={() => setDepositModalOpen(false)}
        account={depositAccount}
        onDepositSuccess={() => {
          fetchAccounts();
          if (selectedAccountId) fetchLedger(selectedAccountId, page);
        }}
      />
    </div>
  );
};

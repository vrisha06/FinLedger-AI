import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { DateDisplay } from '../../components/common/DateDisplay';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { TransferModal } from '../../components/customer/TransferModal';
import { DepositModal } from '../../components/customer/DepositModal';
import { AssetAllocationMeter } from '../../components/common/AssetAllocationMeter';
import { Card } from '../../components/common/Card';
import { PageHeader } from '../../components/common/PageHeader';
import { Account, CustomerFinancialSummary, LedgerEntry, PortfolioSummary } from '../../types/api';
import { accountsApi } from '../../api/accounts';
import { investmentsApi } from '../../api/investments';
import { reportsApi } from '../../api/reports';
import { getErrorMessage } from '../../api/client';
import { Link } from 'react-router-dom';
import {
  Wallet,
  ArrowRightLeft,
  ArrowDownCircle,
  PieChart,
  ShieldCheck,
  Receipt,
  Plus,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

export const CustomerDashboard: React.FC = () => {
  const { user } = useAuth();

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [, setSummary] = useState<CustomerFinancialSummary | null>(null);
  const [recentLedger, setRecentLedger] = useState<LedgerEntry[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [depositModalOpen, setDepositModalOpen] = useState(false);
  const [selectedDepositAccount, setSelectedDepositAccount] = useState<Account | null>(null);

  const handleCreateSavingsAccount = async () => {
    setIsCreatingAccount(true);
    setError(null);
    try {
      await accountsApi.createAccount('SAVINGS');
      await fetchData();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsCreatingAccount(false);
    }
  };

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [accs, port, sum] = await Promise.all([
        accountsApi.listAccounts(),
        investmentsApi.getPortfolio().catch(() => null),
        reportsApi.getCustomerSummary().catch(() => null),
      ]);

      setAccounts(accs);
      setPortfolio(port);
      setSummary(sum);

      if (accs.length > 0) {
        const activePrimary = accs.find((a) => a.account_type === 'SAVINGS') || accs[0];
        const entries = await accountsApi.getAccountLedger(activePrimary.id, 6, 0);
        setRecentLedger(entries);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const totalSavings = accounts
    .filter((a) => a.account_type === 'SAVINGS' || a.account_type === 'CURRENT')
    .reduce((sum, a) => sum + parseFloat(String(a.cached_balance)), 0);

  const totalInvested = portfolio ? parseFloat(String(portfolio.total_invested)) : 0;
  const totalNetWorth = totalSavings + totalInvested;

  const handleOpenDeposit = (acc?: Account) => {
    const target = acc || accounts.find((a) => a.account_type === 'SAVINGS') || accounts[0] || null;
    setSelectedDepositAccount(target);
    setDepositModalOpen(true);
  };

  const firstName = (user?.customer?.full_name || user?.username || '').split(' ')[0];
  const savingsCount = accounts.filter((a) => a.account_type === 'SAVINGS' || a.account_type === 'CURRENT').length;
  const investmentCount = portfolio?.active_investments_count || 0;
  const statementAccount = accounts.find((a) => a.account_type === 'SAVINGS') || accounts[0];

  return (
    <div className="space-y-8">
      <PageHeader
        title={firstName ? `Hello, ${firstName}` : 'Overview'}
        description="Your balances, accounts and latest ledger activity."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleOpenDeposit()}
              leftIcon={<ArrowDownCircle className="w-4 h-4" />}
              disabled={accounts.length === 0}
            >
              Deposit funds
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setTransferModalOpen(true)}
              leftIcon={<ArrowRightLeft className="w-4 h-4" />}
              disabled={accounts.length === 0}
            >
              New transfer
            </Button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {/* The one bold surface on the page: what you hold */}
      {isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : (
        <section className="ledger-hero-green rounded-lg p-6 sm:p-8" aria-label="Balance summary">
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
            <div>
              <p className="text-sm text-sage-100">Total balance</p>
              <CurrencyDisplay amount={totalNetWorth} size="2xl" className="block mt-1 text-white sm:text-5xl" />
              <p className="text-sm text-sage-100 mt-3 max-w-md leading-relaxed">
                Your cash accounts plus everything you have invested, calculated from committed ledger postings.
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-3 sm:min-w-[400px]">
              <div className="rounded-md bg-white/10 border border-white/15 p-4">
                <dt className="flex items-center gap-1.5 text-xs text-sage-100">
                  <Wallet className="w-3.5 h-3.5" aria-hidden="true" /> Cash
                </dt>
                <dd className="mt-1">
                  <CurrencyDisplay amount={totalSavings} size="lg" className="text-white" />
                  <span className="block text-xs text-sage-200 mt-1">
                    {savingsCount} {savingsCount === 1 ? 'account' : 'accounts'}
                  </span>
                </dd>
              </div>
              <div className="rounded-md bg-white/10 border border-white/15 p-4">
                <dt className="flex items-center gap-1.5 text-xs text-sage-100">
                  <PieChart className="w-3.5 h-3.5" aria-hidden="true" /> Investments
                </dt>
                <dd className="mt-1">
                  <CurrencyDisplay amount={totalInvested} size="lg" className="text-white" />
                  <span className="block text-xs text-sage-200 mt-1">
                    {investmentCount} {investmentCount === 1 ? 'holding' : 'holdings'}
                  </span>
                </dd>
              </div>
            </dl>
          </div>

          <p className="mt-6 pt-4 border-t border-white/15 flex items-start gap-2 text-xs text-sage-100">
            <ShieldCheck className="w-4 h-4 shrink-0 text-sage-200" aria-hidden="true" />
            A transfer either posts both its debit and its credit, or nothing at all. Posted entries can
            never be edited or deleted.
          </p>
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card
            variant="paper"
            title="Your accounts"
            action={
              accounts.length > 0 && accounts.length < 3 ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleCreateSavingsAccount}
                  isLoading={isCreatingAccount}
                  leftIcon={<Plus className="w-3.5 h-3.5" />}
                >
                  Open savings account
                </Button>
              ) : undefined
            }
          >
            {isLoading ? (
              <LoadingSkeleton rows={3} />
            ) : accounts.length === 0 ? (
              <EmptyState
                icon={<Wallet className="w-6 h-6 text-forest-700" />}
                title="You don't have an account yet"
                description="Open a savings account, then add an opening deposit to start making transfers."
                action={
                  <Button variant="primary" size="sm" onClick={handleCreateSavingsAccount} isLoading={isCreatingAccount}>
                    Open savings account
                  </Button>
                }
              />
            ) : (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {accounts.map((acc) => (
                  <li
                    key={acc.id}
                    className="p-4 rounded-md bg-white border border-hairline border-l-4 border-l-forest-800 flex flex-col gap-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-sm font-semibold text-forest-950">{acc.account_number}</span>
                      <Badge variant="sage" size="sm">{acc.account_type}</Badge>
                    </div>
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <div>
                        <span className="block text-xs text-ink-500">Available balance</span>
                        <CurrencyDisplay amount={acc.cached_balance} size="lg" className="text-forest-950" />
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Button variant="secondary" size="sm" onClick={() => handleOpenDeposit(acc)}>
                          Deposit
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setTransferModalOpen(true)}>
                          Transfer
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            variant="paper"
            title="Recent activity"
            subtitle={statementAccount ? `Latest postings on ${statementAccount.account_number}` : undefined}
            action={
              <Link to="/accounts" className="text-sm font-semibold text-forest-800 hover:underline flex items-center gap-1 whitespace-nowrap">
                Full statement <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </Link>
            }
          >
            {isLoading ? (
              <LoadingSkeleton rows={4} />
            ) : recentLedger.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-600">
                Nothing posted yet. Your first deposit will appear here.
              </p>
            ) : (
              <div className="overflow-x-auto -mx-4 sm:-mx-5">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-ink-500 border-b border-hairline">
                      <th scope="col" className="font-medium py-2 px-4 sm:px-5">Date</th>
                      <th scope="col" className="font-medium py-2 px-4">Entry</th>
                      <th scope="col" className="font-medium py-2 px-4 text-right">Money out</th>
                      <th scope="col" className="font-medium py-2 px-4 sm:px-5 text-right">Money in</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline-subtle">
                    {recentLedger.map((entry) => {
                      const isDebit = entry.entry_type === 'DEBIT';
                      return (
                        <tr key={entry.id}>
                          <td className="py-3 px-4 sm:px-5">
                            <DateDisplay date={entry.created_at} />
                          </td>
                          <td className="py-3 px-4 text-ink-800">{isDebit ? 'Debit' : 'Credit'}</td>
                          <td className="py-3 px-4 text-right">
                            {isDebit ? (
                              <CurrencyDisplay amount={entry.amount} sign="minus" colored size="sm" />
                            ) : (
                              <span className="text-ink-300">—</span>
                            )}
                          </td>
                          <td className="py-3 px-4 sm:px-5 text-right">
                            {!isDebit ? (
                              <CurrencyDisplay amount={entry.amount} sign="plus" colored size="sm" />
                            ) : (
                              <span className="text-ink-300">—</span>
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
        </div>

        <div className="space-y-6">
          <Card variant="paper" title="Where your money is">
            <AssetAllocationMeter savingsAmount={totalSavings} investedAmount={totalInvested} showLegend={true} />
          </Card>

          <Card variant="paper" title="How your balance is kept">
            <div className="space-y-3 text-sm text-ink-700 leading-relaxed">
              <p>
                Your account is money the bank owes you, so a <strong className="text-ink-950">debit lowers</strong> your
                balance and a <strong className="text-ink-950">credit raises</strong> it.
              </p>
              <p>
                Deposits are balanced against the bank&apos;s clearing account, so money never appears from nowhere. If a
                transfer is sent twice, the second request returns the first result instead of charging you again.
              </p>
            </div>
          </Card>

          <nav aria-label="Shortcuts" className="space-y-3">
            <Link
              to="/products"
              className="p-4 rounded-md bg-surface border border-hairline hover:border-forest-700 transition-colors flex items-center justify-between gap-3 group"
            >
              <span className="flex items-center gap-3">
                <Sparkles className="w-4 h-4 text-forest-800" aria-hidden="true" />
                <span>
                  <span className="block text-sm font-semibold text-forest-950">Explore investments</span>
                  <span className="block text-xs text-ink-500">Fixed deposits, mutual funds and treasury bills</span>
                </span>
              </span>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:text-forest-800" aria-hidden="true" />
            </Link>
            <Link
              to="/disputes"
              className="p-4 rounded-md bg-surface border border-hairline hover:border-copper-700 transition-colors flex items-center justify-between gap-3 group"
            >
              <span className="flex items-center gap-3">
                <Receipt className="w-4 h-4 text-copper-700" aria-hidden="true" />
                <span>
                  <span className="block text-sm font-semibold text-forest-950">Question a transaction</span>
                  <span className="block text-xs text-ink-500">Open a dispute and follow its progress</span>
                </span>
              </span>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:text-copper-700" aria-hidden="true" />
            </Link>
          </nav>
        </div>
      </div>

      {/* Transfer Modal with PayeeGuard */}
      <TransferModal
        isOpen={transferModalOpen}
        onClose={() => setTransferModalOpen(false)}
        accounts={accounts}
        onTransferSuccess={fetchData}
      />

      {/* Deposit Modal */}
      <DepositModal
        isOpen={depositModalOpen}
        onClose={() => setDepositModalOpen(false)}
        account={selectedDepositAccount}
        onDepositSuccess={fetchData}
      />
    </div>
  );
};

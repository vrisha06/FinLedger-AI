import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { getErrorMessage } from '../api/client';
import { Lock, User, Eye, EyeOff } from 'lucide-react';

// Seeded by backend/scripts/seed_users.py (shared demo password)
const DEMO_PASSWORD = 'Password123!';
const DEMO_ACCOUNTS = [
  { role: 'Customer', username: 'rahul_sharma', hint: 'Accounts, transfers, investments' },
  { role: 'Staff', username: 'priya_investigator', hint: 'Fraud alerts and investigations' },
  { role: 'Admin', username: 'admin_system', hint: 'Reconciliation and audit trail' },
];

const SAMPLE_POSTING = [
  { account: 'Rahul Sharma, savings', debit: '2,500.00', credit: '' },
  { account: 'Priya Nair, savings', debit: '', credit: '2,500.00' },
];

export const LoginPage: React.FC = () => {
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname;

  const signIn = async (identifier: string, secret: string) => {
    setError(null);
    setIsLoading(true);

    try {
      await login({ username_or_email: identifier.trim(), password: secret });

      const savedUserStr = localStorage.getItem('finledger_user');
      const savedUser = savedUserStr ? JSON.parse(savedUserStr) : null;

      if (from) {
        navigate(from, { replace: true });
      } else if (savedUser?.role === 'STAFF' || savedUser?.role === 'ADMIN') {
        navigate('/staff', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void signIn(usernameOrEmail, password);
  };

  const handleDemoSignIn = (username: string) => {
    setUsernameOrEmail(username);
    setPassword(DEMO_PASSWORD);
    void signIn(username, DEMO_PASSWORD);
  };

  return (
    <div className="min-h-screen bg-parchment-100 text-ink-950 flex flex-col justify-center items-center px-4 py-8 sm:py-16 font-sans">
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-stretch">
        {/* Left: what the system guarantees, shown as a real posting */}
        <section className="lg:col-span-7 ledger-hero-green rounded-lg p-6 sm:p-9 flex flex-col justify-between gap-8">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded bg-white/10 border border-white/20 font-serif font-bold text-sm flex items-center justify-center">
                FL
              </div>
              <span className="font-serif font-semibold text-lg tracking-tight">FinLedger</span>
            </div>

            <h1 className="mt-8 font-serif text-3xl sm:text-[2.6rem] leading-[1.1] font-semibold tracking-tight max-w-[16ch]">
              Every rupee is recorded twice.
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-sage-100 max-w-[52ch]">
              Each transfer writes a matching debit and credit. PostgreSQL refuses to commit any
              transaction whose two sides don&apos;t agree, and the fraud model can only advise staff,
              never move money.
            </p>
          </div>

          <figure className="rounded-md bg-forest-950/50 border border-white/15 overflow-hidden">
            <figcaption className="flex items-center justify-between px-4 py-2.5 border-b border-white/15 text-xs text-sage-100">
              <span>Transfer of ₹2,500.00, as the ledger stores it</span>
              <span className="text-sage-200">Posted</span>
            </figcaption>
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="text-left text-xs text-sage-200">
                  <th scope="col" className="font-medium px-4 pt-3 pb-2">Account</th>
                  <th scope="col" className="font-medium px-4 pt-3 pb-2 text-right">Debit</th>
                  <th scope="col" className="font-medium px-4 pt-3 pb-2 text-right">Credit</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_POSTING.map((leg) => (
                  <tr key={leg.account} className="border-t border-white/10">
                    <td className="px-4 py-2.5">{leg.account}</td>
                    <td className="px-4 py-2.5 text-right text-copper-300">{leg.debit}</td>
                    <td className="px-4 py-2.5 text-right text-forest-200">{leg.credit}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-white/25">
                  <th scope="row" className="px-4 py-3 text-left font-medium text-sage-100">
                    Debits minus credits
                  </th>
                  <td colSpan={2} className="px-4 py-3 text-right font-serif text-xl">
                    0.00
                  </td>
                </tr>
              </tfoot>
            </table>
          </figure>
        </section>

        {/* Right: sign in */}
        <section className="order-first lg:order-none lg:col-span-5 bg-surface border border-hairline rounded-lg p-6 sm:p-8 flex flex-col justify-between shadow-atelier">
          <div>
            <h2 className="text-2xl font-serif font-semibold text-ink-950">Sign in</h2>
            <p className="text-sm text-ink-600 mt-1">Use your username or email address.</p>

            {error && <ErrorBanner message={error} className="mt-5" />}

            <form onSubmit={handleSubmit} className="space-y-4 mt-6">
              <div>
                <label htmlFor="login-identifier" className="block text-sm font-medium text-ink-800 mb-1.5">
                  Username or email
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="login-identifier"
                    type="text"
                    autoComplete="username"
                    value={usernameOrEmail}
                    onChange={(e) => setUsernameOrEmail(e.target.value)}
                    className="w-full bg-parchment-50 border border-hairline rounded pl-9 pr-3 py-2 text-sm text-ink-950 focus:outline-none focus:border-forest-800 focus:bg-white transition-colors"
                    required
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password" className="block text-sm font-medium text-ink-800 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-parchment-50 border border-hairline rounded pl-9 pr-10 py-2 text-sm text-ink-950 focus:outline-none focus:border-forest-800 focus:bg-white transition-colors"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute right-2 top-1.5 p-1 rounded text-ink-500 hover:text-ink-800"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <Button type="submit" variant="primary" size="lg" isLoading={isLoading} className="w-full">
                Sign in
              </Button>
            </form>

            <div className="mt-8 pt-5 border-t border-hairline">
              <h3 className="text-sm font-medium text-ink-800">Demo accounts</h3>
              <p className="text-xs text-ink-500 mt-0.5">
                Signs in straight away. All use the password <span className="font-mono">{DEMO_PASSWORD}</span>
              </p>
              <ul className="mt-3 divide-y divide-hairline-subtle border border-hairline rounded">
                {DEMO_ACCOUNTS.map((demo) => (
                  <li key={demo.username}>
                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() => handleDemoSignIn(demo.username)}
                      className="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-mist-100 transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      <span>
                        <span className="block text-sm font-medium text-forest-900">{demo.role}</span>
                        <span className="block text-xs text-ink-500">{demo.hint}</span>
                      </span>
                      <span className="font-mono text-xs text-ink-600">{demo.username}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <p className="mt-6 text-sm text-ink-600">
            New customer?{' '}
            <Link to="/register" className="text-forest-800 font-semibold hover:underline">
              Create an account
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
};

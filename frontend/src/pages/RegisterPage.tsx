import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { getErrorMessage } from '../api/client';
import { User, Mail, Lock, CheckCircle2, CreditCard, Phone } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [panNumber, setPanNumber] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Use a password of at least 8 characters.');
      return;
    }

    if (panNumber.trim() && !/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(panNumber.trim())) {
      setError('Enter a PAN in the format ABCDE1234F, or leave it blank.');
      return;
    }

    setIsLoading(true);
    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
        pan_number: panNumber.trim().toUpperCase() || undefined,
      });

      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass =
    'w-full bg-parchment-50 border border-hairline rounded pl-9 pr-3 py-2 text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none focus:border-forest-800 focus:bg-white transition-colors';
  const labelClass = 'block text-sm font-medium text-ink-800 mb-1.5';

  return (
    <div className="min-h-screen bg-parchment text-ink-900 flex flex-col justify-center items-center px-4 py-8 sm:py-16 font-sans">
      <div className="w-full max-w-2xl bg-surface border border-hairline rounded-lg p-6 sm:p-8 shadow-atelier">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-8 h-8 rounded bg-forest-800 text-white font-serif font-bold text-sm flex items-center justify-center">
            FL
          </div>
          <span className="font-serif font-semibold text-lg text-ink-950">FinLedger</span>
        </div>
        <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-ink-950">Create your account</h1>
        <p className="text-sm text-ink-600 mt-1">
          After you sign in you can open a savings account and add an opening deposit.
        </p>

        {error && <ErrorBanner message={error} className="mt-5" />}

        {success ? (
          <div className="mt-6 p-8 text-center space-y-3 bg-sage-100 border border-moss-300 rounded-md" role="status">
            <CheckCircle2 className="w-10 h-10 text-forest-800 mx-auto" aria-hidden="true" />
            <h2 className="text-lg font-serif font-semibold text-forest-900">You&apos;re registered</h2>
            <p className="text-sm text-forest-800">Taking you to sign in…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 mt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="reg-name" className={labelClass}>
                  Full name
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-name"
                    type="text"
                    autoComplete="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Aarav Sharma"
                    className={inputClass}
                    required
                  />
                </div>
              </div>
              <div>
                <label htmlFor="reg-username" className={labelClass}>
                  Username
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-username"
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="aarav_sharma"
                    className={inputClass}
                    required
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="reg-email" className={labelClass}>
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="aarav@example.com"
                    className={inputClass}
                    required
                  />
                </div>
              </div>
              <div>
                <label htmlFor="reg-password" className={labelClass}>
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputClass}
                    aria-describedby="reg-password-hint"
                    required
                  />
                </div>
                <p id="reg-password-hint" className="text-xs text-ink-500 mt-1">
                  At least 8 characters.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="reg-phone" className={labelClass}>
                  Phone <span className="font-normal text-ink-500">(optional)</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-phone"
                    type="tel"
                    autoComplete="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    className={inputClass}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="reg-pan" className={labelClass}>
                  PAN <span className="font-normal text-ink-500">(optional)</span>
                </label>
                <div className="relative">
                  <CreditCard className="absolute left-3 top-2.5 w-4 h-4 text-ink-400" aria-hidden="true" />
                  <input
                    id="reg-pan"
                    type="text"
                    maxLength={10}
                    value={panNumber}
                    onChange={(e) => setPanNumber(e.target.value.toUpperCase())}
                    placeholder="ABCDE1234F"
                    className={`${inputClass} font-mono`}
                  />
                </div>
              </div>
            </div>

            <Button type="submit" variant="primary" size="lg" isLoading={isLoading} className="w-full mt-2">
              Create account
            </Button>
          </form>
        )}

        <p className="mt-6 text-sm text-ink-600">
          Already registered?{' '}
          <Link to="/login" className="text-forest-800 font-semibold hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};

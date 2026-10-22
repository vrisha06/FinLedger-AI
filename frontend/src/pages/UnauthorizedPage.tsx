import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';

export const UnauthorizedPage: React.FC = () => {
  const { isStaff } = useAuth();

  return (
    <main className="min-h-screen bg-parchment flex flex-col items-center justify-center p-6 text-center">
      <p className="font-serif text-6xl font-semibold text-copper-700">403</p>
      <h1 className="mt-3 text-2xl font-serif font-semibold text-ink-950">You don&apos;t have access to this page</h1>
      <p className="text-sm text-ink-600 max-w-sm mt-2 mb-6">
        It&apos;s only available to {isStaff ? 'customers' : 'FinLedger staff'}. The server checks your role on every
        request, so changing the address won&apos;t help.
      </p>
      <Link to={isStaff ? '/staff' : '/dashboard'}>
        <Button variant="primary">Back to your overview</Button>
      </Link>
    </main>
  );
};

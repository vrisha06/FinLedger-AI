import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/common/Button';

export const NotFoundPage: React.FC = () => {
  return (
    <main className="min-h-screen bg-parchment flex flex-col items-center justify-center p-6 text-center">
      <p className="font-serif text-6xl font-semibold text-forest-800">404</p>
      <h1 className="mt-3 text-2xl font-serif font-semibold text-ink-950">This page doesn&apos;t exist</h1>
      <p className="text-sm text-ink-600 max-w-sm mt-2 mb-6">Check the address, or go back to your overview.</p>
      <Link to="/">
        <Button variant="primary">Go to overview</Button>
      </Link>
    </main>
  );
};

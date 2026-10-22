import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const isStaffSection = location.pathname.startsWith('/staff');

  return (
    <div
      className={`min-h-screen flex flex-col transition-colors duration-150 ${
        isStaffSection
          ? 'theme-forensic bg-forensic-900 text-slate-100'
          : 'bg-parchment text-ink-900'
      }`}
    >
      <Navbar onToggleSidebar={() => setSidebarOpen((prev) => !prev)} isStaffSection={isStaffSection} />
      <div className="flex-1 flex">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} isStaffSection={isStaffSection} />
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

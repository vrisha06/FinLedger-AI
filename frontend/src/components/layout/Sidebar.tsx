import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Wallet,
  ArrowRightLeft,
  Sparkles,
  PieChart,
  ShieldAlert,
  Users,
  FileText,
  Scale,
  BarChart3,
  GitBranch,
  FlaskConical,
  Activity,
  LifeBuoy,
} from 'lucide-react';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  isStaffSection?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose, isStaffSection = false }) => {
  const { isStaff } = useAuth();

  const customerNav = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Accounts & statements', path: '/accounts', icon: Wallet },
    { name: 'Transfers', path: '/transfers', icon: ArrowRightLeft },
    { name: 'Investment products', path: '/products', icon: Sparkles },
    { name: 'Portfolio', path: '/portfolio', icon: PieChart },
    { name: 'Disputes', path: '/disputes', icon: LifeBuoy },
  ];

  const staffNav = [
    { name: 'Overview', path: '/staff', icon: LayoutDashboard },
    { name: 'Fraud alerts', path: '/staff/fraud', icon: ShieldAlert },
    { name: 'LedgerGraph', path: '/staff/graph', icon: GitBranch },
    { name: 'Fraud Lab', path: '/staff/fraud-lab', icon: FlaskConical },
    { name: 'Disputes', path: '/staff/disputes', icon: LifeBuoy },
    { name: 'Model health', path: '/staff/ai-health', icon: Activity },
    { name: 'Accounts', path: '/staff/accounts', icon: Users },
    { name: 'Audit trail', path: '/staff/audit', icon: FileText },
    { name: 'Reconciliation', path: '/staff/reconciliation', icon: Scale },
    { name: 'Reports', path: '/staff/reports', icon: BarChart3 },
  ];

  const navItems = isStaff ? staffNav : customerNav;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink-950/60 z-40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed md:sticky top-14 z-40 h-[calc(100vh-3.5rem)] w-60 shrink-0 p-3 flex flex-col justify-between transition-transform duration-200 md:translate-x-0 ${
          isStaffSection
            ? 'bg-forensic-900 border-r border-forensic-700 text-slate-100'
            : 'bg-paper-50 border-r border-eucalyptus-300 text-ink-900 shadow-atelier'
        } ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/dashboard' || item.path === '/staff'}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2.5 rounded text-sm transition-colors ${
                      isActive
                        ? isStaffSection
                          ? 'bg-forensic-800 text-emerald-300 border border-forensic-700 font-bold border-l-4 border-l-emerald-400 shadow-xs [&_svg]:text-emerald-300 [&_span]:text-emerald-300'
                          : 'sidebar-nav-active bg-forest-800 text-white border border-forest-950 font-bold border-l-4 border-l-sage-200 shadow-sm [&_svg]:text-white [&_span]:text-white'
                        : isStaffSection
                        ? 'text-slate-300 hover:text-white hover:bg-forensic-800 font-medium [&_svg]:text-slate-400'
                        : 'sidebar-nav-inactive text-ink-800 hover:text-forest-900 hover:bg-mist-100 font-medium [&_svg]:text-forest-700'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <p
          className={`px-3 text-[11px] leading-relaxed ${isStaffSection ? 'text-slate-500' : 'text-ink-500'}`}
        >
          {isStaff
            ? "Fraud scores are advisory. Only staff decisions change an alert's status."
            : 'All amounts in Indian rupees. Every posting is double-entry and permanent.'}
        </p>
      </aside>
    </>
  );
};

import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { LogOut, User as UserIcon, Menu } from 'lucide-react';

interface NavbarProps {
  onToggleSidebar?: () => void;
  isStaffSection?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar, isStaffSection = false }) => {
  const { user, logout, isCustomer, isStaff } = useAuth();

  const roleVariant = isStaff ? 'purple' : isCustomer ? 'success' : 'neutral';

  return (
    <header
      className={`sticky top-0 z-30 w-full transition-colors ${
        isStaffSection
          ? 'bg-forensic-900 border-b border-forensic-700 text-slate-100'
          : 'bg-paper-50 border-b border-eucalyptus-300 text-ink-900 shadow-xs'
      }`}
    >
      <div className="flex items-center justify-between px-4 sm:px-6 h-14">
        <div className="flex items-center gap-3">
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className={`md:hidden p-1.5 rounded transition-colors ${
                isStaffSection
                  ? 'text-slate-400 hover:text-white hover:bg-forensic-800'
                  : 'text-forest-800 hover:text-forest-950 hover:bg-mist-100'
              }`}
              aria-label="Toggle navigation"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}

          <div className="flex items-center gap-3">
            {/* Atelier Crest / Monogram */}
            <div
              className={`w-8 h-8 rounded flex items-center justify-center font-bold text-xs transition-colors ${
                isStaffSection
                  ? 'bg-forensic-800 border border-forensic-700 text-emerald-400 font-mono'
                  : 'bg-forest-800 text-white font-serif border border-forest-950 shadow-sm'
              }`}
            >
              FL
            </div>

            <div className="flex items-baseline gap-2">
              <span
                className={`tracking-tight ${
                  isStaffSection ? 'font-sans font-semibold text-sm text-slate-100' : 'font-serif font-semibold text-lg text-forest-950'
                }`}
              >
                FinLedger
              </span>
              <span className={`hidden sm:inline text-xs ${isStaffSection ? 'text-slate-400' : 'text-ink-600'}`}>
                {isStaffSection ? 'Staff workspace' : 'Personal banking'}
              </span>
            </div>
          </div>
        </div>

        {/* Right user section */}
        {user && (
          <div className="flex items-center gap-3">
            <div
              className={`flex items-center gap-2 rounded px-2.5 py-1 border transition-colors ${
                isStaffSection
                  ? 'bg-forensic-800 border-forensic-700'
                  : 'bg-mist-100 border-eucalyptus-300'
              }`}
            >
              <div
                className={`w-6 h-6 rounded flex items-center justify-center ${
                  isStaffSection ? 'bg-forensic-750 text-slate-400' : 'bg-sage-200 text-forest-800'
                }`}
              >
                <UserIcon className="w-3.5 h-3.5" />
              </div>
              <div className="hidden sm:block text-left pr-1">
                <p
                  className={`text-xs font-medium ${
                    isStaffSection ? 'text-slate-200' : 'text-ink-900 font-serif'
                  }`}
                >
                  {user.customer?.full_name || user.username}
                </p>
                <p
                  className={`text-[11px] ${
                    isStaffSection ? 'text-slate-400' : 'text-ink-500'
                  }`}
                >
                  {user.email}
                </p>
              </div>
              <Badge variant={roleVariant} size="sm" className="hidden sm:inline-flex">
                {user.role}
              </Badge>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={logout}
              leftIcon={<LogOut className="w-3.5 h-3.5" />}
              className="text-xs"
            >
              Sign out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
};

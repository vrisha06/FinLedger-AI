import React from 'react';
import { CurrencyDisplay } from './CurrencyDisplay';
import { Wallet, PieChart } from 'lucide-react';

interface AssetAllocationMeterProps {
  savingsAmount: number;
  investedAmount: number;
  className?: string;
  showLegend?: boolean;
}

export const AssetAllocationMeter: React.FC<AssetAllocationMeterProps> = ({
  savingsAmount,
  investedAmount,
  className = '',
  showLegend = true,
}) => {
  const total = savingsAmount + investedAmount;
  const savingsPct = total > 0 ? (savingsAmount / total) * 100 : 100;
  const investedPct = total > 0 ? (investedAmount / total) * 100 : 0;

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Proportion Bar with Double-Entry Balance Divider */}
      <div className="space-y-1.5">
        <div className="flex justify-between items-center text-xs font-medium text-ink-700">
          <span className="flex items-center gap-1.5 text-forest-800">
            <span className="w-2 h-2 rounded-full bg-forest-800"></span>
            Savings {savingsPct.toFixed(0)}%
          </span>
          <span className="flex items-center gap-1.5 text-copper-800">
            <span className="w-2 h-2 rounded-full bg-copper-700"></span>
            Investments {investedPct.toFixed(0)}%
          </span>
        </div>

        {/* Precision Progress Track */}
        <div className="h-3 w-full bg-parchment-200 rounded-sm overflow-hidden flex border border-hairline p-0.5">
          <div
            style={{ width: `${savingsPct}%` }}
            className="h-full bg-forest-800 rounded-sm transition-all duration-300"
            title={`Liquid Savings: ₹${savingsAmount.toLocaleString('en-IN')}`}
          />
          {investedPct > 0 && (
            <div
              style={{ width: `${investedPct}%` }}
              className="h-full bg-copper-700 rounded-sm ml-0.5 transition-all duration-300"
              title={`Invested Assets: ₹${investedAmount.toLocaleString('en-IN')}`}
            />
          )}
        </div>
      </div>

      {showLegend && (
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-hairline font-sans text-xs">
          <div className="p-2.5 rounded bg-sage-50 border border-moss-300 flex items-start gap-2">
            <Wallet className="w-3.5 h-3.5 text-forest-800 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-forest-800 block">Savings</span>
              <CurrencyDisplay amount={savingsAmount} size="sm" className="font-semibold text-ink-950" />
            </div>
          </div>

          <div className="p-2.5 rounded bg-clay-100 border border-copper-200 flex items-start gap-2">
            <PieChart className="w-3.5 h-3.5 text-copper-800 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-copper-800 block">Investments</span>
              <CurrencyDisplay amount={investedAmount} size="sm" className="font-semibold text-ink-950" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

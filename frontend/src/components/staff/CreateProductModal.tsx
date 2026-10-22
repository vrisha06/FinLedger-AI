import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ErrorBanner } from '../common/ErrorBanner';
import { FinancialProduct, ProductType } from '../../types/api';
import { productsApi } from '../../api/products';
import { getErrorMessage } from '../../api/client';

interface CreateProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProductCreated?: (newProduct: FinancialProduct) => void;
}

export const CreateProductModal: React.FC<CreateProductModalProps> = ({
  isOpen,
  onClose,
  onProductCreated,
}) => {
  const [name, setName] = useState<string>('');
  const [code, setCode] = useState<string>('');
  const [productType, setProductType] = useState<ProductType>('FIXED_DEPOSIT');
  const [annualYieldRate, setAnnualYieldRate] = useState<string>('7.50');
  const [minAmount, setMinAmount] = useState<string>('10000.00');
  const [termMonths, setTermMonths] = useState<string>('12');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const yieldRate = parseFloat(annualYieldRate);
    const minAmt = parseFloat(minAmount);
    const months = parseInt(termMonths, 10);

    if (isNaN(yieldRate) || yieldRate < 0 || yieldRate > 100) {
      setError('Annual yield rate must be between 0.00% and 100.00%');
      return;
    }

    if (isNaN(minAmt) || minAmt <= 0) {
      setError('Minimum amount must be greater than ₹0.00');
      return;
    }

    if (isNaN(months) || months <= 0) {
      setError('Term duration must be at least 1 month');
      return;
    }

    setIsLoading(true);
    try {
      const created = await productsApi.createProduct({
        name: name.trim(),
        code: code.trim().toUpperCase(),
        product_type: productType,
        annual_yield_rate: yieldRate.toFixed(2),
        min_amount: minAmt.toFixed(2),
        term_months: months,
        is_active: true,
      });

      onProductCreated?.(created);
      onClose();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Financial Product"
      description="Add a simulated investment product to the system catalogue."
      maxWidth="md"
    >
      {error && <ErrorBanner message={error} className="mb-4" />}

      <form onSubmit={handleSubmit} className="space-y-4 font-sans">
        <div>
          <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
            Product Display Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. 1-Year High Yield Fixed Deposit"
            className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3.5 py-2 text-xs text-white placeholder:text-sage-400/60 focus:outline-none focus:border-forest-500 font-sans"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
              Product Code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. FD-12M-PREM"
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3.5 py-2 text-xs font-mono text-white placeholder:text-sage-400/60 focus:outline-none focus:border-forest-500"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
              Category
            </label>
            <select
              value={productType}
              onChange={(e) => setProductType(e.target.value as ProductType)}
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none focus:border-forest-500 font-sans"
            >
              <option value="FIXED_DEPOSIT">Fixed Deposit</option>
              <option value="RECURRING_DEPOSIT">Recurring Deposit</option>
              <option value="MUTUAL_FUND">Mutual Fund</option>
              <option value="TREASURY_BILL">Treasury Bill</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
              Yield Rate (% p.a.)
            </label>
            <input
              type="number"
              step="0.01"
              value={annualYieldRate}
              onChange={(e) => setAnnualYieldRate(e.target.value)}
              placeholder="7.50"
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-forest-500"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
              Min Amount (₹)
            </label>
            <input
              type="number"
              step="0.01"
              value={minAmount}
              onChange={(e) => setMinAmount(e.target.value)}
              placeholder="10000.00"
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-forest-500"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-sage-300 mb-1.5 font-mono">
              Term (Months)
            </label>
            <input
              type="number"
              value={termMonths}
              onChange={(e) => setTermMonths(e.target.value)}
              placeholder="12"
              className="w-full bg-forensic-900 border border-forensic-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-forest-500"
              required
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-3 border-t border-forensic-700">
          <Button variant="outline" type="button" onClick={onClose} className="font-semibold">
            Cancel
          </Button>
          <Button variant="primary" type="submit" isLoading={isLoading} className="font-semibold shadow-xs">
            Create Product
          </Button>
        </div>
      </form>
    </Modal>
  );
};

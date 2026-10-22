/**
 * Financial and display formatting utilities for FinLedger-AI.
 * Strictly denominated in INR.
 */

export function formatINR(val: string | number | null | undefined): string {
  if (val === null || val === undefined || val === '') {
    return '₹0.00';
  }

  // Parse carefully
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) {
    return '₹0.00';
  }

  // Format with Indian locale number grouping
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatPercent(val: string | number | null | undefined): string {
  if (val === null || val === undefined || val === '') {
    return '0.00%';
  }
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return '0.00%';
  return `${num.toFixed(2)}%`;
}

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).format(d);
  } catch {
    return isoString;
  }
}

export function formatDateOnly(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(d);
  } catch {
    return isoString;
  }
}

export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback UUIDv4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Validate a typed rupee amount without going through floating point.
 * Accepts digits with up to 2 decimals (commas ignored) and returns the canonical
 * "1234.50" string the API expects, or null when invalid or not greater than zero.
 */
export function parseAmountInput(raw: string): string | null {
  const s = raw.trim().replace(/,/g, '');
  if (!/^\d{1,13}(\.\d{1,2})?$/.test(s)) return null;
  const [whole, frac = ''] = s.split('.');
  const canonical = `${whole.replace(/^0+(?=\d)/, '')}.${frac.padEnd(2, '0')}`;
  return canonical === '0.00' ? null : canonical;
}

import { describe, it, expect } from 'vitest';
import { formatINR, formatPercent, formatDate, generateUUID, parseAmountInput } from '../utils/formatters';

describe('formatters utility', () => {
  it('formats positive and zero INR amounts correctly with two decimals and grouping', () => {
    expect(formatINR(0)).toBe('₹0.00');
    expect(formatINR('0.00')).toBe('₹0.00');
    expect(formatINR(1000)).toBe('₹1,000.00');
    expect(formatINR('50000.50')).toBe('₹50,000.50');
    expect(formatINR(1000000)).toBe('₹10,00,000.00');
  });

  it('safely handles null and undefined values without crashing', () => {
    expect(formatINR(null)).toBe('₹0.00');
    expect(formatINR(undefined)).toBe('₹0.00');
    expect(formatINR('')).toBe('₹0.00');
  });

  it('formats percentages with exact two decimals', () => {
    expect(formatPercent(7.1)).toBe('7.10%');
    expect(formatPercent('8.50')).toBe('8.50%');
    expect(formatPercent(0)).toBe('0.00%');
  });

  it('generates valid UUIDv4 strings', () => {
    const uuid1 = generateUUID();
    const uuid2 = generateUUID();

    expect(uuid1).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(uuid2).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(uuid1).not.toBe(uuid2);
  });

  it('formats dates consistently', () => {
    const iso = '2026-10-11T12:00:00Z';
    const formatted = formatDate(iso);
    expect(formatted).toContain('2026');
    expect(formatted).toContain('Oct');
  });
});

describe('parseAmountInput', () => {
  it('normalises valid rupee amounts to two decimals', () => {
    expect(parseAmountInput('2500')).toBe('2500.00');
    expect(parseAmountInput(' 1,250.5 ')).toBe('1250.50');
    expect(parseAmountInput('0.01')).toBe('0.01');
    expect(parseAmountInput('007.10')).toBe('7.10');
  });

  it('rejects zero, negatives, extra precision and non-numbers', () => {
    expect(parseAmountInput('0')).toBeNull();
    expect(parseAmountInput('0.00')).toBeNull();
    expect(parseAmountInput('-5')).toBeNull();
    expect(parseAmountInput('10.005')).toBeNull();
    expect(parseAmountInput('1e3')).toBeNull();
    expect(parseAmountInput('')).toBeNull();
  });
});

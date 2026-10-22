import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ForensicDossierDrawer } from '../components/staff/ForensicDossierDrawer';
import { fraudApi } from '../api/fraud';
import { FraudAlert, ForensicDossierResponse } from '../types/api';

// Staff triage happens in the forensic dossier (the only review surface the triage queue opens)
const mockAlert: FraudAlert = {
  id: 'alert-1234-5678',
  transfer_request_id: 'transfer-9999',
  model_version: 'rf-v1.0.0',
  risk_score: '0.8500',
  decision: 'HIGH_RISK',
  rule_flags: ['AMOUNT_THRESHOLD_50K', 'RAPID_BURST'],
  feature_snapshot: { amount: 75000, hour_of_day: 2 },
  explanation: 'High transaction amount exceeding ₹50,000 threshold during off-hours.',
  review_status: 'PENDING',
  created_at: new Date().toISOString(),
};

const account = (id: string, number: string) => ({
  id,
  account_number: number,
  account_type: 'SAVINGS',
  cached_balance: '1000.00',
  customer_legal_name: 'Test Holder',
  status: 'ACTIVE',
});

const mockDossier: ForensicDossierResponse = {
  alert: mockAlert,
  transfer: {
    id: 'transfer-9999',
    idempotency_key: 'k',
    source_account_id: 'a1',
    destination_account_id: 'a2',
    amount: '75000.00',
    currency: 'INR',
    status: 'POSTED',
    created_at: new Date().toISOString(),
  },
  source_account: account('a1', 'INR-SAV-AAAA'),
  destination_account: account('a2', 'INR-SAV-BBBB'),
  ledger_entries: [],
  graph_findings: [],
  investigation_notes: [],
  audit_events: [],
  disputes: [],
  timeline: [],
};

describe('Fraud alert triage (forensic dossier)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(fraudApi, 'getDossier').mockResolvedValue(mockDossier);
  });

  it('renders risk score, decision, explanation and heuristic rule triggers', async () => {
    render(<ForensicDossierDrawer isOpen={true} onClose={vi.fn()} alertId={mockAlert.id} />);

    expect(await screen.findByText('0.8500')).toBeInTheDocument();
    expect(screen.getByText(/High risk/i)).toBeInTheDocument();
    expect(screen.getByText('AMOUNT_THRESHOLD_50K')).toBeInTheDocument();
    expect(screen.getByText('RAPID_BURST')).toBeInTheDocument();
    expect(screen.getByText(mockAlert.explanation)).toBeInTheDocument();
  });

  it('enforces a mandatory review reason before committing a triage decision', async () => {
    const reviewSpy = vi.spyOn(fraudApi, 'reviewAlert').mockResolvedValue({ ...mockAlert, review_status: 'ESCALATED' });
    const onReviewed = vi.fn();
    render(<ForensicDossierDrawer isOpen={true} onClose={vi.fn()} alertId={mockAlert.id} onAlertReviewed={onReviewed} />);

    const submitBtn = await screen.findByRole('button', { name: /commit determination/i });
    fireEvent.click(submitBtn);
    expect(await screen.findByText(/Give a reason for the decision/i)).toBeInTheDocument();
    expect(reviewSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('radio', { name: /escalate/i }));
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Off-hours burst to a new payee' } });
    fireEvent.click(submitBtn);

    await waitFor(() =>
      expect(reviewSpy).toHaveBeenCalledWith(mockAlert.id, {
        review_status: 'ESCALATED',
        review_notes: 'Off-hours burst to a new payee',
      })
    );
    expect(onReviewed).toHaveBeenCalled();
  });
});

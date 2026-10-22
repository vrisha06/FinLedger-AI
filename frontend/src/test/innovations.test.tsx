import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DisputeModal } from '../components/customer/DisputeModal';
import { ForensicDossierDrawer } from '../components/staff/ForensicDossierDrawer';
import { disputesApi } from '../api/disputes';
import { fraudApi } from '../api/fraud';
import { ForensicDossierResponse } from '../types/api';

describe('Innovation UI Components', () => {
  it('renders DisputeModal and submits dispute inquiry', async () => {
    const handleClose = vi.fn();
    const handleCreated = vi.fn();

    const createSpy = vi.spyOn(disputesApi, 'createDispute').mockResolvedValue({
      id: 'disp-test-1',
      customer_id: 'cust-1',
      transfer_request_id: 'tx-123',
      category: 'UNAUTHORIZED',
      description: 'Unrecognized ATM debit',
      status: 'OPEN',
      created_at: new Date().toISOString(),
      events: [],
    });

    render(
      <DisputeModal
        isOpen={true}
        onClose={handleClose}
        transferId="tx-123"
        onDisputeCreated={handleCreated}
      />
    );

    expect(screen.getByText(/Dispute a transfer/i)).toBeInTheDocument();
    expect(screen.getByText('tx-123')).toBeInTheDocument();

    const desc = screen.getByLabelText(/What happened\?/i);
    const submitBtn = screen.getByRole('button', { name: /Open dispute/i });

    // Backend requires at least 10 characters; the form says so before calling the API
    fireEvent.change(desc, { target: { value: 'too short' } });
    fireEvent.click(submitBtn);
    expect(await screen.findByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(createSpy).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/What's the problem\?/i), { target: { value: 'SUSPECTED_FRAUD' } });
    fireEvent.change(desc, { target: { value: 'Unauthorized fund transfer from unrecognized device.' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Dispute opened/i)).toBeInTheDocument();
    });
    expect(createSpy).toHaveBeenCalledWith({
      transfer_request_id: 'tx-123',
      category: 'SUSPECTED_FRAUD',
      description: 'Unauthorized fund transfer from unrecognized device.',
    });
    expect(handleCreated).toHaveBeenCalled();
  });

  it('renders ForensicDossierDrawer with double-entry legs and evidentiary timeline', async () => {
    const handleClose = vi.fn();

    const mockDossier: ForensicDossierResponse = {
      alert: {
        id: 'alt-1',
        transfer_request_id: 'tx-1',
        model_version: 'rf-v1.0.0',
        risk_score: '0.9200',
        decision: 'HIGH_RISK',
        rule_flags: ['RULE_ZSCORE_OUTLIER', 'GRAPH_RAPID_PASS_THROUGH'],
        feature_snapshot: {},
        explanation: 'Transaction volume is 6.2x higher than typical baseline.',
        review_status: 'PENDING',
        created_at: new Date().toISOString(),
      },
      transfer: {
        id: 'tx-1',
        idempotency_key: 'idemp-1',
        source_account_id: 'acc-src-1',
        destination_account_id: 'acc-dst-1',
        amount: '45000.00',
        currency: 'INR',
        status: 'POSTED',
        created_at: new Date().toISOString(),
      },
      source_account: {
        id: 'acc-src-1',
        account_number: 'ACC-SAV-111111',
        account_type: 'SAVINGS',
        cached_balance: '5000.00',
        customer_legal_name: 'Aarav Sharma',
        status: 'ACTIVE',
      },
      destination_account: {
        id: 'acc-dst-1',
        account_number: 'ACC-SAV-222222',
        account_type: 'SAVINGS',
        cached_balance: '45000.00',
        customer_legal_name: 'Meera Iyer',
        status: 'ACTIVE',
      },
      ledger_entries: [
        {
          id: 'leg-1',
          account_id: 'acc-src-1',
          account_number: 'ACC-SAV-111111',
          entry_type: 'DEBIT',
          amount: '45000.00',
          sequence_num: 1,
          created_at: new Date().toISOString(),
        },
        {
          id: 'leg-2',
          account_id: 'acc-dst-1',
          account_number: 'ACC-SAV-222222',
          entry_type: 'CREDIT',
          amount: '45000.00',
          sequence_num: 2,
          created_at: new Date().toISOString(),
        },
      ],
      graph_findings: [
        {
          id: 'gf-1',
          pattern_type: 'RAPID_PASS_THROUGH',
          severity: 'CRITICAL',
          heuristic_score: '0.8800',
          explanation: 'Account received ₹45,000 and dispersed ₹44,500 within 2 hours.',
          created_at: new Date().toISOString(),
        },
      ],
      investigation_notes: [],
      audit_events: [
        { id: '7', action: 'TRANSFER_POSTED', entity_type: 'TRANSFER', created_at: new Date().toISOString(), metadata: {} },
      ],
      disputes: [],
      timeline: [
        {
          timestamp: new Date().toISOString(),
          category: 'FACT',
          title: 'Transfer Posted',
          detail: 'Amount ₹45,000 posted in PostgreSQL ledger.',
          evidence_ref: 'transfer_request:tx-1',
        },
        {
          timestamp: new Date().toISOString(),
          category: 'STATISTICAL_MODEL',
          title: 'Random Forest Inference',
          detail: 'Risk score evaluated as 0.9200.',
          evidence_ref: 'model:rf-v1.0.0',
        },
      ],
    };

    vi.spyOn(fraudApi, 'getDossier').mockResolvedValue(mockDossier);

    render(
      <ForensicDossierDrawer
        isOpen={true}
        onClose={handleClose}
        alertId="alt-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Forensic Investigation Dossier/i)).toBeInTheDocument();
      expect(screen.getByText('0.9200')).toBeInTheDocument();
      expect(screen.getAllByText('ACC-SAV-111111').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('ACC-SAV-222222').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Rapid pass through/i)).toBeInTheDocument();
      expect(screen.getByText('Random Forest Inference')).toBeInTheDocument();
      expect(screen.getByText('TRANSFER_POSTED')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Commit Determination/i })).toBeInTheDocument();
    });
  });
});

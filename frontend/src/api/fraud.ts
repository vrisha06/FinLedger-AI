import { apiClient } from './client';
import { FraudAlert, FraudReviewStatus, FraudRiskDecision } from '../types/api';

export interface ListFraudAlertsParams {
  review_status?: FraudReviewStatus;
  decision?: FraudRiskDecision;
  min_risk_score?: number;
  limit?: number;
  offset?: number;
}

export interface ReviewFraudAlertPayload {
  review_status: 'CLEARED' | 'CONFIRMED_FRAUD' | 'ESCALATED';
  review_notes?: string;
}

export const fraudApi = {
  listAlerts: async (params?: ListFraudAlertsParams): Promise<FraudAlert[]> => {
    const res = await apiClient.get<FraudAlert[]>('/api/v1/fraud/alerts', { params });
    return res.data;
  },

  getAlert: async (id: string): Promise<FraudAlert> => {
    const res = await apiClient.get<FraudAlert>(`/api/v1/fraud/alerts/${id}`);
    return res.data;
  },

  reviewAlert: async (
    id: string,
    payload: ReviewFraudAlertPayload
  ): Promise<FraudAlert> => {
    const res = await apiClient.patch<FraudAlert>(
      `/api/v1/fraud/alerts/${id}/review`,
      payload
    );
    return res.data;
  },

  getDossier: async (id: string): Promise<import('../types/api').ForensicDossierResponse> => {
    const res = await apiClient.get<import('../types/api').ForensicDossierResponse>(
      `/api/v1/fraud/alerts/${id}/dossier`
    );
    return res.data;
  },

  addInvestigationNote: async (
    id: string,
    payload: import('../types/api').CreateNotePayload
  ): Promise<import('../types/api').InvestigationNoteResponse> => {
    const res = await apiClient.post<import('../types/api').InvestigationNoteResponse>(
      `/api/v1/fraud/alerts/${id}/notes`,
      payload
    );
    return res.data;
  },

  getHealth: async (): Promise<import('../types/api').AIHealthResponse> => {
    const res = await apiClient.get<import('../types/api').AIHealthResponse>('/api/v1/fraud/health');
    return res.data;
  },
};


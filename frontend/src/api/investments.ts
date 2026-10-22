import { apiClient } from './client';
import { Investment, PortfolioSummary } from '../types/api';

export interface PurchaseInvestmentPayload {
  product_id: string;
  source_account_id: string;
  amount: string | number;
}

export const investmentsApi = {
  purchaseInvestment: async (
    payload: PurchaseInvestmentPayload,
    idempotencyKey: string
  ): Promise<Investment> => {
    const res = await apiClient.post<Investment>(
      '/api/v1/investments',
      payload,
      {
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      }
    );
    return res.data;
  },

  listInvestments: async (statusFilter?: string): Promise<Investment[]> => {
    const params = statusFilter ? { status_filter: statusFilter } : {};
    const res = await apiClient.get<Investment[]>('/api/v1/investments', { params });
    return res.data;
  },

  getPortfolio: async (): Promise<PortfolioSummary> => {
    const res = await apiClient.get<PortfolioSummary>('/api/v1/investments/portfolio');
    return res.data;
  },

  getInvestment: async (id: string): Promise<Investment> => {
    const res = await apiClient.get<Investment>(`/api/v1/investments/${id}`);
    return res.data;
  },
};

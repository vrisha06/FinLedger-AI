import { apiClient } from './client';
import { PayeePreviewPayload, PayeePreviewResponse, TransferHistoryItem, TransferRequest } from '../types/api';

export interface CreateTransferPayload {
  source_account_id: string;
  destination_account_id: string;
  amount: string | number;
  currency?: string;
  memo?: string | null;
}

export const transfersApi = {
  createTransfer: async (
    payload: CreateTransferPayload,
    idempotencyKey: string
  ): Promise<TransferRequest> => {
    const res = await apiClient.post<TransferRequest>(
      '/api/v1/transfers',
      {
        ...payload,
        currency: 'INR', // Strictly INR
      },
      {
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      }
    );
    return res.data;
  },

  listTransfers: async (limit = 25, offset = 0): Promise<TransferHistoryItem[]> => {
    const res = await apiClient.get<TransferHistoryItem[]>('/api/v1/transfers', { params: { limit, offset } });
    return res.data;
  },

  // Admin-only: posts a balanced CORRECTION_REVERSAL; returns the new reversal transfer
  reverseTransfer: async (id: string, reason: string): Promise<TransferRequest> => {
    const res = await apiClient.post<TransferRequest>(`/api/v1/transfers/${id}/reverse`, { reason });
    return res.data;
  },

  getTransfer: async (id: string): Promise<TransferRequest> => {
    const res = await apiClient.get<TransferRequest>(`/api/v1/transfers/${id}`);
    return res.data;
  },

  previewTransfer: async (payload: PayeePreviewPayload): Promise<PayeePreviewResponse> => {
    const res = await apiClient.post<PayeePreviewResponse>(
      '/api/v1/transfers/preview',
      payload
    );
    return res.data;
  },
};


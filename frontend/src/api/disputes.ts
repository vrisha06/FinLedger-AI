import { apiClient } from './client';
import { DisputeResponse, CreateDisputePayload } from '../types/api';

export const disputesApi = {
  listDisputes: async (): Promise<DisputeResponse[]> => {
    const res = await apiClient.get<DisputeResponse[]>('/api/v1/disputes');
    return res.data;
  },

  getDispute: async (id: string): Promise<DisputeResponse> => {
    const res = await apiClient.get<DisputeResponse>(`/api/v1/disputes/${id}`);
    return res.data;
  },

  createDispute: async (payload: CreateDisputePayload): Promise<DisputeResponse> => {
    const res = await apiClient.post<DisputeResponse>('/api/v1/disputes', payload);
    return res.data;
  },

  updateStatus: async (
    id: string,
    payload: { status: string; notes: string }
  ): Promise<DisputeResponse> => {
    const res = await apiClient.post<DisputeResponse>(`/api/v1/disputes/${id}/status`, payload);
    return res.data;
  },

  addNote: async (
    id: string,
    payload: { notes: string }
  ): Promise<DisputeResponse> => {
    const res = await apiClient.post<DisputeResponse>(`/api/v1/disputes/${id}/note`, payload);
    return res.data;
  },
};

import { apiClient } from './client';
import { TokenResponse, User } from '../types/api';

export interface LoginPayload {
  username_or_email: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  full_name: string;
  phone?: string;
  pan_number?: string;
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/api/v1/auth/login', payload);
    return res.data;
  },

  register: async (payload: RegisterPayload): Promise<User> => {
    const res = await apiClient.post<User>('/api/v1/auth/register', payload);
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get<User>('/api/v1/auth/me');
    return res.data;
  },

  logout: async (): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>('/api/v1/auth/logout');
    return res.data;
  },
};

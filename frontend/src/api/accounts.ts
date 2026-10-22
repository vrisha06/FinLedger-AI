import { apiClient } from './client';
import { Account, LedgerEntry } from '../types/api';

export const accountsApi = {
  listAccounts: async (customerId?: string): Promise<Account[]> => {
    const params = customerId ? { customer_id: customerId } : {};
    const res = await apiClient.get<Account[]>('/api/v1/accounts', { params });
    return res.data;
  },

  getAccount: async (id: string): Promise<Account> => {
    const res = await apiClient.get<Account>(`/api/v1/accounts/${id}`);
    return res.data;
  },

  getAccountLedger: async (
    id: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<LedgerEntry[]> => {
    const res = await apiClient.get<LedgerEntry[]>(`/api/v1/accounts/${id}/ledger`, {
      params: { limit, offset },
    });
    return res.data;
  },

  depositOpeningFunds: async (
    id: string,
    amount: number | string,
    description: string = 'Simulated Opening Deposit'
  ): Promise<Account> => {
    const res = await apiClient.post<Account>(`/api/v1/accounts/${id}/deposit`, {
      amount,
      description,
    });
    return res.data;
  },

  createAccount: async (
    accountType: 'SAVINGS' | 'CURRENT' = 'SAVINGS'
  ): Promise<Account> => {
    const res = await apiClient.post<Account>('/api/v1/accounts', {
      account_type: accountType,
    });
    return res.data;
  },
};

import { apiClient } from './client';
import {
  BalanceDistributionReport,
  CustomerFinancialSummary,
  DailyVolumeReport,
  ProductsSummaryReport,
} from '../types/api';

export const reportsApi = {
  getCustomerSummary: async (customerId?: string): Promise<CustomerFinancialSummary> => {
    const params = customerId ? { customer_id: customerId } : {};
    const res = await apiClient.get<CustomerFinancialSummary>(
      '/api/v1/reports/customer-summary',
      { params }
    );
    return res.data;
  },

  getProductsSummary: async (): Promise<ProductsSummaryReport> => {
    const res = await apiClient.get<ProductsSummaryReport>('/api/v1/reports/products-summary');
    return res.data;
  },

  getDailyVolume: async (days: number = 14): Promise<DailyVolumeReport> => {
    const res = await apiClient.get<DailyVolumeReport>('/api/v1/reports/daily-volume', {
      params: { days },
    });
    return res.data;
  },

  getBalanceDistribution: async (): Promise<BalanceDistributionReport> => {
    const res = await apiClient.get<BalanceDistributionReport>(
      '/api/v1/reports/balance-distribution'
    );
    return res.data;
  },
};

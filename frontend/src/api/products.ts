import { apiClient } from './client';
import { FinancialProduct, ProductType } from '../types/api';

export interface ProductCreatePayload {
  name: string;
  code: string;
  product_type: ProductType;
  annual_yield_rate: string | number;
  min_amount: string | number;
  term_months: number;
  is_active?: boolean;
}

export const productsApi = {
  listProducts: async (
    productType?: ProductType,
    isActive: boolean = true
  ): Promise<FinancialProduct[]> => {
    const params: Record<string, unknown> = { is_active: isActive };
    if (productType) params.product_type = productType;
    const res = await apiClient.get<FinancialProduct[]>('/api/v1/products', { params });
    return res.data;
  },

  getProduct: async (id: string): Promise<FinancialProduct> => {
    const res = await apiClient.get<FinancialProduct>(`/api/v1/products/${id}`);
    return res.data;
  },

  createProduct: async (payload: ProductCreatePayload): Promise<FinancialProduct> => {
    const res = await apiClient.post<FinancialProduct>('/api/v1/products', payload);
    return res.data;
  },
};

import { apiClient } from './client';
import { AuditLog, ReconciliationReport } from '../types/api';

export interface ListAuditLogsParams {
  action?: string;
  entity_type?: string;
  entity_id?: string;
  limit?: number;
  offset?: number;
}

export const auditApi = {
  listLogs: async (params?: ListAuditLogsParams): Promise<AuditLog[]> => {
    const res = await apiClient.get<AuditLog[]>('/api/v1/audit/logs', { params });
    return res.data;
  },

  getReconciliation: async (): Promise<ReconciliationReport> => {
    const res = await apiClient.get<ReconciliationReport>('/api/v1/audit/reconciliation');
    return res.data;
  },
};

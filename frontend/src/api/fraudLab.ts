import { apiClient } from './client';
import { FraudLabScenario, FraudLabRunResult, FraudLabHistoryItem } from '../types/api';

export interface RunSimulationPayload {
  scenario_name: string;
  seed?: number;
  sample_size?: number;
}

export const fraudLabApi = {
  listScenarios: async (): Promise<FraudLabScenario[]> => {
    const res = await apiClient.get<FraudLabScenario[]>('/api/v1/fraud-lab/scenarios');
    return res.data;
  },

  runSimulation: async (payload: RunSimulationPayload): Promise<FraudLabRunResult> => {
    const res = await apiClient.post<FraudLabRunResult>('/api/v1/fraud-lab/run', payload);
    return res.data;
  },

  getHistory: async (): Promise<FraudLabHistoryItem[]> => {
    const res = await apiClient.get<FraudLabHistoryItem[]>('/api/v1/fraud-lab/history');
    return res.data;
  },
};

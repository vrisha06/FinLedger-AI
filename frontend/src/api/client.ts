import axios, { AxiosError } from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Request interceptor to attach bearer token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('finledger_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to format errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg: string }> }>) => {
    if (error.response?.status === 401) {
      // If token expired, clear from storage
      const hadToken = !!localStorage.getItem('finledger_token');
      if (hadToken && !window.location.pathname.includes('/login')) {
        localStorage.removeItem('finledger_token');
        localStorage.removeItem('finledger_user');
        window.dispatchEvent(new Event('auth_expired'));
      }
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data?.detail) {
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (Array.isArray(data.detail)) {
        return data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
      }
    }
    if (error.response?.status === 403) {
      return 'Access Denied: You do not have permission for this action.';
    }
    if (error.response?.status === 404) {
      return 'Requested resource not found.';
    }
    if (error.response?.status === 409) {
      return data?.detail || 'Conflict: Idempotency conflict or duplicate resource.';
    }
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      return 'Request timed out. Please check your network connection.';
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred. Please try again.';
}

/**
 * True when the server definitively rejected the request (4xx). The attempt is then
 * recorded server-side, so a corrected retry needs a fresh Idempotency-Key. Network
 * errors and 5xx are ambiguous: keep the key so a retry can never charge twice.
 */
export function isDefinitiveRejection(error: unknown): boolean {
  if (!axios.isAxiosError(error) || !error.response) return false;
  return error.response.status >= 400 && error.response.status < 500;
}

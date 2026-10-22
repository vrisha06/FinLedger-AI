import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole } from '../types/api';
import { authApi, LoginPayload, RegisterPayload } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isCustomer: boolean;
  isStaff: boolean;
  isAdmin: boolean;
  login: (credentials: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('finledger_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('finledger_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshMe = useCallback(async () => {
    if (!localStorage.getItem('finledger_token')) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }
    try {
      const freshUser = await authApi.getMe();
      setUser(freshUser);
      localStorage.setItem('finledger_user', JSON.stringify(freshUser));
    } catch {
      // If verification fails, clear
      localStorage.removeItem('finledger_token');
      localStorage.removeItem('finledger_user');
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMe();

    const handleExpired = () => {
      setUser(null);
      setToken(null);
    };

    window.addEventListener('auth_expired', handleExpired);
    return () => window.removeEventListener('auth_expired', handleExpired);
  }, [refreshMe]);

  const login = async (credentials: LoginPayload) => {
    setIsLoading(true);
    try {
      const data = await authApi.login(credentials);
      localStorage.setItem('finledger_token', data.access_token);
      localStorage.setItem('finledger_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload): Promise<User> => {
    return await authApi.register(payload);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('finledger_token');
      localStorage.removeItem('finledger_user');
      setUser(null);
      setToken(null);
    }
  };

  const role: UserRole | undefined = user?.role;
  const isCustomer = role === 'CUSTOMER';
  const isStaff = role === 'STAFF' || role === 'ADMIN';
  const isAdmin = role === 'ADMIN';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        isCustomer,
        isStaff,
        isAdmin,
        login,
        register,
        logout,
        refreshMe,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

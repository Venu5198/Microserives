import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export interface User {
  id: string;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (data: any) => Promise<void>;
  register: (data: any) => Promise<void>;
  logout: () => Promise<void>;
  loading: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  const fetchProfile = async () => {
    try {
      const res = await apiClient.get('/api/v1/users/me');
      setUser(res.data);
    } catch {
      setUser(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setToken(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchProfile();
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = async (credentials: any) => {
    const res = await apiClient.post('/api/v1/auth/login', credentials);
    const { access_token, refresh_token, user_id, email, role } = res.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    setToken(access_token);
    setUser({ id: user_id, email, role });
  };

  const register = async (userData: any) => {
    const res = await apiClient.post('/api/v1/auth/register', userData);
    const { access_token, refresh_token, user_id, email, role } = res.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    setToken(access_token);
    setUser({ id: user_id, email, role });
  };

  const logout = async () => {
    const rt = localStorage.getItem('refresh_token');
    try {
      if (rt) {
        await apiClient.post('/api/v1/auth/logout', { refresh_token: rt });
      }
    } catch (e) {
      // Ignore
    } finally {
      localStorage.clear();
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        register,
        logout,
        loading,
        isAdmin: user?.role === 'ADMIN' || user?.role === 'OPERATIONS',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};


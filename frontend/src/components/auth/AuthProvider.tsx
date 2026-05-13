'use client';
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, AuthState } from '@/types';
import { api } from '@/lib/api';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; name: string; organization?: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null, token: null, isAuthenticated: false, loading: true,
  });

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem('kubemind_token');
    const userStr = localStorage.getItem('kubemind_user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        setState({ user, token, isAuthenticated: true, loading: false });
      } catch {
        setState(s => ({ ...s, loading: false }));
      }
    } else {
      setState(s => ({ ...s, loading: false }));
    }

    // Listen for unauthorized events
    const handler = () => { logout(); };
    window.addEventListener('kubemind:unauthorized', handler);
    return () => window.removeEventListener('kubemind:unauthorized', handler);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    localStorage.setItem('kubemind_token', res.token);
    localStorage.setItem('kubemind_user', JSON.stringify(res.user));
    setState({ user: res.user, token: res.token, isAuthenticated: true, loading: false });
  }, []);

  const register = useCallback(async (data: { email: string; password: string; name: string; organization?: string }) => {
    const res = await api.register(data);
    localStorage.setItem('kubemind_token', res.token);
    localStorage.setItem('kubemind_user', JSON.stringify(res.user));
    setState({ user: res.user, token: res.token, isAuthenticated: true, loading: false });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('kubemind_token');
    localStorage.removeItem('kubemind_user');
    setState({ user: null, token: null, isAuthenticated: false, loading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    // Return a safe fallback for SSR/prerendering
    return {
      user: null,
      token: null,
      isAuthenticated: false,
      loading: true,
      login: async () => {},
      register: async () => {},
      logout: () => {},
    };
  }
  return ctx;
}

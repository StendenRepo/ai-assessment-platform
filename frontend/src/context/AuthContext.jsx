'use client';

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import { getStoredUser, getToken, clearSession, saveSession } from '@/lib/auth';
import { API_PATHS } from '@/lib/routes';

const AuthContext = createContext(null);
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let canceled = false;

    const bootstrap = async () => {
      const token = getToken();
      const stored = getStoredUser();

      if (!token) {
        if (!canceled) {
          setUser(null);
          setReady(true);
        }
        return;
      }

      // Keep previous UX by showing stored user while token validation runs.
      if (!canceled && stored) setUser(stored);

      try {
        const res = await fetch(`${API_URL}/api/v1${API_PATHS.authMe}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) throw new Error('Session expired');

        const freshUser = await res.json();
        if (!canceled) {
          saveSession(token, freshUser);
          setUser(freshUser);
        }
      } catch {
        if (!canceled) {
          clearSession();
          setUser(null);
        }
      } finally {
        if (!canceled) setReady(true);
      }
    };

    bootstrap();

    return () => {
      canceled = true;
    };
  }, []);

  const login = useCallback((userData) => {
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, ready, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

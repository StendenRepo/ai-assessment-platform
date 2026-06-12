'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  listNotifications,
  markNotificationRead,
} from '@/lib/api/notifications';

const NotificationContext = createContext(null);

export function NotificationProvider({ children, pollIntervalMs = 60000 }) {
  const [items, setItems] = useState([]);

  const refresh = useCallback(async () => {
    try {
      const next = await listNotifications(false);
      setItems(Array.isArray(next) ? next : []);
    } catch {
      // Not authenticated or temporarily offline.
    }
  }, []);

  const markAsRead = useCallback(async (notificationId) => {
    try {
      await markNotificationRead(notificationId);
      setItems((prev) =>
        prev.map((n) =>
          n.id === notificationId
            ? { ...n, read_at: n.read_at || new Date().toISOString() }
            : n
        )
      );
    } catch {
      // Ignore temporary failures; polling will reconcile state.
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollIntervalMs);
    return () => clearInterval(id);
  }, [pollIntervalMs, refresh]);

  const unreadCount = useMemo(
    () => items.filter((n) => !n.read_at).length,
    [items]
  );

  const value = useMemo(
    () => ({ items, unreadCount, refresh, markAsRead }),
    [items, unreadCount, refresh, markAsRead]
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      'useNotifications must be used within NotificationProvider'
    );
  }
  return context;
}

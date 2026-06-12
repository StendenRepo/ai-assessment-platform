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
const AI_NOTIFICATIONS_KEY = 'settings.notifications.aiProcessingComplete';

export function NotificationProvider({ children, pollIntervalMs = 60000 }) {
  const [items, setItems] = useState([]);
  const [aiProcessingEnabled, setAiProcessingEnabled] = useState(true);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(AI_NOTIFICATIONS_KEY);
      if (stored != null) {
        setAiProcessingEnabled(stored === 'true');
      }
    } catch {
      // Ignore storage access issues.
    }
  }, []);

  const setAiProcessingNotificationsEnabled = useCallback((enabled) => {
    const next = Boolean(enabled);
    setAiProcessingEnabled(next);
    try {
      localStorage.setItem(AI_NOTIFICATIONS_KEY, String(next));
    } catch {
      // Ignore storage access issues.
    }
  }, []);

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

  const visibleItems = useMemo(
    () =>
      items.filter((n) => {
        if (
          (n?.type === 'ai_processing_complete' ||
            n?.type === 'ai_processing_failed') &&
          !aiProcessingEnabled
        ) {
          return false;
        }
        return true;
      }),
    [items, aiProcessingEnabled]
  );

  const unreadCount = useMemo(
    () => visibleItems.filter((n) => !n.read_at).length,
    [visibleItems]
  );

  const value = useMemo(
    () => ({
      items: visibleItems,
      unreadCount,
      refresh,
      markAsRead,
      aiProcessingEnabled,
      setAiProcessingNotificationsEnabled,
    }),
    [
      visibleItems,
      unreadCount,
      refresh,
      markAsRead,
      aiProcessingEnabled,
      setAiProcessingNotificationsEnabled,
    ]
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

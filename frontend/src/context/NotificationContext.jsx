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
import {
  getNotificationPreferences,
  updateNotificationPreference,
} from '@/lib/api/notificationPreferences';

const NotificationContext = createContext(null);

export function NotificationProvider({ children, pollIntervalMs = 60000 }) {
  const [items, setItems] = useState([]);
  // Per-event-type preferences, persisted server-side (G2-220).
  // Shape: { [notification_type]: boolean }. Missing key defaults to enabled.
  const [preferences, setPreferences] = useState({});

  const refresh = useCallback(async () => {
    try {
      const next = await listNotifications(false);
      setItems(Array.isArray(next) ? next : []);
    } catch {
      // Not authenticated or temporarily offline.
    }
  }, []);

  const refreshPreferences = useCallback(async () => {
    try {
      const rows = await getNotificationPreferences();
      if (Array.isArray(rows)) {
        setPreferences(
          rows.reduce((acc, row) => {
            acc[row.notification_type] = row.enabled;
            return acc;
          }, {})
        );
      }
    } catch {
      // Not authenticated or temporarily offline.
    }
  }, []);

  const setPreference = useCallback(
    async (notificationType, enabled) => {
      const next = Boolean(enabled);
      // Optimistic: reflect the toggle immediately, reconcile on response.
      setPreferences((prev) => ({ ...prev, [notificationType]: next }));
      try {
        await updateNotificationPreference(notificationType, next);
        // Server already filters reads by preference; pull the fresh list so a
        // re-enabled type's existing notifications reappear.
        refresh();
      } catch {
        // Revert on failure.
        setPreferences((prev) => ({ ...prev, [notificationType]: !next }));
      }
    },
    [refresh]
  );

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
    refreshPreferences();
    const id = setInterval(refresh, pollIntervalMs);
    return () => clearInterval(id);
  }, [pollIntervalMs, refresh, refreshPreferences]);

  // Cosmetic client-side filter for instant toggle feedback; the server is the
  // authoritative gate (disabled types are never returned by the API).
  const visibleItems = useMemo(
    () => items.filter((n) => preferences[n?.type] !== false),
    [items, preferences]
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
      preferences,
      setPreference,
    }),
    [visibleItems, unreadCount, refresh, markAsRead, preferences, setPreference]
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

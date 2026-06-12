'use client';

import { useMemo, useRef, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Bell } from 'lucide-react';
import { useNotifications } from '@/context/NotificationContext';

function buildMeta(notification) {
  const type = String(notification?.type || '');

  if (type === 'deletion_reminder') {
    return {
      label: 'Recording retention',
      detail: notification?.due_date
        ? `Deletion: ${new Date(notification.due_date).toLocaleDateString()}`
        : null,
    };
  }

  if (type === 'ai_processing_complete') {
    return {
      label: 'AI processing',
      detail: 'Results are ready to review',
    };
  }

  if (type === 'ai_processing_failed') {
    return {
      label: 'AI processing',
      detail: 'Processing failed - review needed',
    };
  }

  return {
    label: 'System',
    detail: notification?.due_date
      ? `Due: ${new Date(notification.due_date).toLocaleDateString()}`
      : null,
  };
}

export default function NotificationBell() {
  const router = useRouter();
  const { items, unreadCount, markAsRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  async function handleNotificationClick(notification) {
    await markAsRead(notification.id);
    if (notification?.target_path) {
      router.push(notification.target_path);
      setOpen(false);
    }
  }

  useEffect(() => {
    function onClick(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const sortedItems = useMemo(
    () =>
      [...items].sort((a, b) => {
        const aTs = a?.created_at ? new Date(a.created_at).getTime() : 0;
        const bTs = b?.created_at ? new Date(b.created_at).getTime() : 0;
        return bTs - aTs;
      }),
    [items]
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center w-9 h-9 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        aria-label="Notifications"
      >
        <Bell size={15} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-lg bg-card border border-border shadow-2xl z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-border text-sm font-semibold text-foreground">
            Notifications
          </div>
          <div className="max-h-80 overflow-y-auto">
            {sortedItems.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                No notifications
              </div>
            ) : (
              sortedItems.map((notification) => {
                const meta = buildMeta(notification);
                const isRead = Boolean(notification.read_at);

                return (
                  <button
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={`w-full text-left px-4 py-3 border-b border-border last:border-0 hover:bg-secondary/50 transition-colors ${
                      isRead ? 'opacity-60' : ''
                    }`}
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {meta.label}
                    </p>
                    <p className="text-xs text-foreground leading-relaxed mt-1">
                      {notification.message}
                    </p>
                    {meta.detail && (
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {meta.detail}
                      </p>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

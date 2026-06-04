'use client';

import { useEffect, useRef, useState } from 'react';
import { Bell } from 'lucide-react';
import { listNotifications, markNotificationRead } from '@/lib/recording';

/**
 * Header bell showing recording deletion reminders (G2-142).
 * Polls periodically; lets the teacher mark reminders as read.
 */
export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  async function refresh() {
    try {
      setItems(await listNotifications(false));
    } catch {
      /* not logged in / offline — ignore */
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
    const id = setInterval(refresh, 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const unread = items.filter((n) => !n.read_at).length;

  async function handleRead(id) {
    try {
      await markNotificationRead(id);
      setItems((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, read_at: new Date().toISOString() } : n
        )
      );
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex items-center justify-center w-9 h-9 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        aria-label="Notifications"
      >
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-lg bg-card border border-border shadow-2xl z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-border text-sm font-semibold text-foreground">
            Notifications
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                No notifications
              </div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleRead(n.id)}
                  className={`w-full text-left px-4 py-3 border-b border-border last:border-0 hover:bg-secondary/50 transition-colors ${
                    n.read_at ? 'opacity-60' : ''
                  }`}
                >
                  <p className="text-xs text-foreground leading-relaxed">
                    {n.message}
                  </p>
                  {n.due_date && (
                    <p className="text-[10px] text-muted-foreground mt-1">
                      Deletion: {new Date(n.due_date).toLocaleDateString()}
                    </p>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

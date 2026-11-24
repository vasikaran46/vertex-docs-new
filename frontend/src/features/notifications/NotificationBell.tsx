import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, Check, Trash2 } from 'lucide-react';
import { apiJson, timeAgo } from '../../lib/api';

export type AppNotification = {
  id: number; kind: string; title: string; message: string | null; document_id: number | null; read: boolean; created_at: string;
};

type Props = {
  token: string | null;
  refreshKey?: number;
  onOpen: (notification: AppNotification) => void;
};

export function NotificationBell({ token, refreshKey = 0, onOpen }: Props) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const root = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!token) { setItems([]); setUnread(0); return; }
    try {
      const result = await apiJson<{ items: AppNotification[]; unread_count: number }>('/api/notifications?limit=30', token);
      setItems(result.items);
      setUnread(result.unread_count);
      setError('');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not load notifications.');
    }
  }, [token]);

  useEffect(() => { void load(); }, [load, refreshKey]);
  useEffect(() => {
    if (!token) return;
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [token, load]);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', escape); };
  }, [open]);

  async function act(path: string, method: string) {
    try { await apiJson(path, token, { method }); await load(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Action failed.'); }
  }

  return (
    <div className="vx-bell" ref={root}>
      <button className="icon-button" aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'} aria-expanded={open} onClick={() => { setOpen((value) => !value); void load(); }}>
        <Bell size={18} />
        {unread > 0 && <span className="vx-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div className="vx-popover" role="dialog" aria-label="Notifications">
          <header>
            <b>Notifications</b>
            <span>
              <button type="button" disabled={!unread} onClick={() => void act('/api/notifications/read-all', 'POST')}><Check size={13} /> Mark all read</button>
              <button type="button" disabled={!items.length} onClick={() => void act('/api/notifications', 'DELETE')}><Trash2 size={13} /> Clear</button>
            </span>
          </header>
          {!token ? <p className="vx-empty">Sign in to see notifications.</p>
            : error ? <p className="vx-empty" role="alert">{error}</p>
              : !items.length ? <p className="vx-empty">No notifications yet. Conversions, translations and shares will appear here.</p>
                : <ul>
                  {items.map((item) => (
                    <li key={item.id} className={item.read ? '' : 'unread'}>
                      <button type="button" className="vx-note-main" onClick={async () => { if (!item.read) await act(`/api/notifications/${item.id}/read`, 'POST'); setOpen(false); onOpen(item); }}>
                        <b>{item.title}</b>
                        {item.message && <span>{item.message}</span>}
                        <small>{timeAgo(item.created_at)}</small>
                      </button>
                      <button type="button" className="vx-note-delete" aria-label={`Dismiss ${item.title}`} onClick={() => void act(`/api/notifications/${item.id}`, 'DELETE')}><Trash2 size={13} /></button>
                    </li>
                  ))}
                </ul>}
        </div>
      )}
    </div>
  );
}

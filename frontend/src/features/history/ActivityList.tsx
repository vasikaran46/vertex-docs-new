import { useCallback, useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { apiJson, formatWhen } from '../../lib/api';

type EventItem = { id: number; document_id: number | null; file_name: string | null; file_type: string | null; action: string; category: string; detail: string | null; created_at: string };

const FILTERS: [string, string][] = [['', 'All activity'], ['upload', 'Uploads'], ['conversion', 'Conversions'], ['edit', 'Editing'], ['translation', 'Translation'], ['share', 'Sharing'], ['signature', 'Signatures']];

export function ActivityList({ token, refreshKey }: { token: string; refreshKey: number }) {
  const [items, setItems] = useState<EventItem[]>([]);
  const [category, setCategory] = useState('');
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(15);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const query = `/api/history/events?limit=${limit}${category ? `&category=${category}` : ''}`;
      const result = await apiJson<{ items: EventItem[]; total: number }>(query, token);
      setItems(result.items); setTotal(result.total); setError('');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not load activity.'); }
  }, [token, category, limit]);
  useEffect(() => { void load(); }, [load, refreshKey]);

  async function remove(id: number) {
    try { await apiJson(`/api/history/events/${id}`, token, { method: 'DELETE' }); await load(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not delete the entry.'); }
  }

  return (
    <section className="panel history-panel vx-activity">
      <div className="history-panel-heading"><div><h2>Activity</h2><p>{total ? `${total} recorded ${total === 1 ? 'action' : 'actions'}` : 'Operations on your documents are recorded here.'}</p></div></div>
      <div className="history-filters" role="group" aria-label="Filter activity">
        {FILTERS.map(([id, label]) => <button key={id || 'all'} className={category === id ? 'active' : ''} aria-pressed={category === id} onClick={() => { setCategory(id); setLimit(15); }}>{label}</button>)}
      </div>
      {error && <p className="ai-error" role="alert">{error}</p>}
      {!items.length ? <div className="history-empty"><b>No activity yet</b><span>Uploads, conversions, edits and shares will be listed here.</span></div> : (
        <ul className="vx-activity-list">
          {items.map((item) => (
            <li key={item.id}>
              <span className="vx-type">{(item.file_type ?? '—').toUpperCase()}</span>
              <div><b>{item.action}</b><small>{item.file_name ?? 'Workspace'}{item.detail ? ` · ${item.detail}` : ''}</small></div>
              <time>{formatWhen(item.created_at)}</time>
              <button aria-label="Remove from activity" onClick={() => void remove(item.id)}><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      )}
      {items.length < total && <button className="vx-more" onClick={() => setLimit((value) => value + 15)}>Show more</button>}
    </section>
  );
}

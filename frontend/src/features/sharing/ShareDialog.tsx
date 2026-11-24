import { useEffect, useState } from 'react';
import { Copy, Link2, Trash2, X } from 'lucide-react';
import { API, apiJson, formatWhen, networkMessage } from '../../lib/api';

type Share = {
  id: number; recipient_email: string | null; created_at: string; expires_at: string | null; revoked: boolean;
  download_count: number; emailed: boolean; download_url: string; email_status?: string;
};

type Props = { token: string; documentId: number; documentName: string; onClose: () => void; onChanged?: () => void };

export function ShareDialog({ token, documentId, documentName, onClose, onChanged }: Props) {
  const [email, setEmail] = useState('');
  const [hours, setHours] = useState('168');
  const [shares, setShares] = useState<Share[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    try {
      const result = await apiJson<{ items: Share[] }>(`/api/documents/${documentId}/shares`, token);
      setShares(result.items.filter((item) => !item.revoked));
    } catch (failure) { setError(networkMessage(failure, 'Could not load share links.')); }
  }
  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [documentId]);

  async function create() {
    setBusy(true); setError(''); setMessage('');
    try {
      const created = await apiJson<Share>(`/api/documents/${documentId}/share`, token, {
        method: 'POST',
        body: JSON.stringify({ recipient_email: email.trim() || null, expires_hours: Number(hours) }),
      });
      const emailNote = created.email_status === 'sent' ? ` and e-mailed to ${created.recipient_email}`
        : created.email_status === 'not_configured' ? '. E-mail delivery is not configured on this server, so copy the link and send it yourself'
          : created.email_status === 'failed' ? '. The e-mail could not be sent, so copy the link and send it yourself' : '';
      setMessage(`Share link created${emailNote}.`);
      setEmail('');
      await load();
      onChanged?.();
    } catch (failure) { setError(networkMessage(failure, 'Could not create the share link.')); }
    finally { setBusy(false); }
  }

  async function copy(url: string) {
    try { await navigator.clipboard.writeText(url); setMessage('Link copied to clipboard.'); setError(''); }
    catch { setError('Could not copy automatically. Select the link and copy it manually.'); }
  }

  async function revoke(id: number) {
    try { await apiJson(`/api/shares/${id}`, token, { method: 'DELETE' }); setMessage('Share link revoked.'); await load(); onChanged?.(); }
    catch (failure) { setError(networkMessage(failure, 'Could not revoke the link.')); }
  }

  return (
    <div className="vx-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="vx-modal" role="dialog" aria-modal="true" aria-label={`Share ${documentName}`}>
        <header><h3>Share “{documentName}”</h3><button className="vx-close" aria-label="Close" onClick={onClose}><X size={16} /></button></header>
        <p className="vx-hint">Anyone with the link can download this file until it expires or you revoke it.</p>
        <label className="vx-field">Recipient e-mail (optional)
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" />
        </label>
        <label className="vx-field">Link expires after
          <select value={hours} onChange={(event) => setHours(event.target.value)}>
            <option value="24">1 day</option><option value="168">7 days</option><option value="720">30 days</option><option value="2160">90 days</option>
          </select>
        </label>
        <button className="primary" disabled={busy} onClick={() => void create()}><Link2 size={15} /> {busy ? 'Creating…' : 'Create share link'}</button>
        {message && <p className="operation-notice" role="status">{message}</p>}
        {error && <p className="ai-error" role="alert">{error}</p>}
        {shares.length > 0 && <>
          <h4>Active links</h4>
          <ul className="vx-share-list">
            {shares.map((share) => (
              <li key={share.id}>
                <input readOnly value={share.download_url || `${API}/api/shared/…`} onFocus={(event) => event.currentTarget.select()} aria-label="Share link" />
                <small>{share.recipient_email ? `For ${share.recipient_email} · ` : ''}Expires {formatWhen(share.expires_at)} · {share.download_count} download{share.download_count === 1 ? '' : 's'}</small>
                <span>
                  <button onClick={() => void copy(share.download_url)}><Copy size={14} /> Copy</button>
                  <button className="history-delete" onClick={() => void revoke(share.id)}><Trash2 size={14} /> Revoke</button>
                </span>
              </li>
            ))}
          </ul>
        </>}
      </section>
    </div>
  );
}

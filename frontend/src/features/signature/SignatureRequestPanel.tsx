import { useCallback, useEffect, useState } from 'react';
import { Copy, PenLine, Send, XCircle } from 'lucide-react';
import { apiJson, formatWhen, networkMessage } from '../../lib/api';

type DocItem = { id: number; name: string };
type SigRequest = {
  id: number; document_id: number; document_name: string | null; signer_name: string; signer_email: string; status: string;
  created_at: string; completed_at: string | null; signed_document_id: number | null; sign_url: string; emailed: boolean; email_status?: string;
};

type Props = { token: string | null; documents: DocItem[]; onChanged?: () => void; onOpenDocument?: (id: number) => void };

const STATUS_LABEL: Record<string, string> = { pending: 'Waiting for signature', signed: 'Signed', declined: 'Declined', cancelled: 'Cancelled', expired: 'Expired' };

export function SignatureRequestPanel({ token, documents, onChanged, onOpenDocument }: Props) {
  const pdfs = documents.filter((item) => item.name.toLowerCase().endsWith('.pdf'));
  const [documentId, setDocumentId] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [requests, setRequests] = useState<SigRequest[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    try { setRequests((await apiJson<{ items: SigRequest[] }>('/api/signatures', token)).items); }
    catch (failure) { setError(networkMessage(failure, 'Could not load signature requests.')); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!documentId && pdfs.length) setDocumentId(String(pdfs[0].id)); }, [pdfs, documentId]);

  async function submit() {
    setError(''); setMessage('');
    if (!documentId) { setError('Choose a PDF document first.'); return; }
    if (!name.trim() || !email.trim()) { setError('Enter the signer’s name and e-mail address.'); return; }
    setBusy(true);
    try {
      const created = await apiJson<SigRequest>('/api/signatures', token, {
        method: 'POST',
        body: JSON.stringify({ document_id: Number(documentId), signer_name: name.trim(), signer_email: email.trim(), message: note.trim() || null }),
      });
      setMessage(created.email_status === 'sent'
        ? `Request created and e-mailed to ${created.signer_email}.`
        : 'Request created. E-mail delivery is not configured on this server, so copy the signing link below and send it to the signer yourself.');
      setName(''); setEmail(''); setNote('');
      await load();
      onChanged?.();
    } catch (failure) { setError(networkMessage(failure, 'The request could not be created.')); }
    finally { setBusy(false); }
  }

  async function cancel(id: number) {
    try { await apiJson(`/api/signatures/${id}/cancel`, token, { method: 'POST' }); await load(); onChanged?.(); }
    catch (failure) { setError(networkMessage(failure, 'Could not cancel the request.')); }
  }

  async function copy(url: string) {
    try { await navigator.clipboard.writeText(url); setMessage('Signing link copied.'); setError(''); }
    catch { setError('Could not copy automatically. Select the link and copy it manually.'); }
  }

  return (
    <section className="panel advanced-tool-panel vx-sign-panel">
      <div className="conversion-heading"><div><h2>Request Signature</h2><p>Send a PDF to someone for a typed signature. The signed copy is saved to your Document History.</p></div></div>
      {!token ? <p className="inline-hint">Sign in to request signatures.</p> : !pdfs.length ? <p className="inline-hint">Upload a PDF to your workspace first, then come back to request a signature.</p> : (
        <div className="vx-form-grid">
          <label className="vx-field">Document
            <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>{pdfs.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          </label>
          <label className="vx-field">Signer’s name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} /></label>
          <label className="vx-field">Signer’s e-mail<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="vx-field vx-wide">Message (optional)<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={2} /></label>
          <button className="primary vx-wide" disabled={busy} onClick={() => void submit()}><Send size={15} /> {busy ? 'Creating request…' : 'Request signature'}</button>
        </div>
      )}
      {message && <p className="operation-notice" role="status">{message}</p>}
      {error && <p className="ai-error" role="alert">{error}</p>}
      <h4 className="vx-sub">Your signature requests</h4>
      {!requests.length ? <p className="inline-hint">No requests yet.</p> : (
        <ul className="vx-request-list">
          {requests.map((request) => (
            <li key={request.id}>
              <div><b>{request.document_name ?? 'Deleted document'}</b><small>To {request.signer_name} ({request.signer_email}) · {formatWhen(request.created_at)}</small></div>
              <span className={`vx-status vx-${request.status}`}>{STATUS_LABEL[request.status] ?? request.status}</span>
              <span className="vx-row-actions">
                {request.status === 'pending' && <>
                  <button onClick={() => void copy(request.sign_url)}><Copy size={14} /> Copy link</button>
                  <button className="history-delete" onClick={() => void cancel(request.id)}><XCircle size={14} /> Cancel</button>
                </>}
                {request.status === 'signed' && request.signed_document_id && onOpenDocument && <button onClick={() => onOpenDocument(request.signed_document_id!)}><PenLine size={14} /> Open signed copy</button>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

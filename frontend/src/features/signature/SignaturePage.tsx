import { useEffect, useState } from 'react';
import { API, readError } from '../../lib/api';

type Details = { document_name: string | null; signer_name: string; requested_by: string | null; message: string | null; status: string };

/** Standalone page opened from a signature link (?sign=TOKEN). No account is required. */
export function SignaturePage({ token }: { token: string }) {
  const [details, setDetails] = useState<Details | null>(null);
  const [signature, setSignature] = useState('');
  const [agree, setAgree] = useState(false);
  const [state, setState] = useState<'loading' | 'ready' | 'done' | 'declined' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [pdfUrl, setPdfUrl] = useState('');

  useEffect(() => {
    let revoked = '';
    (async () => {
      try {
        const response = await fetch(`${API}/api/signatures/public/${encodeURIComponent(token)}`);
        if (!response.ok) throw new Error(await readError(response));
        const result = (await response.json()) as Details;
        setDetails(result);
        setSignature(result.signer_name);
        if (result.status !== 'pending') { setState('error'); setMessage(`This request is ${result.status}.`); return; }
        const file = await fetch(`${API}/api/signatures/public/${encodeURIComponent(token)}/document`);
        if (file.ok) { revoked = URL.createObjectURL(await file.blob()); setPdfUrl(revoked); }
        setState('ready');
      } catch (failure) {
        setState('error');
        setMessage(failure instanceof TypeError ? 'Could not reach the server.' : failure instanceof Error ? failure.message : 'This signature link is not valid.');
      }
    })();
    return () => { if (revoked) URL.revokeObjectURL(revoked); };
  }, [token]);

  async function post(path: string, body?: unknown) {
    const response = await fetch(`${API}/api/signatures/public/${encodeURIComponent(token)}/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw new Error(await readError(response));
    return response.json() as Promise<{ message?: string }>;
  }

  async function sign() {
    setMessage('');
    try { const result = await post('sign', { signature_text: signature.trim(), agree }); setMessage(result.message ?? 'Signed.'); setState('done'); }
    catch (failure) { setMessage(failure instanceof Error ? failure.message : 'Signing failed.'); }
  }
  async function decline() {
    try { await post('decline'); setState('declined'); setMessage('You declined to sign this document.'); }
    catch (failure) { setMessage(failure instanceof Error ? failure.message : 'Could not decline.'); }
  }

  return (
    <main className="vx-sign-page">
      <section className="panel vx-sign-card">
        <h1>Sign document</h1>
        {state === 'loading' && <p>Loading…</p>}
        {state === 'error' && <p className="ai-error" role="alert">{message}</p>}
        {(state === 'done' || state === 'declined') && <p className="operation-notice" role="status">{message}</p>}
        {state === 'ready' && details && <>
          <p><b>{details.requested_by ?? 'Someone'}</b> asked <b>{details.signer_name}</b> to sign <b>{details.document_name}</b>.</p>
          {details.message && <blockquote>{details.message}</blockquote>}
          {pdfUrl && <iframe title="Document to sign" src={pdfUrl} className="vx-sign-frame" />}
          <label className="vx-field">Type your full name as your signature
            <input value={signature} onChange={(event) => setSignature(event.target.value)} maxLength={160} />
          </label>
          <label className="vx-check"><input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} /> I have reviewed this document and agree to sign it electronically.</label>
          <div className="vx-sign-actions">
            <button className="primary" disabled={!agree || signature.trim().length < 2} onClick={() => void sign()}>Sign document</button>
            <button onClick={() => void decline()}>Decline</button>
          </div>
          {message && <p className="ai-error" role="alert">{message}</p>}
        </>}
      </section>
    </main>
  );
}

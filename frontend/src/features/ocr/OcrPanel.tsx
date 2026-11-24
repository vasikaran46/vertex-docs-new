import { useEffect, useState } from 'react';
import { Check, Copy, ScanText, UploadCloud } from 'lucide-react';
import { API, apiJson, networkMessage, readError } from '../../lib/api';
import { ExportMenu } from '../export/ExportMenu';

type Page = { page: number; method: 'ocr' | 'text-layer'; characters: number; text: string; warning: string | null };
type Result = { text: string; page_count: number; processed_pages: number; ocr_pages: number; unreadable_pages: number[]; truncated: boolean; languages: string[]; pages: Page[] };
type Status = { available: boolean; languages: string[]; supported_language_codes: Record<string, string>; reason: string | null };

const NAMES: Record<string, string> = { en: 'English', ta: 'Tamil', hi: 'Hindi', ml: 'Malayalam', te: 'Telugu', kn: 'Kannada', bn: 'Bengali', sa: 'Sanskrit', fr: 'French', de: 'German', es: 'Spanish', ja: 'Japanese' };

type Props = { token: string | null; onUseText?: (text: string) => void };

export function OcrPanel({ token, onUseText }: Props) {
  const [status, setStatus] = useState<Status | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiJson<Status>('/api/pdf/ocr/status', token).then(setStatus).catch(() => setStatus(null));
  }, [token]);

  async function run() {
    if (!file || !token) return;
    setBusy(true); setError(''); setResult(null);
    try {
      const body = new FormData();
      body.append('file', file);
      body.append('language', language);
      const response = await fetch(`${API}/api/pdf/ocr`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body });
      if (!response.ok) throw new Error(await readError(response));
      setResult((await response.json()) as Result);
    } catch (failure) { setError(networkMessage(failure, 'OCR failed.')); }
    finally { setBusy(false); }
  }

  async function copy() {
    if (!result?.text) return;
    try { await navigator.clipboard.writeText(result.text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }
    catch { setError('Could not copy to the clipboard.'); }
  }

  const codes = status ? Object.keys(status.supported_language_codes) : [];
  return (
    <section className="panel advanced-tool-panel vx-ocr">
      <div className="conversion-heading"><div><h2>OCR PDF</h2><p>Read text from scanned PDFs and images, page by page. Pages that already contain text are not re-scanned.</p></div></div>
      {!token && <p className="inline-hint">Sign in to use OCR.</p>}
      {status && !status.available && <p className="ai-error" role="alert">{status.reason}</p>}
      <label className="file-drop"><UploadCloud size={22} /><b>{file ? file.name : 'Choose a scanned PDF or image'}</b><small>PDF, PNG, JPG or WebP · up to 50 MB</small>
        <input type="file" style={{ display: 'none' }} accept=".pdf,application/pdf,image/png,image/jpeg,image/webp" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setResult(null); setError(''); event.target.value = ''; }} />
      </label>
      {codes.length > 0 && (
        <label className="vx-field">Document language
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="">Automatic (installed languages)</option>
            {codes.map((code) => <option key={code} value={code}>{NAMES[code] ?? code}</option>)}
          </select>
        </label>
      )}
      <button className="primary" disabled={!file || !token || busy} onClick={() => void run()}><ScanText size={16} /> {busy ? 'Reading pages…' : 'Run OCR'}</button>
      {error && <p className="ai-error" role="alert">{error}</p>}
      {result && <>
        <p className="operation-notice" role="status">
          Read {result.processed_pages} of {result.page_count} page{result.page_count === 1 ? '' : 's'} · {result.ocr_pages} scanned with OCR
          {result.unreadable_pages.length > 0 && ` · no readable text on page${result.unreadable_pages.length === 1 ? '' : 's'} ${result.unreadable_pages.join(', ')}`}
          {result.truncated && ' · only the first pages were processed (limit reached)'}
        </p>
        <div className="vx-output">
          <button type="button" className="vx-copy-icon" aria-label="Copy extracted text" title="Copy" disabled={!result.text} onClick={() => void copy()}>{copied ? <Check size={15} /> : <Copy size={15} />}</button>
          <pre>{result.text || 'No readable text was found.'}</pre>
        </div>
        <div className="vx-row-actions">
          <ExportMenu token={token} text={result.text} title={(file?.name ?? 'ocr-result').replace(/\.[^.]+$/, '') + '-ocr'} source="ocr" />
          {onUseText && <button disabled={!result.text} onClick={() => onUseText(result.text)}>Use text in AI Documents</button>}
        </div>
      </>}
    </section>
  );
}

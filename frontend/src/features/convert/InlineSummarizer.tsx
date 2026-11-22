import { useRef, useState } from 'react';
import { Copy, RefreshCw, Sparkles, UploadCloud, X } from 'lucide-react';
import { API, networkMessage, readError } from '../../lib/api';
import { ExportMenu } from '../export/ExportMenu';

const LANGS: [string, string][] = [['en', 'English'], ['ta', 'Tamil'], ['hi', 'Hindi'], ['ml', 'Malayalam'], ['te', 'Telugu'], ['kn', 'Kannada'], ['bn', 'Bengali'], ['fr', 'French'], ['de', 'German'], ['es', 'Spanish'], ['ja', 'Japanese']];

export function InlineSummarizer({ token, onClose }: { token: string; onClose: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [length, setLength] = useState('medium');
  const [language, setLanguage] = useState('en');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ summary: string; words: number; summary_words: number; name: string } | null>(null);
  const [notice, setNotice] = useState('');

  async function run() {
    if (!file) { setError('Choose a document first.'); return; }
    setBusy(true); setError(''); setResult(null);
    const form = new FormData();
    form.append('file', file); form.append('length', length); form.append('language', language);
    try {
      const response = await fetch(`${API}/api/ai/summarize-file`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
      if (!response.ok) throw new Error(await readError(response));
      setResult(await response.json());
    } catch (e) { setError(networkMessage(e, 'Could not summarize this document.')); } finally { setBusy(false); }
  }

  return (
    <section className="panel advanced-tool-panel inline-tool" aria-label="AI PDF Summarizer">
      <div className="conversion-heading"><div><h2>AI PDF Summarizer</h2><p>Upload a PDF, Word, text or image document and get the key points in your document&apos;s own language, in seconds.</p></div>
        <button type="button" className="inline-close" aria-label="Close tool" onClick={onClose}><X size={16} /></button></div>
      <input ref={input} type="file" hidden accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.rtf,.html,.htm,.csv,.epub,.jpg,.jpeg,.png,.webp" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(''); e.target.value = ''; }} />
      <button type="button" className="file-drop" onClick={() => input.current?.click()}><UploadCloud size={22} /><b>{file ? file.name : 'Choose a document'}</b><small>PDF, Word, PowerPoint, Excel, text, images · up to 50 MB</small></button>
      <div className="template-style-options">
        <label className="field-label">Summary length<select value={length} onChange={(e) => setLength(e.target.value)}><option value="short">Short</option><option value="medium">Medium</option><option value="long">Detailed</option></select></label>
        <label className="field-label">Preferred language<select value={language} onChange={(e) => setLanguage(e.target.value)}>{LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></label>
      </div>
      <button type="button" className="primary full-button" disabled={busy || !file} onClick={() => void run()}>{busy ? <><RefreshCw className="spin" size={15} /> Summarizing…</> : <><Sparkles size={15} /> Summarize</>}</button>
      {error && <p className="ai-error" role="alert">{error}</p>}
      {result && <section className="ai-response-card"><div className="ai-response-heading"><span><b>Summary of {result.name}</b><small>{result.summary_words} of {result.words} words</small></span>
        <button type="button" onClick={() => { void navigator.clipboard?.writeText(result.summary); setNotice('Copied.'); }}><Copy size={14} /><span>Copy</span></button></div>
        <p style={{ whiteSpace: 'pre-wrap' }}>{result.summary}</p>
        <ExportMenu token={token} text={result.summary} title="summary" source="summarizer" className="language-bridge-download-button" onMessage={setNotice} />
        {notice && <small role="status">{notice}</small>}</section>}
    </section>
  );
}

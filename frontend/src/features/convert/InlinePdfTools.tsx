import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, RefreshCw, Save, Trash2, UploadCloud, X } from 'lucide-react';
import { API, networkMessage, readError, saveBlob } from '../../lib/api';

export type InlineKind =
  | 'info' | 'merge' | 'split' | 'rotate' | 'remove-pages' | 'extract-pages' | 'organize'
  | 'protect' | 'unlock' | 'text' | 'compress' | 'flip' | 'read';

const META: Record<InlineKind, { title: string; help: string; multi?: boolean }> = {
  info: { title: 'PDF information', help: 'See the page count and document properties.' },
  merge: { title: 'Merge PDF', help: 'Combine two or more PDFs, in the order shown.', multi: true },
  split: { title: 'Split PDF', help: 'Create a new PDF from the pages you list.' },
  rotate: { title: 'Rotate PDF', help: 'Rotate every page by 90°, 180° or 270°.' },
  'remove-pages': { title: 'Remove pages', help: 'Delete the pages you list.' },
  'extract-pages': { title: 'Extract pages', help: 'Keep only the pages you list.' },
  organize: { title: 'Organize PDF', help: 'Put pages in a new order (pages you leave out are dropped).' },
  protect: { title: 'Protect PDF', help: 'Lock the PDF with a password.' },
  unlock: { title: 'Unlock PDF', help: 'Remove a password you already know.' },
  text: { title: 'PDF to Text', help: 'Read the text inside a PDF.' },
  compress: { title: 'Compress PDF', help: 'Make the file smaller, optionally to a target size.' },
  flip: { title: 'Flip PDF', help: 'Mirror every page horizontally or vertically.' },
  read: { title: 'PDF Reader', help: 'Read a PDF right here, and copy its text if you need it.' },
};

const formatSize = (bytes: number) => (bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

type Props = { kind: InlineKind; token: string; onClose: () => void; onSaved?: () => void };

export function InlinePdfTools({ kind, token, onClose, onSaved }: Props) {
  const meta = META[kind];
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [pages, setPages] = useState('');
  const [degrees, setDegrees] = useState('90');
  const [password, setPassword] = useState('');
  const [target, setTarget] = useState('');
  const [unit, setUnit] = useState<'kb' | 'mb'>('kb');
  const [direction, setDirection] = useState('horizontal');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [text, setText] = useState('');
  const [output, setOutput] = useState<{ file: File; url: string } | null>(null);
  const readerUrl = useMemo(() => (kind === 'read' && files[0] ? URL.createObjectURL(files[0]) : ''), [kind, files]);

  useEffect(() => () => { if (readerUrl) URL.revokeObjectURL(readerUrl); }, [readerUrl]);
  useEffect(() => () => { if (output) URL.revokeObjectURL(output.url); }, [output]);
  useEffect(() => { setFiles([]); setOutput(null); setText(''); setError(''); setNotice(''); setPages(''); setPassword(''); }, [kind]);

  function choose(list: FileList | null) {
    const picked = Array.from(list ?? []).filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
    if (!picked.length) { setError('Choose a PDF file.'); return; }
    if (picked.some((f) => f.size > 50 * 1024 * 1024)) { setError('Each PDF must be 50 MB or smaller.'); return; }
    setError(''); setOutput(null); setText(''); setNotice('');
    setFiles(meta.multi ? [...files, ...picked] : picked.slice(0, 1));
  }

  async function call(path: string, form: FormData) {
    const response = await fetch(`${API}${path}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
    if (!response.ok) throw new Error(await readError(response));
    return response;
  }

  async function run(action: InlineKind = kind) {
    setError(''); setNotice(''); setText('');
    if (!files.length) { setError('Choose a PDF file first.'); return; }
    if (action === 'merge' && files.length < 2) { setError('Add at least two PDFs to merge.'); return; }
    if (['split', 'remove-pages', 'extract-pages'].includes(action) && !pages.trim()) { setError('Enter page numbers separated by commas, for example 1,3,5.'); return; }
    if (action === 'organize' && !pages.trim()) { setError('Enter the new page order, for example 3,1,2.'); return; }
    if (['protect', 'unlock'].includes(action) && !password) { setError('Enter the PDF password.'); return; }
    let targetBytes: number | null = null;
    if (action === 'compress' && target.trim()) {
      targetBytes = Math.round(Number(target) * (unit === 'mb' ? 1048576 : 1024));
      if (!Number.isFinite(targetBytes) || targetBytes < 1 || targetBytes > 50 * 1048576) { setError('Enter a target greater than zero and no larger than 50 MB.'); return; }
    }
    const form = new FormData();
    if (action === 'merge') files.forEach((f) => form.append('files', f)); else form.append('file', files[0]);
    if (['split', 'remove-pages', 'extract-pages'].includes(action)) form.append('pages', pages);
    if (action === 'organize') { form.append('page_order', pages); form.append('rotations', ''); }
    if (action === 'rotate') form.append('degrees', degrees);
    if (['protect', 'unlock'].includes(action)) form.append('password', password);
    if (action === 'compress') { if (targetBytes !== null) form.append('target_size_bytes', String(targetBytes)); form.append('rasterize_if_needed', 'false'); }
    if (action === 'flip') form.append('options', JSON.stringify({ direction }));
    setBusy(true);
    try {
      const response = await call(action === 'flip' ? '/api/pdf/tools/flip-pdf' : `/api/pdf/${action === 'read' ? 'text' : action}`, form);
      if (action === 'info' || action === 'text' || action === 'read') {
        const result = await response.json();
        setText(action === 'info' ? JSON.stringify(result, null, 2) : result.text || 'No extractable text was found (this may be a scanned PDF — try OCR PDF).');
      } else {
        const blob = await response.blob();
        const file = new File([blob], `vertex-${action}.pdf`, { type: 'application/pdf' });
        setOutput({ file, url: URL.createObjectURL(file) });
        setNotice(action === 'compress' && files[0] ? `Smaller file: ${formatSize(files[0].size)} → ${formatSize(blob.size)}.` : 'Your PDF is ready. Preview it, then download or save it.');
      }
    } catch (e) {
      setError(networkMessage(e, 'The PDF operation failed.'));
    } finally {
      setBusy(false);
    }
  }

  async function saveToWorkspace() {
    if (!output) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', output.file);
      await call('/api/documents/upload', form);
      setNotice(`Saved “${output.file.name}” to your workspace.`);
      onSaved?.();
    } catch (e) { setError(networkMessage(e, 'Could not save the file.')); } finally { setBusy(false); }
  }

  const needsPages = ['split', 'remove-pages', 'extract-pages', 'organize'].includes(kind);
  return (
    <section className="panel advanced-tool-panel inline-tool" aria-label={meta.title}>
      <div className="conversion-heading">
        <div><h2>{meta.title}</h2><p>{meta.help}</p></div>
        <button type="button" className="inline-close" aria-label="Close tool" onClick={onClose}><X size={16} /></button>
      </div>
      <input ref={input} type="file" accept="application/pdf,.pdf" multiple={meta.multi} hidden onChange={(e) => { choose(e.target.files); e.target.value = ''; }} />
      <button type="button" className="file-drop" onClick={() => input.current?.click()}>
        <UploadCloud size={22} />
        <b>{files.length ? files.map((f) => f.name).join(', ') : meta.multi ? 'Choose PDFs' : 'Choose a PDF file'}</b>
        <small>{files.length ? `${files.length} file${files.length === 1 ? '' : 's'} · ${formatSize(files.reduce((n, f) => n + f.size, 0))}${meta.multi ? ' · click to add more' : ''}` : 'PDF files only · up to 50 MB'}</small>
      </button>
      {meta.multi && files.length > 0 && <ol className="inline-file-list">{files.map((f, i) => (
        <li key={`${f.name}-${i}`}><span>{i + 1}. {f.name}</span>
          <button type="button" aria-label={`Move ${f.name} up`} disabled={i === 0} onClick={() => setFiles((l) => { const n = [...l]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; return n; })}>↑</button>
          <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles((l) => l.filter((_, k) => k !== i))}><X size={13} /></button></li>))}</ol>}

      {needsPages && <label className="field-label">{kind === 'organize' ? 'New page order' : 'Pages'}<input value={pages} onChange={(e) => setPages(e.target.value)} placeholder={kind === 'organize' ? 'e.g. 3,1,2' : 'e.g. 1,3,5-7'} /></label>}
      {kind === 'rotate' && <label className="field-label">Rotate by<select value={degrees} onChange={(e) => setDegrees(e.target.value)}><option value="90">90° clockwise</option><option value="180">180°</option><option value="270">270° (90° anticlockwise)</option></select></label>}
      {(kind === 'protect' || kind === 'unlock') && <label className="field-label">Password<input type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} /></label>}
      {kind === 'compress' && <div className="template-style-options"><label className="field-label">Target size (optional)<input type="number" min={1} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="e.g. 500" /></label><label className="field-label">Unit<select value={unit} onChange={(e) => setUnit(e.target.value as 'kb' | 'mb')}><option value="kb">KB</option><option value="mb">MB</option></select></label></div>}
      {kind === 'flip' && <label className="field-label">Direction<select value={direction} onChange={(e) => setDirection(e.target.value)}><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option></select></label>}

      {kind !== 'read' && <button type="button" className="primary full-button" disabled={busy || !files.length} onClick={() => void run()}>{busy ? <><RefreshCw className="spin" size={15} /> Working…</> : `Run ${meta.title}`}</button>}
      {kind === 'read' && files.length > 0 && <>
        <iframe className="pdf-preview-frame" src={readerUrl} title="PDF reader" />
        <div className="pdf-output-actions"><button type="button" disabled={busy} onClick={() => void run('read')}>{busy ? 'Reading…' : 'Show text'}</button></div></>}
      {error && <p className="ai-error" role="alert">{error}</p>}
      {notice && <p className="operation-notice" role="status">{notice}</p>}
      {text && <pre className="operation-result">{text}</pre>}
      {output && <>
        <iframe className="pdf-preview-frame" src={output.url} title={`${meta.title} result`} />
        <div className="pdf-output-actions">
          <button type="button" className="primary" onClick={() => saveBlob(output.file, output.file.name)}><Download size={15} /> Download</button>
          <button type="button" disabled={busy} onClick={() => void saveToWorkspace()}><Save size={15} /> Save to workspace</button>
          <button type="button" className="discard-button" onClick={() => setOutput(null)}><Trash2 size={15} /> Discard</button>
        </div></>}
    </section>
  );
}

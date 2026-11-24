import { useRef, useState } from 'react';
import { RefreshCw, UploadCloud, X } from 'lucide-react';
import { API, networkMessage, readError } from '../../lib/api';
import { PdfAnnotator } from '../annotator/PdfAnnotator';

/** Edit PDF without leaving Convert: the file is added to your workspace, then opened in the annotator (highlight, draw, text, shapes). */
export function InlineEditPdf({ token, onClose, onSaved }: { token: string; onClose: () => void; onSaved?: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [doc, setDoc] = useState<{ id: number; name: string } | null>(null);

  async function open(file?: File) {
    if (!file) return;
    if (!(file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'))) { setError('Choose a PDF file.'); return; }
    setBusy(true); setError('');
    const form = new FormData(); form.append('file', file);
    try {
      const response = await fetch(`${API}/api/documents/upload`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
      if (!response.ok) throw new Error(await readError(response));
      const result = await response.json();
      setDoc({ id: result.id, name: result.name });
      onSaved?.();
    } catch (e) { setError(networkMessage(e, 'Could not open this PDF.')); } finally { setBusy(false); }
  }

  if (doc) return <PdfAnnotator token={token} documentId={doc.id} name={doc.name} onClose={() => { setDoc(null); onClose(); }} />;
  return (
    <section className="panel advanced-tool-panel inline-tool" aria-label="Edit PDF">
      <div className="conversion-heading"><div><h2>Edit PDF</h2><p>Highlight, draw, add text and shapes, then save your changes. The PDF is added to your workspace.</p></div>
        <button type="button" className="inline-close" aria-label="Close tool" onClick={onClose}><X size={16} /></button></div>
      <input ref={input} type="file" hidden accept="application/pdf,.pdf" onChange={(e) => { void open(e.target.files?.[0]); e.target.value = ''; }} />
      <button type="button" className="file-drop" disabled={busy} onClick={() => input.current?.click()}>{busy ? <RefreshCw className="spin" size={22} /> : <UploadCloud size={22} />}<b>{busy ? 'Opening…' : 'Choose a PDF to edit'}</b><small>PDF files only · up to 50 MB</small></button>
      {error && <p className="ai-error" role="alert">{error}</p>}
    </section>
  );
}

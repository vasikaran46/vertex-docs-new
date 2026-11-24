import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { apiJson, networkMessage } from '../../lib/api';

type PageResult = { page_number: number; page_count: number; image_data: string };

type Props = { token: string; documentId: number; name: string; onClose: () => void };

export function DocumentPreview({ token, documentId, name, onClose }: Props) {
  const isPdf = name.toLowerCase().endsWith('.pdf');
  const [page, setPage] = useState(1);
  const [image, setImage] = useState<PageResult | null>(null);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    const request = isPdf
      ? apiJson<PageResult>(`/api/documents/${documentId}/page/${page}`, token).then((result) => { if (!cancelled) setImage(result); })
      : apiJson<{ text: string; truncated: boolean }>(`/api/documents/${documentId}/text`, token).then((result) => { if (!cancelled) setText(result.text + (result.truncated ? '\n\n… (preview truncated)' : '')); });
    request.catch((failure) => { if (!cancelled) setError(networkMessage(failure, 'Could not preview this document.')); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, documentId, page, isPdf]);

  return (
    <div className="vx-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="vx-modal vx-preview" role="dialog" aria-modal="true" aria-label={`Preview ${name}`}>
        <header><h3>{name}</h3><button className="vx-close" aria-label="Close preview" onClick={onClose}><X size={16} /></button></header>
        {loading && <p className="inline-hint">Loading preview…</p>}
        {error && <p className="ai-error" role="alert">{error}</p>}
        {!loading && !error && isPdf && image && <>
          <img alt={`Page ${image.page_number} of ${name}`} src={`data:image/png;base64,${image.image_data}`} />
          <div className="vx-pager">
            <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
            <span>Page {image.page_number} of {image.page_count}</span>
            <button disabled={page >= image.page_count} onClick={() => setPage((value) => value + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
          </div>
        </>}
        {!loading && !error && !isPdf && <pre className="vx-text-preview">{text || 'No readable text was found in this document.'}</pre>}
      </section>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react';
import { ChevronLeft, ChevronRight, Download, Eraser, Highlighter, Pen, Save, Square, Type, Undo2, X } from 'lucide-react';
import { API, apiJson, filenameFrom, networkMessage, readError, saveBlob } from '../../lib/api';

type Tool = 'highlight' | 'rect' | 'pen' | 'text' | 'eraser';
type Annotation = {
  id: string; type: 'highlight' | 'rect' | 'pen' | 'text'; page: number; color: string;
  x?: number; y?: number; w?: number; h?: number; points?: [number, number][]; width?: number; text?: string; size?: number;
};
type PageImage = { page_number: number; page_count: number; width: number; height: number; image_data: string };

const COLORS = ['#ffe066', '#ff8787', '#69db7c', '#74c0fc', '#212529', '#d6336c'];
const SCALE = 1.35; // matches the backend page renderer (pixels per PDF point)
const clamp = (value: number) => Math.min(1, Math.max(0, value));
const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

type Props = { token: string; documentId: number; name: string; onClose: () => void };

export function PdfAnnotator({ token, documentId, name, onClose }: Props) {
  const [page, setPage] = useState(1);
  const [image, setImage] = useState<PageImage | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [tool, setTool] = useState<Tool>('highlight');
  const [color, setColor] = useState(COLORS[0]);
  const [draft, setDraft] = useState<Annotation | null>(null);
  const [textAt, setTextAt] = useState<{ x: number; y: number } | null>(null);
  const [textValue, setTextValue] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const surface = useRef<SVGSVGElement>(null);
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  const latest = useRef(annotations);
  latest.current = annotations;

  useEffect(() => {
    apiJson<{ annotations: Annotation[] }>(`/api/documents/${documentId}/annotations`, token)
      .then((result) => { setAnnotations(result.annotations); setLoaded(true); })
      .catch((failure) => setError(networkMessage(failure, 'Could not load saved annotations.')));
  }, [documentId, token]);

  useEffect(() => {
    let cancelled = false;
    setError('');
    apiJson<PageImage>(`/api/documents/${documentId}/page/${page}`, token)
      .then((result) => { if (!cancelled) setImage(result); })
      .catch((failure) => { if (!cancelled) setError(networkMessage(failure, 'Could not render this page.')); });
    return () => { cancelled = true; };
  }, [documentId, token, page]);

  const save = useCallback(async (silent = false) => {
    setSaving(true);
    try {
      await apiJson(`/api/documents/${documentId}/annotations`, token, { method: 'PUT', body: JSON.stringify({ annotations: latest.current }) });
      setDirty(false);
      setError('');
      if (!silent) setMessage('Annotations saved. They will be here when you reopen this PDF.');
    } catch (failure) { setError(networkMessage(failure, 'Annotations could not be saved.')); }
    finally { setSaving(false); }
  }, [documentId, token]);

  // Autosave shortly after each change so a refresh never loses work.
  useEffect(() => {
    if (!dirty || !loaded) return;
    const timer = window.setTimeout(() => void save(true), 1500);
    return () => window.clearTimeout(timer);
  }, [dirty, annotations, loaded, save]);

  function change(next: Annotation[]) { setAnnotations(next); setDirty(true); setMessage(''); }

  function point(event: React.PointerEvent): { x: number; y: number } {
    const box = surface.current!.getBoundingClientRect();
    return { x: clamp((event.clientX - box.left) / box.width), y: clamp((event.clientY - box.top) / box.height) };
  }

  function down(event: React.PointerEvent<SVGSVGElement>) {
    if (!image || tool === 'eraser') return;
    const at = point(event);
    if (tool === 'text') { setTextAt(at); setTextValue(''); return; }
    surface.current?.setPointerCapture(event.pointerId);
    dragStart.current = at;
    if (tool === 'pen') setDraft({ id: newId(), type: 'pen', page, color, width: 2, points: [[at.x, at.y], [at.x, at.y]] });
    else setDraft({ id: newId(), type: tool, page, color, x: at.x, y: at.y, w: 0, h: 0 });
  }
  function move(event: React.PointerEvent<SVGSVGElement>) {
    if (!draft || !dragStart.current) return;
    const at = point(event);
    if (draft.type === 'pen') setDraft({ ...draft, points: [...(draft.points ?? []), [at.x, at.y]].slice(-3000) as [number, number][] });
    else {
      const start = dragStart.current;
      setDraft({ ...draft, x: Math.min(start.x, at.x), y: Math.min(start.y, at.y), w: Math.abs(at.x - start.x), h: Math.abs(at.y - start.y) });
    }
  }
  function up() {
    if (!draft) return;
    const tooSmall = draft.type !== 'pen' && ((draft.w ?? 0) < 0.004 || (draft.h ?? 0) < 0.004);
    if (!tooSmall) change([...annotations, draft]);
    setDraft(null);
    dragStart.current = null;
  }
  function commitText() {
    if (textAt && textValue.trim()) change([...annotations, { id: newId(), type: 'text', page, color, x: textAt.x, y: textAt.y, text: textValue.trim(), size: 14 }]);
    setTextAt(null); setTextValue('');
  }
  function erase(id: string) { if (tool === 'eraser') change(annotations.filter((item) => item.id !== id)); }

  async function download() {
    try {
      if (dirty) await save(true);
      const response = await fetch(`${API}/api/documents/${documentId}/annotated-pdf`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error(await readError(response));
      const filename = filenameFrom(response, name.replace(/\.pdf$/i, '') + '-annotated.pdf');
      saveBlob(await response.blob(), filename);
      setMessage(`Downloaded ${filename} with your annotations included.`);
    } catch (failure) { setError(networkMessage(failure, 'Could not export the annotated PDF.')); }
  }

  async function close() {
    if (dirty) await save(true);
    onClose();
  }

  const width = image?.width ?? 1;
  const height = image?.height ?? 1;
  const shown = [...annotations.filter((item) => item.page === page), ...(draft ? [draft] : [])];

  function render(item: Annotation) {
    const common = { key: item.id, onPointerDown: () => erase(item.id), style: { cursor: tool === 'eraser' ? 'pointer' : 'inherit' } };
    if (item.type === 'highlight') return <rect {...common} x={(item.x ?? 0) * width} y={(item.y ?? 0) * height} width={(item.w ?? 0) * width} height={(item.h ?? 0) * height} fill={item.color} fillOpacity={0.4} />;
    if (item.type === 'rect') return <rect {...common} x={(item.x ?? 0) * width} y={(item.y ?? 0) * height} width={(item.w ?? 0) * width} height={(item.h ?? 0) * height} fill="transparent" stroke={item.color} strokeWidth={2} />;
    if (item.type === 'pen') return <polyline {...common} points={(item.points ?? []).map(([px, py]) => `${px * width},${py * height}`).join(' ')} fill="none" stroke={item.color} strokeWidth={(item.width ?? 2) * SCALE} strokeLinecap="round" strokeLinejoin="round" />;
    return <text {...common} x={(item.x ?? 0) * width} y={(item.y ?? 0) * height + (item.size ?? 14) * SCALE} fill={item.color} fontSize={(item.size ?? 14) * SCALE}>{item.text}</text>;
  }

  const tools: [Tool, string, ReactElement][] = [
    ['highlight', 'Highlight', <Highlighter size={15} key="h" />], ['rect', 'Box', <Square size={15} key="r" />], ['pen', 'Pen', <Pen size={15} key="p" />],
    ['text', 'Text', <Type size={15} key="t" />], ['eraser', 'Eraser', <Eraser size={15} key="e" />],
  ];

  return (
    <div className="vx-modal-backdrop vx-annotator-backdrop" role="presentation">
      <section className="vx-modal vx-annotator" role="dialog" aria-modal="true" aria-label={`Annotate ${name}`}>
        <header><h3>{name}</h3><button className="vx-close" aria-label="Close annotator" onClick={() => void close()}><X size={16} /></button></header>
        <div className="vx-annotator-bar">
          {tools.map(([id, label, icon]) => <button key={id} className={tool === id ? 'active' : ''} aria-pressed={tool === id} onClick={() => setTool(id)}>{icon} {label}</button>)}
          <span className="vx-swatches" role="group" aria-label="Colour">
            {COLORS.map((item) => <button key={item} className={color === item ? 'active' : ''} style={{ background: item }} aria-label={`Colour ${item}`} onClick={() => setColor(item)} />)}
          </span>
          <button disabled={!annotations.some((item) => item.page === page)} onClick={() => { const last = [...annotations].reverse().find((item) => item.page === page); if (last) change(annotations.filter((item) => item.id !== last.id)); }}><Undo2 size={15} /> Undo</button>
          <button disabled={saving || !dirty} onClick={() => void save()}><Save size={15} /> {saving ? 'Saving…' : dirty ? 'Save' : 'Saved'}</button>
          <button onClick={() => void download()}><Download size={15} /> Download PDF</button>
        </div>
        {error && <p className="ai-error" role="alert">{error}</p>}
        {message && <p className="operation-notice" role="status">{message}</p>}
        <div className="vx-annotator-stage">
          {!image ? <p className="inline-hint">Loading page…</p> : (
            <div className="vx-annotator-page" style={{ aspectRatio: `${width} / ${height}` }}>
              <img alt={`Page ${page}`} src={`data:image/png;base64,${image.image_data}`} draggable={false} />
              <svg ref={surface} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} style={{ cursor: tool === 'eraser' ? 'default' : tool === 'text' ? 'text' : 'crosshair' }}>
                {shown.map(render)}
              </svg>
              {textAt && (
                <input className="vx-text-input" autoFocus value={textValue} placeholder="Type, then press Enter" style={{ left: `${textAt.x * 100}%`, top: `${textAt.y * 100}%` }}
                  onChange={(event) => setTextValue(event.target.value)} onBlur={commitText}
                  onKeyDown={(event) => { if (event.key === 'Enter') commitText(); if (event.key === 'Escape') { setTextAt(null); setTextValue(''); } }} />
              )}
            </div>
          )}
        </div>
        {image && (
          <div className="vx-pager">
            <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
            <span>Page {page} of {image.page_count}</span>
            <button disabled={page >= image.page_count} onClick={() => setPage((value) => value + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
          </div>
        )}
      </section>
    </div>
  );
}

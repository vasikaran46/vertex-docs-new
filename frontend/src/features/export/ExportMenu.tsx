import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Download } from 'lucide-react';
import { API, filenameFrom, readError, saveBlob, networkMessage } from '../../lib/api';

const FORMATS: [string, string][] = [
  ['txt', 'Plain text (.txt)'],
  ['docx', 'Word (.docx)'],
  ['pdf', 'PDF (.pdf)'],
  ['pptx', 'PowerPoint (.pptx)'],
  ['html', 'Web page (.html)'],
  ['md', 'Markdown (.md)'],
  ['rtf', 'Rich text (.rtf)'],
  ['json', 'JSON (.json)'],
];

type Props = {
  token: string | null;
  text: string;
  title: string;
  source: string;
  className?: string;
  label?: string;
  onMessage?: (message: string, isError: boolean) => void;
};

/** One clear "Export As" control that creates a real file on the backend. */
export function ExportMenu({ token, text, title, source, className = '', label = 'Export As', onMessage }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const disabled = !text.trim() || !token || busy;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', escape); };
  }, [open]);

  async function run(format: string) {
    setOpen(false);
    if (!token) return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/export/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text, title, format, source }),
      });
      if (!response.ok) throw new Error(await readError(response));
      const name = filenameFrom(response, `${title}.${format}`);
      saveBlob(await response.blob(), name);
      onMessage?.(`Exported ${name}.`, false);
    } catch (error) {
      onMessage?.(networkMessage(error, 'Export failed.'), true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="vx-export" ref={root}>
      <button type="button" className={className} disabled={disabled} aria-haspopup="menu" aria-expanded={open} title={!token ? 'Sign in to export' : undefined} onClick={() => setOpen((value) => !value)}>
        <Download size={14} /> {busy ? 'Exporting…' : label} <ChevronDown size={13} />
      </button>
      {open && (
        <div className="vx-menu" role="menu">
          {FORMATS.map(([id, name]) => <button type="button" role="menuitem" key={id} onClick={() => void run(id)}>{name}</button>)}
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { Printer, X } from 'lucide-react';
import { EditorToolbar } from '../pdf-studio/EditorToolbar';
import { ensureBlocks, EDITOR_CSS } from '../pdf-studio/richText';
import { useRichEditor } from '../pdf-studio/useRichEditor';
import { ExportMenu } from '../export/ExportMenu';

/** Word-style document editor for the Convert page: full rich toolbar, print/Save-as-PDF (keeps formatting) and text exports. */
export function DocumentEditor({ token, onClose }: { token: string; onClose: () => void }) {
  const [text, setText] = useState('');
  const [notice, setNotice] = useState('');
  const { ref, imageInput, toolbar, insertImageFile, remember } = useRichEditor('Calibri', 14, () => { if (ref.current) setText(ref.current.innerText); });
  const font = toolbar.fontFamily;
  const size = toolbar.fontSize;
  const sync = () => { if (ref.current) setText(ref.current.innerText); };

  function print() {
    const editor = ref.current; if (!editor) return;
    const frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
    document.body.appendChild(frame);
    const doc = frame.contentDocument!;
    doc.open();
    doc.write(`<!doctype html><html><head><meta charset="utf-8"><title>Document</title><style>@page{size:A4;margin:18mm}body{font:${size}px/1.6 "${font}",Calibri,Arial,sans-serif;color:#111}img{max-width:100%}${EDITOR_CSS}</style></head><body class="vd-rich">${editor.innerHTML}</body></html>`);
    doc.close();
    frame.onload = () => { frame.contentWindow?.focus(); frame.contentWindow?.print(); setTimeout(() => frame.remove(), 1500); };
    setNotice('In the print window choose “Save as PDF” to keep fonts, bullets and spacing exactly as you see them.');
  }

  return (
    <section className="panel advanced-tool-panel inline-tool" aria-label="Word and Document Editor">
      <div className="conversion-heading"><div><h2>Word and Document Editor</h2><p>Write and format a document, then save it as PDF, Word, text and more.</p></div>
        <button type="button" className="inline-close" aria-label="Close tool" onClick={onClose}><X size={16} /></button></div>
      <EditorToolbar {...toolbar} />
      <input ref={imageInput} type="file" accept="image/*" hidden onChange={(e) => { insertImageFile(e.target.files?.[0]); e.target.value = ''; }} />
      <div className="doc-editor-paper-wrap"><div ref={ref} className="doc-editor-paper vd-rich" contentEditable suppressContentEditableWarning spellCheck aria-label="Document body" role="textbox" aria-multiline="true"
        onInput={sync} onKeyUp={remember} onMouseUp={remember} onFocus={(e) => ensureBlocks(e.currentTarget)} style={{ fontFamily: `"${font}", Calibri, Arial, sans-serif`, fontSize: size }} /></div>
      <div className="pdf-output-actions">
        <button type="button" className="primary" onClick={print}><Printer size={15} /> Save as PDF / Print</button>
        <ExportMenu token={token} text={text} title="document" source="editor" className="language-bridge-download-button" onMessage={setNotice} />
      </div>
      {notice && <p className="operation-notice" role="status">{notice}</p>}
    </section>
  );
}

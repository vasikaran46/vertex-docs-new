import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Download, FileText, Printer, RotateCcw, Search, Sparkles } from 'lucide-react';
import { EditorToolbar } from '../pdf-studio/EditorToolbar';
import { EDITOR_CSS, FONT_FAMILIES, ensureBlocks } from '../pdf-studio/richText';
import { useRichEditor } from '../pdf-studio/useRichEditor';
import { atsScore, buildDefaultHtml, templateCatalog, templateCategories, type TemplateItem } from './catalog';

const ACCENTS = ['#1f3a5f', '#6a3df0', '#2563eb', '#0f766e', '#047857', '#b45309', '#be185d', '#b91c1c', '#374151', '#7c3aed'];

function Thumb({ item, name, email }: { item: TemplateItem; name: string; email: string }) {
  const html = useMemo(() => buildDefaultHtml(item, name, email), [item, name, email]);
  return (
    <div className="tpl-thumb" aria-hidden="true">
      <div className="tpl-thumb-paper" style={{ ['--tpl-accent' as string]: item.accent, fontFamily: item.font }} dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

export function TemplateStudio({ token, userName, userEmail }: { token: string; userName: string; userEmail: string }) {
  const [category, setCategory] = useState<(typeof templateCategories)[number]>('All');
  const [query, setQuery] = useState('');
  const [active, setActive] = useState<TemplateItem | null>(null);
  const [accent, setAccent] = useState('#6a3df0');
  const [jd, setJd] = useState('');
  const [plain, setPlain] = useState('');
  const [notice, setNotice] = useState('');
  const paperText = () => ref.current?.innerText ?? '';
  const { ref, imageInput, toolbar, insertImageFile, setFont } = useRichEditor('Calibri', 14, () => setPlain(paperText()));
  const initial = useRef('');

  const shown = templateCatalog.filter((t) => (category === 'All' || t.category === category)
    && (!query.trim() || `${t.name} ${t.description} ${t.category}`.toLowerCase().includes(query.toLowerCase())));

  function open(item: TemplateItem) {
    setActive(item);
    setAccent(item.accent);
    setFont(FONT_FAMILIES.includes(item.font) ? item.font : 'Arial');
    setNotice('');
    setJd('');
    initial.current = buildDefaultHtml(item, userName, userEmail);
  }

  useEffect(() => {
    if (active && ref.current) {
      ref.current.innerHTML = initial.current;
      setPlain(ref.current.innerText);
      window.scrollTo({ top: 0 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const ats = useMemo(() => (active?.ats ? atsScore(plain, jd) : null), [active, plain, jd]);

  function printDoc() {
    const editor = ref.current;
    if (!editor || !active) return;
    const frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
    document.body.appendChild(frame);
    const doc = frame.contentDocument!;
    doc.open();
    doc.write(`<!doctype html><html><head><meta charset="utf-8"><title>${active.name}</title><style>@page{size:A4;margin:0}html,body{margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}body{--tpl-accent:${accent};font:14px/1.55 "${toolbar.fontFamily}",Arial,sans-serif;color:#1b1d22}img{max-width:100%}${EDITOR_CSS}</style></head><body class="vd-rich">${editor.innerHTML}</body></html>`);
    doc.close();
    frame.onload = () => { frame.contentWindow?.focus(); frame.contentWindow?.print(); setTimeout(() => frame.remove(), 1500); };
    setNotice('In the print window, choose “Save as PDF” and set Margins to “None” for an exact copy.');
  }

  function downloadWord() {
    const editor = ref.current;
    if (!editor || !active) return;
    const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><title>${active.name}</title><style>body{--tpl-accent:${accent};font-family:"${toolbar.fontFamily}",Arial;}</style></head><body>${editor.innerHTML.replace(/var\(--tpl-accent\)/g, accent)}</body></html>`;
    const url = URL.createObjectURL(new Blob(['\ufeff', html], { type: 'application/msword' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${active.name.replace(/[^\w]+/g, '-').toLowerCase()}.doc`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setNotice('Downloaded a Word-compatible file. Open it in Word to keep editing.');
  }

  if (!active) {
    return (
      <div className="tpl-gallery">
        <div className="tpl-gallery-bar">
          <div className="tpl-chips" role="tablist" aria-label="Template categories">
            {templateCategories.map((c) => <button key={c} role="tab" aria-selected={category === c} className={category === c ? 'active' : ''} onClick={() => setCategory(c)}>{c}</button>)}
          </div>
          <label className="tpl-search"><Search size={14} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search templates…" aria-label="Search templates" /></label>
        </div>
        {!shown.length && <p className="inline-hint">No templates match your search.</p>}
        <div className="tpl-grid">
          {shown.map((t) => (
            <button key={t.id} className="tpl-card" onClick={() => open(t)} aria-label={`Use template: ${t.name}`}>
              <Thumb item={t} name={userName} email={userEmail} />
              <div className="tpl-card-body"><span className="tpl-cat">{t.category}</span>{t.ats && <span className="tpl-ats">ATS-friendly</span>}<b>{t.name}</b><small>{t.description}</small></div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="tpl-editor">
      <div className="tpl-editor-bar">
        <button onClick={() => setActive(null)}><ArrowLeft size={15} /> All templates</button>
        <b>{active.name}</b>
        <span className="tpl-bar-spacer" />
        <label className="tpl-accent-picker">Colour {ACCENTS.map((c) => <button key={c} aria-label={`Accent ${c}`} className={accent === c ? 'on' : ''} style={{ background: c }} onClick={() => setAccent(c)} />)}<input type="color" aria-label="Custom accent colour" value={accent} onChange={(e) => setAccent(e.target.value)} /></label>
        <button onClick={() => { if (ref.current && window.confirm('Reset this template to its original content? Your edits will be lost.')) { ref.current.innerHTML = initial.current; setPlain(ref.current.innerText); } }}><RotateCcw size={14} /> Reset</button>
        <button onClick={downloadWord}><FileText size={14} /> Word</button>
        <button className="primary" onClick={printDoc}><Printer size={14} /> Save as PDF</button>
      </div>
      <EditorToolbar {...toolbar} />
      <input ref={imageInput} type="file" accept="image/*" hidden onChange={(e) => { insertImageFile(e.target.files?.[0]); e.target.value = ''; }} />
      <div className="tpl-editor-body">
        <div className="tpl-paper-wrap">
          <div ref={ref} className="tpl-paper vd-rich" contentEditable suppressContentEditableWarning spellCheck role="textbox" aria-multiline="true" aria-label={`${active.name} – click any text to edit`}
            style={{ ['--tpl-accent' as string]: accent, fontFamily: `"${toolbar.fontFamily}", Arial, sans-serif`, fontSize: toolbar.fontSize }}
            onInput={() => setPlain(paperText())} onKeyUp={toolbar.onRemember} onMouseUp={toolbar.onRemember} onFocus={(e) => ensureBlocks(e.currentTarget)} />
        </div>
        {ats && (
          <aside className="tpl-ats-panel" aria-label="ATS score">
            <div className="tpl-ats-score" style={{ ['--score' as string]: ats.score }}><b>{ats.score}</b><small>ATS score</small></div>
            <p className="tpl-ats-note"><Sparkles size={13} /> Updates live as you edit. Scores are an estimate based on common ATS rules, not a guarantee.</p>
            <ul className="tpl-ats-checks">{ats.checks.map((c) => <li key={c.label} className={c.ok ? 'ok' : 'bad'}><b>{c.ok ? '✓' : '✗'} {c.label}</b>{!c.ok && <small>{c.tip}</small>}</li>)}</ul>
            <label className="field-label">Paste a job description to check keyword match<textarea rows={5} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the job posting here…" /></label>
          </aside>
        )}
      </div>
      {notice && <p className="operation-notice" role="status">{notice}</p>}
      {!token && <p className="inline-hint">Sign in to save work to your workspace.</p>}
    </div>
  );
}

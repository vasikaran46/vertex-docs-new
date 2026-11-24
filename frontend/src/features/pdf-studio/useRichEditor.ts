import { useRef, useState } from 'react';
import { applyBlockCss, applyListStyle, ensureBlocks, tableHtml, transformCase, type ListStyleOption } from './richText';

/** Props for <EditorToolbar> bound to a contentEditable element. Used by the Document Editor and Template Studio. */
export function useRichEditor(defaultFont = 'Calibri', defaultSize = 14, onChange?: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const saved = useRef<Range | null>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const [font, setFont] = useState(defaultFont);
  const [size, setSize] = useState(defaultSize);

  const remember = () => {
    const sel = window.getSelection();
    if (sel?.rangeCount && ref.current?.contains(sel.anchorNode)) saved.current = sel.getRangeAt(0).cloneRange();
  };

  function edit(fn: (editor: HTMLElement, range: Range | null) => void) {
    const editor = ref.current;
    if (!editor) return;
    editor.focus();
    const sel = window.getSelection();
    if (saved.current && sel) { sel.removeAllRanges(); sel.addRange(saved.current); }
    document.execCommand('styleWithCSS', false, 'true');
    fn(editor, sel && sel.rangeCount ? sel.getRangeAt(0) : null);
    remember();
    onChange?.();
  }

  const caretSpan = (range: Range, css: Partial<CSSStyleDeclaration>) => {
    const span = document.createElement('span');
    Object.assign(span.style, css);
    span.textContent = '\u200B';
    range.insertNode(span);
    range.setStart(span.firstChild as Node, 1);
    range.collapse(true);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  };

  const toolbar = {
    fontFamily: font,
    fontSize: size,
    onRemember: remember,
    onCommand: (c: string, v?: string) => edit(() => { document.execCommand(c, false, c === 'formatBlock' ? `<${v}>` : v); }),
    onFontFamily: (family: string) => { setFont(family); edit((_e, r) => { if (r?.collapsed) caretSpan(r, { fontFamily: `"${family}"` }); else document.execCommand('fontName', false, family); }); },
    onFontSize: (px: number) => {
      setSize(px);
      edit((e, r) => {
        if (r?.collapsed) { caretSpan(r, { fontSize: `${px}px` }); return; }
        document.execCommand('fontSize', false, '7');
        e.querySelectorAll('font[size="7"]').forEach((n) => { const s = document.createElement('span'); s.style.fontSize = `${px}px`; s.innerHTML = (n as HTMLElement).innerHTML; n.replaceWith(s); });
      });
    },
    onBullet: (o: ListStyleOption) => edit((e) => applyListStyle(e, false, o)),
    onNumber: (o: ListStyleOption) => edit((e) => applyListStyle(e, true, o)),
    onLineSpacing: (v: string) => edit((e, r) => applyBlockCss(e, r, { lineHeight: v })),
    onParagraphGap: (px: string) => edit((e, r) => applyBlockCss(e, r, { marginBottom: `${px}px` })),
    onCase: (o: string) => edit((_e, r) => { const t = r?.toString(); if (t) document.execCommand('insertText', false, transformCase(t, o)); }),
    onSymbol: (s: string) => edit(() => { document.execCommand('insertText', false, s); }),
    onTable: (r: number, c: number) => edit(() => { document.execCommand('insertHTML', false, tableHtml(r, c)); }),
    onImage: () => imageInput.current?.click(),
    onClear: () => edit(() => { document.execCommand('removeFormat'); }),
  };

  const insertImageFile = (file?: File) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => edit(() => { document.execCommand('insertImage', false, String(reader.result)); });
    reader.readAsDataURL(file);
  };

  return { ref, imageInput, toolbar, insertImageFile, ensureBlocks, remember, setFont };
}

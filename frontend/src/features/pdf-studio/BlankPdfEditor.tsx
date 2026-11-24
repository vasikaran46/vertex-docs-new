import { useRef, useState } from 'react';
import './BlankPdfEditor.css';

const FONT_FAMILIES = [
  'Arial', 'Calibri', 'Times New Roman', 'Georgia', 'Verdana',
  'Trebuchet MS', 'Courier New', 'Garamond', 'Comic Sans MS', 'Impact',
];

const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 30, 32, 36, 40, 48, 60, 72];

const CASE_OPTIONS = ['Sentence case', 'lowercase', 'UPPERCASE', 'Capitalize Each Word', 'tOGGLE cASE'];

export default function BlankPdfEditor({ onClose }: { onClose?: () => void }) {
  const editorRef = useRef<HTMLDivElement>(null);
  const savedSelRef = useRef<Range | null>(null);
  const [fontFamily, setFontFamily] = useState('Arial');
  const [fontSize, setFontSize] = useState(30);
  const [showCaseMenu, setShowCaseMenu] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showBgColorPicker, setShowBgColorPicker] = useState(false);
  const [fontColor, setFontColor] = useState('#000000');
  const [bgColor, setBgColor] = useState('#ffffff');
  const [lineSpacing, setLineSpacing] = useState('1.5');

  function saveSelection() {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      savedSelRef.current = sel.getRangeAt(0).cloneRange();
    }
  }

  function restoreSelection() {
    const sel = window.getSelection();
    if (sel && savedSelRef.current) {
      sel.removeAllRanges();
      sel.addRange(savedSelRef.current);
    }
  }

  function exec(command: string, value?: string) {
    restoreSelection();
    document.execCommand(command, false, value);
    editorRef.current?.focus();
  }

  function applyFontFamily(family: string) {
    setFontFamily(family);
    exec('fontName', family);
  }

  function applyFontSize(size: number) {
    setFontSize(size);
    // execCommand fontSize only supports 1-7, so we use a workaround
    restoreSelection();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (range.collapsed) {
      // cursor only - set style on a marker span
      const span = document.createElement('span');
      span.style.fontSize = `${size}px`;
      span.style.fontFamily = fontFamily;
      span.appendChild(document.createTextNode('\u200B')); // zero-width space
      range.insertNode(span);
      range.setStartAfter(span);
      range.collapse(true);
      sel.removeAllRanges();
      sel.addRange(range);
    } else {
      document.execCommand('fontSize', false, '7');
      editorRef.current?.querySelectorAll('font[size="7"]').forEach((el) => {
        (el as HTMLElement).removeAttribute('size');
        (el as HTMLElement).style.fontSize = `${size}px`;
      });
    }
    editorRef.current?.focus();
  }

  function applyCase(option: string) {
    restoreSelection();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    const text = range.toString();
    if (!text) return;
    let transformed = text;
    if (option === 'lowercase') transformed = text.toLowerCase();
    else if (option === 'UPPERCASE') transformed = text.toUpperCase();
    else if (option === 'Capitalize Each Word') transformed = text.replace(/\b\w/g, (c) => c.toUpperCase());
    else if (option === 'Sentence case') transformed = text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
    else if (option === 'tOGGLE cASE') transformed = text.split('').map((c) => c === c.toUpperCase() ? c.toLowerCase() : c.toUpperCase()).join('');
    document.execCommand('insertText', false, transformed);
    setShowCaseMenu(false);
    editorRef.current?.focus();
  }

  function applyFontColor(color: string) {
    setFontColor(color);
    exec('foreColor', color);
  }

  function applyBgColor(color: string) {
    setBgColor(color);
    exec('hiliteColor', color);
  }

  function applyLineSpacing(value: string) {
    setLineSpacing(value);
    if (editorRef.current) {
      editorRef.current.style.lineHeight = value;
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const html = e.clipboardData.getData('text/html');
    const text = e.clipboardData.getData('text/plain');
    if (html) {
      document.execCommand('insertHTML', false, html);
    } else {
      document.execCommand('insertText', false, text);
    }
  }

  // Handle image paste
  function handlePasteImage(e: React.ClipboardEvent) {
    const items = e.clipboardData.items;
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (!file) continue;
        const reader = new FileReader();
        reader.onload = (ev) => {
          if (ev.target?.result) {
            restoreSelection();
            document.execCommand('insertImage', false, ev.target.result as string);
          }
        };
        reader.readAsDataURL(file);
        e.preventDefault();
        return;
      }
    }
    handlePaste(e);
  }

  function insertImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) {
        restoreSelection();
        document.execCommand('insertImage', false, ev.target.result as string);
        editorRef.current?.focus();
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  }

  const THEME_COLORS = [
    '#ffffff','#000000','#1f497d','#c0504d','#9bbb59','#f79646','#4bacc6','#8064a2',
    '#c6d9f1','#dbe5f1','#f2dcdb','#ebf1dd','#fdeada','#daeef3','#e5e0ec',
    '#c4bd97','#938953','#494429','#17375e','#366092','#953734','#76923c',
    '#e36c09','#31849b','#604a7b',
  ];

  const STANDARD_COLORS = [
    '#c00000','#ff0000','#ffc000','#ffff00','#92d050','#00b050',
    '#00b0f0','#0070c0','#002060','#7030a0',
  ];

  return (
    <div className="blank-editor-wrap">
      {/* Top toolbar */}
      <div className="blank-toolbar" onMouseDown={(e) => { if ((e.target as HTMLElement).closest('button,select,input,label')) e.preventDefault(); }}>
        {/* Row 1 */}
        <div className="blank-toolbar-row">
          {/* Font family */}
          <select
            className="blank-select blank-font-family"
            value={fontFamily}
            onFocus={saveSelection}
            onChange={(e) => applyFontFamily(e.target.value)}
          >
            {FONT_FAMILIES.map((f) => <option key={f}>{f}</option>)}
          </select>

          {/* Font size */}
          <select
            className="blank-select blank-font-size"
            value={fontSize}
            onFocus={saveSelection}
            onChange={(e) => applyFontSize(Number(e.target.value))}
          >
            {FONT_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>

          <div className="blank-divider" />

          {/* B I U S */}
          <button title="Bold (Ctrl+B)" onClick={() => exec('bold')}><b>B</b></button>
          <button title="Italic (Ctrl+I)" onClick={() => exec('italic')}><i>I</i></button>
          <button title="Underline (Ctrl+U)" onClick={() => exec('underline')} style={{ textDecoration: 'underline' }}>U</button>
          <button title="Strikethrough" onClick={() => exec('strikeThrough')} style={{ textDecoration: 'line-through' }}>S</button>
          <button title="Subscript" onClick={() => exec('subscript')}>x<sub>2</sub></button>
          <button title="Superscript" onClick={() => exec('superscript')}>x<sup>2</sup></button>

          <div className="blank-divider" />

          {/* Font color */}
          <div className="blank-color-wrap">
            <button title="Font color" onClick={() => { saveSelection(); setShowColorPicker((v) => !v); setShowBgColorPicker(false); }}>
              A <span className="blank-color-swatch" style={{ background: fontColor }} />
            </button>
            {showColorPicker && (
              <div className="blank-color-popup">
                <div className="blank-color-label">Theme Colors</div>
                <div className="blank-color-grid">
                  {THEME_COLORS.map((c) => <button key={c} className="blank-swatch-btn" style={{ background: c }} onClick={() => { applyFontColor(c); setShowColorPicker(false); }} />)}
                </div>
                <div className="blank-color-label">Standard Colors</div>
                <div className="blank-color-grid">
                  {STANDARD_COLORS.map((c) => <button key={c} className="blank-swatch-btn" style={{ background: c }} onClick={() => { applyFontColor(c); setShowColorPicker(false); }} />)}
                </div>
                <label className="blank-custom-color">More Colors… <input type="color" value={fontColor} onChange={(e) => { applyFontColor(e.target.value); setShowColorPicker(false); }} /></label>
              </div>
            )}
          </div>

          {/* Highlight/bg color */}
          <div className="blank-color-wrap">
            <button title="Text highlight" onClick={() => { saveSelection(); setShowBgColorPicker((v) => !v); setShowColorPicker(false); }}>
              🖌 <span className="blank-color-swatch" style={{ background: bgColor }} />
            </button>
            {showBgColorPicker && (
              <div className="blank-color-popup">
                <div className="blank-color-label">Theme Colors</div>
                <div className="blank-color-grid">
                  {THEME_COLORS.map((c) => <button key={c} className="blank-swatch-btn" style={{ background: c }} onClick={() => { applyBgColor(c); setShowBgColorPicker(false); }} />)}
                </div>
                <div className="blank-color-label">Standard Colors</div>
                <div className="blank-color-grid">
                  {STANDARD_COLORS.map((c) => <button key={c} className="blank-swatch-btn" style={{ background: c }} onClick={() => { applyBgColor(c); setShowBgColorPicker(false); }} />)}
                </div>
                <label className="blank-custom-color">More Colors… <input type="color" value={bgColor} onChange={(e) => { applyBgColor(e.target.value); setShowBgColorPicker(false); }} /></label>
              </div>
            )}
          </div>

          <div className="blank-divider" />

          {/* Case */}
          <div className="blank-color-wrap">
            <button title="Change case" onClick={() => { saveSelection(); setShowCaseMenu((v) => !v); setShowColorPicker(false); setShowBgColorPicker(false); }}>Aa ▾</button>
            {showCaseMenu && (
              <div className="blank-case-menu">
                {CASE_OPTIONS.map((opt) => <button key={opt} onClick={() => applyCase(opt)}>{opt}</button>)}
              </div>
            )}
          </div>

          <div className="blank-divider" />

          {/* Clear formatting */}
          <button title="Clear formatting" onClick={() => exec('removeFormat')}>✕ Clear</button>

          {/* Close button */}
          {onClose && <button className="blank-close-btn" title="Close blank document" onClick={onClose}>✕ Close</button>}
        </div>

        {/* Row 2 */}
        <div className="blank-toolbar-row">
          {/* Lists */}
          <button title="Bullet list" onClick={() => exec('insertUnorderedList')}>☰ Bullets</button>
          <button title="Numbered list" onClick={() => exec('insertOrderedList')}>1. Number</button>
          <button title="Increase indent" onClick={() => exec('indent')}>⇥ Indent</button>
          <button title="Decrease indent" onClick={() => exec('outdent')}>⇤ Outdent</button>

          <div className="blank-divider" />

          {/* Alignment */}
          <button title="Align left" onClick={() => exec('justifyLeft')}>⬛ Left</button>
          <button title="Center" onClick={() => exec('justifyCenter')}>⬜ Center</button>
          <button title="Align right" onClick={() => exec('justifyRight')}>Right ⬛</button>
          <button title="Justify" onClick={() => exec('justifyFull')}>≡ Justify</button>

          <div className="blank-divider" />

          {/* Line spacing */}
          <label className="blank-label">Line spacing
            <select className="blank-select" value={lineSpacing} onFocus={saveSelection} onChange={(e) => applyLineSpacing(e.target.value)}>
              {['1', '1.15', '1.5', '2', '2.5', '3'].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>

          <div className="blank-divider" />

          {/* Insert image */}
          <label className="blank-btn-label" title="Insert image">
            🖼 Image
            <input type="file" accept="image/*" style={{ display: 'none' }} onChange={insertImage} />
          </label>

          {/* Undo / Redo */}
          <button title="Undo (Ctrl+Z)" onClick={() => exec('undo')}>↩ Undo</button>
          <button title="Redo (Ctrl+Y)" onClick={() => exec('redo')}>↪ Redo</button>
        </div>
      </div>

      {/* Page canvas */}
      <div className="blank-page-wrap">
        <div className="blank-paper">
          <div
            ref={editorRef}
            className="blank-editable"
            contentEditable
            suppressContentEditableWarning
            spellCheck
            style={{ fontFamily, fontSize: `${fontSize}px`, lineHeight: lineSpacing }}
            onMouseUp={saveSelection}
            onKeyUp={saveSelection}
            onFocus={saveSelection}
            onPaste={handlePasteImage}
          />
        </div>
      </div>
    </div>
  );
}

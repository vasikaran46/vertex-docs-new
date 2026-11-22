import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, ChevronDown, Highlighter, ImagePlus, Indent, Italic, List,
  ListOrdered, Minus, Outdent, RemoveFormatting, Strikethrough, Subscript, Superscript, Table2, Type, Underline,
} from 'lucide-react';
import {
  BULLET_STYLES, CASE_OPTIONS, FONT_FAMILIES, FONT_SIZES, LINE_SPACINGS, NUMBER_STYLES, PARAGRAPH_GAPS, SYMBOLS,
  type ListStyleOption,
} from './richText';

type Props = {
  fontFamily: string;
  fontSize: number;
  onRemember: () => void;
  onCommand: (command: string, value?: string) => void;
  onFontFamily: (family: string) => void;
  onFontSize: (size: number) => void;
  onBullet: (option: ListStyleOption) => void;
  onNumber: (option: ListStyleOption) => void;
  onLineSpacing: (value: string) => void;
  onParagraphGap: (px: string) => void;
  onCase: (option: string) => void;
  onSymbol: (symbol: string) => void;
  onTable: (rows: number, cols: number) => void;
  onImage: () => void;
  onClear: () => void;
};

function Menu({ id, open, setOpen, label, title, wide, children }: { id: string; open: string | null; setOpen: (id: string | null) => void; label: ReactNode; title: string; wide?: boolean; children: ReactNode }) {
  const isOpen = open === id;
  return (
    <div className="vd-menu-wrap">
      <button type="button" className={`vd-menu-trigger ${isOpen ? 'open' : ''}`} title={title} aria-label={title} aria-haspopup="menu" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : id)}>
        {label}<ChevronDown size={11} />
      </button>
      {isOpen && <div className={`vd-menu ${wide ? 'wide' : ''}`} role="menu">{children}</div>}
    </div>
  );
}

export function EditorToolbar(p: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(null); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  const pick = (fn: () => void) => () => { fn(); setOpen(null); };
  const cmd = (command: string, value?: string) => () => p.onCommand(command, value);
  const [tableRows, setTableRows] = useState(3);
  const [tableCols, setTableCols] = useState(3);

  return (
    <div ref={root} className="word-format-toolbar vd-toolbar" role="toolbar" aria-label="Text formatting"
      onMouseDown={(event) => { if ((event.target as HTMLElement).closest('button')) event.preventDefault(); }}>
      <Menu id="font" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Font family" wide label={<span className="vd-font-label" style={{ fontFamily: p.fontFamily }}>{p.fontFamily}</span>}>
        {FONT_FAMILIES.map((family) => (
          <button type="button" role="menuitem" key={family} className={family === p.fontFamily ? 'on' : ''} style={{ fontFamily: family }} onClick={pick(() => p.onFontFamily(family))}>{family}</button>
        ))}
      </Menu>
      <Menu id="size" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Font size" label={<span className="vd-size-label">{p.fontSize}</span>}>
        {FONT_SIZES.map((size) => <button type="button" role="menuitem" key={size} className={size === p.fontSize ? 'on' : ''} onClick={pick(() => p.onFontSize(size))}>{size}</button>)}
      </Menu>
      <button type="button" title="Bigger text" aria-label="Bigger text" onClick={() => p.onFontSize(Math.min(200, p.fontSize + 2))}><Type size={15} /><sup>+</sup></button>
      <button type="button" title="Smaller text" aria-label="Smaller text" onClick={() => p.onFontSize(Math.max(6, p.fontSize - 2))}><Type size={12} /><sup>−</sup></button>
      <span className="word-toolbar-divider" />
      <button type="button" title="Bold (Ctrl+B)" aria-label="Bold" onClick={cmd('bold')}><Bold size={15} /></button>
      <button type="button" title="Italic (Ctrl+I)" aria-label="Italic" onClick={cmd('italic')}><Italic size={15} /></button>
      <button type="button" title="Underline (Ctrl+U)" aria-label="Underline" onClick={cmd('underline')}><Underline size={15} /></button>
      <button type="button" title="Strikethrough" aria-label="Strikethrough" onClick={cmd('strikeThrough')}><Strikethrough size={15} /></button>
      <button type="button" title="Subscript" aria-label="Subscript" onClick={cmd('subscript')}><Subscript size={15} /></button>
      <button type="button" title="Superscript" aria-label="Superscript" onClick={cmd('superscript')}><Superscript size={15} /></button>
      <label className="word-color-control" title="Font colour" aria-label="Font colour"><span>A</span><input type="color" defaultValue="#252b38" onFocus={p.onRemember} onChange={(event) => p.onCommand('foreColor', event.target.value)} /></label>
      <label className="word-color-control highlight-control" title="Text highlight" aria-label="Text highlight"><Highlighter size={15} /><input type="color" defaultValue="#fff2a1" onFocus={p.onRemember} onChange={(event) => p.onCommand('hiliteColor', event.target.value)} /></label>
      <Menu id="case" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Change case" label={<span>Aa</span>}>
        {CASE_OPTIONS.map((option) => <button type="button" role="menuitem" key={option} onClick={pick(() => p.onCase(option))}>{option}</button>)}
      </Menu>
      <span className="word-toolbar-divider" />
      <button type="button" title="Align left" aria-label="Align left" onClick={cmd('justifyLeft')}><AlignLeft size={15} /></button>
      <button type="button" title="Centre" aria-label="Centre" onClick={cmd('justifyCenter')}><AlignCenter size={15} /></button>
      <button type="button" title="Align right" aria-label="Align right" onClick={cmd('justifyRight')}><AlignRight size={15} /></button>
      <button type="button" title="Justify" aria-label="Justify" onClick={cmd('justifyFull')}><AlignJustify size={15} /></button>
      <span className="word-toolbar-divider" />
      <Menu id="bullets" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Bullet style" wide label={<List size={15} />}>
        <div className="vd-menu-grid">
          {BULLET_STYLES.map((option) => <button type="button" role="menuitem" key={option.id} title={option.label} aria-label={`Bullets: ${option.label}`} onClick={pick(() => p.onBullet(option))}><b>{option.sample}</b><small>{option.label}</small></button>)}
        </div>
      </Menu>
      <Menu id="numbers" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Numbering style" wide label={<ListOrdered size={15} />}>
        <div className="vd-menu-grid">
          {NUMBER_STYLES.map((option) => <button type="button" role="menuitem" key={option.id} title={option.label} aria-label={`Numbering: ${option.label}`} onClick={pick(() => p.onNumber(option))}><b>{option.sample}</b><small>{option.label}</small></button>)}
        </div>
      </Menu>
      <Menu id="spacing" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Line and paragraph spacing" label={<span className="vd-spacing-label">↕</span>}>
        <div className="vd-menu-head">Line spacing</div>
        {LINE_SPACINGS.map((value) => <button type="button" role="menuitem" key={value} onClick={pick(() => p.onLineSpacing(value))}>{value}</button>)}
        <div className="vd-menu-head">Space after paragraph</div>
        {PARAGRAPH_GAPS.map(([px, name]) => <button type="button" role="menuitem" key={px} onClick={pick(() => p.onParagraphGap(px))}>{name}</button>)}
      </Menu>
      <button type="button" title="Decrease indent" aria-label="Decrease indent" onClick={cmd('outdent')}><Outdent size={15} /></button>
      <button type="button" title="Increase indent" aria-label="Increase indent" onClick={cmd('indent')}><Indent size={15} /></button>
      <span className="word-toolbar-divider" />
      <Menu id="block" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Paragraph style" label={<span>Style</span>}>
        {([['div', 'Normal'], ['h1', 'Heading 1'], ['h2', 'Heading 2'], ['h3', 'Heading 3'], ['blockquote', 'Quote']] as const).map(([tag, name]) => (
          <button type="button" role="menuitem" key={tag} onClick={pick(() => p.onCommand('formatBlock', tag))}>{name}</button>
        ))}
      </Menu>
      <Menu id="symbols" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Insert symbol" wide label={<span>Ω</span>}>
        <div className="vd-symbol-grid">{SYMBOLS.map((symbol) => <button type="button" role="menuitem" key={symbol} aria-label={`Insert ${symbol}`} onClick={pick(() => p.onSymbol(symbol))}>{symbol}</button>)}</div>
      </Menu>
      <Menu id="table" open={open} setOpen={(v) => { p.onRemember(); setOpen(v); }} title="Insert table" label={<Table2 size={15} />}>
        <div className="vd-table-picker" onMouseDown={(event) => event.stopPropagation()}>
          <label>Rows <input type="number" min={1} max={12} value={tableRows} onChange={(event) => setTableRows(Math.max(1, Math.min(12, Number(event.target.value) || 1)))} /></label>
          <label>Columns <input type="number" min={1} max={8} value={tableCols} onChange={(event) => setTableCols(Math.max(1, Math.min(8, Number(event.target.value) || 1)))} /></label>
          <button type="button" className="vd-menu-action" onClick={pick(() => p.onTable(tableRows, tableCols))}>Insert table</button>
        </div>
      </Menu>
      <button type="button" title="Horizontal line" aria-label="Horizontal line" onClick={cmd('insertHorizontalRule')}><Minus size={15} /></button>
      <button type="button" title="Insert image" aria-label="Insert image" onClick={p.onImage}><ImagePlus size={15} /></button>
      <button type="button" title="Clear formatting" aria-label="Clear formatting" onClick={p.onClear}><RemoveFormatting size={15} /></button>
    </div>
  );
}

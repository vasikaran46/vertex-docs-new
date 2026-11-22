// Shared helpers for the PDF Studio page editor (on-screen editing AND the export renderer).

export const FONT_FAMILIES = [
  'Arial', 'Arial Black', 'Calibri', 'Cambria', 'Candara', 'Century Gothic', 'Comic Sans MS', 'Consolas',
  'Courier New', 'Franklin Gothic Medium', 'Garamond', 'Georgia', 'Gill Sans MT', 'Helvetica', 'Impact',
  'Lucida Console', 'Lucida Sans Unicode', 'Palatino Linotype', 'Rockwell', 'Segoe UI', 'Tahoma',
  'Times New Roman', 'Trebuchet MS', 'Verdana', 'Book Antiqua', 'Bookman Old Style', 'Brush Script MT',
  'Copperplate Gothic', 'Perpetua', 'Baskerville', 'Nirmala UI', 'Latha', 'serif', 'sans-serif', 'monospace', 'cursive',
];
export const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 48, 60, 72, 96];

export type ListStyleOption = { id: string; label: string; sample: string; value: string };

// CSS <string> list-style-type values give ticks, stars, arrows... without images.
export const BULLET_STYLES: ListStyleOption[] = [
  { id: 'disc', label: 'Solid dot', sample: '•', value: 'disc' },
  { id: 'circle', label: 'Hollow circle', sample: '○', value: 'circle' },
  { id: 'square', label: 'Square', sample: '▪', value: 'square' },
  { id: 'tick', label: 'Tick mark', sample: '✓', value: '"✓  "' },
  { id: 'heavy-tick', label: 'Bold tick', sample: '✔', value: '"✔  "' },
  { id: 'cross', label: 'Cross', sample: '✗', value: '"✗  "' },
  { id: 'star', label: 'Star', sample: '★', value: '"★  "' },
  { id: 'star-o', label: 'Hollow star', sample: '☆', value: '"☆  "' },
  { id: 'arrow', label: 'Arrow', sample: '➤', value: '"➤  "' },
  { id: 'arrow-r', label: 'Right arrow', sample: '→', value: '"→  "' },
  { id: 'chevron', label: 'Double chevron', sample: '»', value: '"»  "' },
  { id: 'diamond', label: 'Diamond', sample: '◆', value: '"◆  "' },
  { id: 'filled-circle', label: 'Big circle', sample: '●', value: '"●  "' },
  { id: 'bullseye', label: 'Target', sample: '◉', value: '"◉  "' },
  { id: 'checkbox', label: 'Checkbox', sample: '☐', value: '"☐  "' },
  { id: 'checked', label: 'Checked box', sample: '☑', value: '"☑  "' },
  { id: 'dash', label: 'Dash', sample: '–', value: '"–  "' },
  { id: 'plus', label: 'Plus', sample: '+', value: '"+  "' },
  { id: 'heart', label: 'Heart', sample: '♥', value: '"♥  "' },
  { id: 'pointer', label: 'Pointing hand', sample: '☞', value: '"☞  "' },
  { id: 'flower', label: 'Flower', sample: '❀', value: '"❀  "' },
  { id: 'none', label: 'No bullet', sample: '∅', value: 'none' },
];

export const NUMBER_STYLES: ListStyleOption[] = [
  { id: 'decimal', label: '1. 2. 3.', sample: '1.', value: 'decimal' },
  { id: 'paren', label: '1) 2) 3)', sample: '1)', value: 'vd-paren-decimal' },
  { id: 'zero', label: '01. 02. 03.', sample: '01.', value: 'decimal-leading-zero' },
  { id: 'lower-alpha', label: 'a. b. c.', sample: 'a.', value: 'lower-alpha' },
  { id: 'upper-alpha', label: 'A. B. C.', sample: 'A.', value: 'upper-alpha' },
  { id: 'paren-alpha', label: 'a) b) c)', sample: 'a)', value: 'vd-paren-alpha' },
  { id: 'lower-roman', label: 'i. ii. iii.', sample: 'i.', value: 'lower-roman' },
  { id: 'upper-roman', label: 'I. II. III.', sample: 'I.', value: 'upper-roman' },
  { id: 'paren-roman', label: 'i) ii) iii)', sample: 'i)', value: 'vd-paren-roman' },
  { id: 'greek', label: 'α. β. γ.', sample: 'α.', value: 'lower-greek' },
  { id: 'tamil', label: 'Tamil ௧ ௨ ௩', sample: '௧.', value: 'tamil' },
  { id: 'devanagari', label: 'Hindi १ २ ३', sample: '१.', value: 'devanagari' },
];

export const LINE_SPACINGS = ['1', '1.15', '1.5', '1.8', '2', '2.5', '3'];
export const PARAGRAPH_GAPS: [string, string][] = [['0', 'None'], ['4', 'Small'], ['8', 'Medium'], ['14', 'Large'], ['24', 'Extra large']];
export const SYMBOLS = ['✓', '✔', '✗', '★', '☆', '→', '←', '↑', '↓', '⇒', '•', '©', '®', '™', '€', '₹', '£', '¥', '§', '¶', '°', '±', '×', '÷', '≈', '≠', '≤', '≥', '∞', '♥', '☎', '✉', '●', '■', '▲', '◆'];
export const CASE_OPTIONS = ['Sentence case', 'lowercase', 'UPPERCASE', 'Capitalize Each Word', 'tOGGLE cASE'];

// Same rules are injected on screen and into the export renderer, so the PDF matches what you see.
export const EDITOR_CSS = `
@counter-style vd-paren-decimal { system: extends decimal; suffix: ") "; }
@counter-style vd-paren-alpha { system: extends lower-alpha; suffix: ") "; }
@counter-style vd-paren-roman { system: extends lower-roman; suffix: ") "; }
.vd-rich ul, .vd-rich ol { margin: 0 0 .5em; padding-left: 2em; }
.vd-rich p, .vd-rich div { margin: 0; }
.vd-rich h1 { font-size: 2em; margin: .3em 0; } .vd-rich h2 { font-size: 1.5em; margin: .3em 0; } .vd-rich h3 { font-size: 1.2em; margin: .3em 0; }
.vd-rich blockquote { margin: .4em 0 .4em 1em; padding-left: .8em; border-left: 3px solid #9aa; color: #444; }
.vd-rich table { border-collapse: collapse; margin: .4em 0; } .vd-rich td { border: 1px solid #888; padding: 6px 10px; min-width: 40px; }
.vd-rich hr { border: 0; border-top: 1px solid #888; margin: .6em 0; }
`;

export function ensureBlocks(editor: HTMLElement) {
  if (!editor.firstChild) { editor.innerHTML = '<div><br></div>'; return; }
  const loose: ChildNode[] = [];
  const flush = (before: ChildNode | null) => {
    if (!loose.length) return;
    const wrapper = document.createElement('div');
    editor.insertBefore(wrapper, before);
    loose.forEach((node) => wrapper.appendChild(node));
    loose.length = 0;
  };
  Array.from(editor.childNodes).forEach((node) => {
    const isBlock = node instanceof HTMLElement && /^(DIV|P|UL|OL|H[1-6]|BLOCKQUOTE|TABLE|HR|PRE)$/.test(node.tagName);
    if (isBlock) flush(node); else loose.push(node);
  });
  flush(null);
}

export function blocksInRange(editor: HTMLElement, range: Range | null): HTMLElement[] {
  ensureBlocks(editor);
  const blocks = Array.from(editor.children).filter((child): child is HTMLElement => child instanceof HTMLElement);
  if (!range) return blocks;
  const hit = blocks.filter((block) => range.intersectsNode(block));
  return hit.length ? hit : blocks.slice(-1);
}

export function closestList(editor: HTMLElement, node: Node | null): HTMLUListElement | HTMLOListElement | null {
  let current: Node | null = node;
  while (current && current !== editor) {
    if (current instanceof HTMLUListElement || current instanceof HTMLOListElement) return current;
    current = current.parentNode;
  }
  return null;
}

function lineBlock(editor: HTMLElement, node: Node | null): HTMLElement | null {
  let current: Node | null = node;
  while (current && current !== editor) {
    if (current instanceof HTMLElement && (current.parentElement === editor || current.tagName === 'LI')) return current;
    current = current.parentNode;
  }
  return null;
}

function charOffsetInBlock(block: HTMLElement, selection: Selection): number {
  const range = document.createRange();
  range.selectNodeContents(block);
  range.setEnd(selection.anchorNode as Node, selection.anchorOffset);
  return range.toString().length;
}

function placeCaretAtChar(block: HTMLElement, offset: number) {
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  let remaining = offset;
  let node = walker.nextNode();
  while (node) {
    const length = node.textContent?.length ?? 0;
    if (remaining <= length) { window.getSelection()?.collapse(node, remaining); return; }
    remaining -= length;
    node = walker.nextNode();
  }
  const range = document.createRange();
  range.selectNodeContents(block);
  range.collapse(false);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}

export function applyListStyle(editor: HTMLElement, ordered: boolean, option: ListStyleOption) {
  const selection = window.getSelection();
  let list = closestList(editor, selection?.anchorNode ?? null);
  if (option.value === 'none' && !ordered) {
    if (list) document.execCommand(list instanceof HTMLOListElement ? 'insertOrderedList' : 'insertUnorderedList');
    return;
  }
  if (!list || (list instanceof HTMLOListElement) !== ordered) {
    // Chrome moves the caret to the start of the line when it becomes a list item; put it back.
    let offset = -1;
    if (selection?.isCollapsed && selection.anchorNode) {
      const block = lineBlock(editor, selection.anchorNode);
      if (block) offset = charOffsetInBlock(block, selection);
    }
    document.execCommand(ordered ? 'insertOrderedList' : 'insertUnorderedList');
    const after = window.getSelection();
    list = closestList(editor, after?.anchorNode ?? null);
    if (offset >= 0 && after?.anchorNode) {
      const block = lineBlock(editor, after.anchorNode);
      if (block) placeCaretAtChar(block, offset);
    }
  }
  if (list) list.style.listStyleType = option.value;
}

export function applyBlockCss(editor: HTMLElement, range: Range | null, css: Partial<CSSStyleDeclaration>) {
  blocksInRange(editor, range).forEach((block) => Object.assign(block.style, css));
}

export function transformCase(text: string, option: string) {
  switch (option) {
    case 'lowercase': return text.toLowerCase();
    case 'UPPERCASE': return text.toUpperCase();
    case 'Capitalize Each Word': return text.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
    case 'Sentence case': return text.toLowerCase().replace(/(^\s*|[.!?]\s+)([a-z])/g, (_m, a, b) => a + b.toUpperCase());
    case 'tOGGLE cASE': return text.split('').map((c) => (c === c.toUpperCase() ? c.toLowerCase() : c.toUpperCase())).join('');
    default: return text;
  }
}

export function tableHtml(rows: number, cols: number) {
  const cell = '<td style="border:1px solid #888;padding:6px 10px;min-width:40px">&nbsp;</td>';
  return `<table style="border-collapse:collapse;margin:6px 0">${`<tr>${cell.repeat(cols)}</tr>`.repeat(rows)}</table><div><br></div>`;
}

/**
 * "Click and type anywhere": clicking in blank space below the last line (or to the right of an empty line)
 * adds the lines/indent needed to reach that spot and puts the caret there.
 * Returns true when it handled the click (caller should preventDefault).
 */
export function clickAndType(editor: HTMLElement, clientX: number, clientY: number): boolean {
  ensureBlocks(editor);
  const rect = editor.getBoundingClientRect();
  const style = getComputedStyle(editor);
  const padLeft = parseFloat(style.paddingLeft) || 0;
  const padRight = parseFloat(style.paddingRight) || 0;
  const maxIndent = Math.max(0, rect.width - padLeft - padRight - 40);
  const indent = Math.min(maxIndent, Math.max(0, clientX - rect.left - padLeft));
  const blocks = Array.from(editor.children).filter((c): c is HTMLElement => c instanceof HTMLElement);
  const last = blocks[blocks.length - 1];
  const lastBottom = last ? last.getBoundingClientRect().bottom : rect.top;
  const baseLine = parseFloat(getComputedStyle(last ?? editor).lineHeight) || parseFloat(style.fontSize) * 1.65 || 23;

  const place = (block: HTMLElement) => {
    const range = document.createRange();
    range.selectNodeContents(block);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    editor.focus();
  };
  const isEmpty = (block: HTMLElement) => !block.textContent?.trim() && !block.querySelector('img,table,hr');

  if (clientY > lastBottom + 2) {
    const lines = Math.max(0, Math.floor((clientY - lastBottom) / baseLine));
    let target = last;
    // reuse a trailing empty line, otherwise start a fresh one
    const needNew = !last || !isEmpty(last) ? lines + 1 : lines;
    for (let i = 0; i < needNew; i++) {
      target = document.createElement('div');
      target.innerHTML = '<br>';
      editor.appendChild(target);
    }
    if (target && indent > 12) target.style.marginLeft = `${Math.round(indent)}px`;
    if (target) place(target);
    return true;
  }
  // Click inside an empty line: honour the horizontal position.
  const hit = blocks.find((b) => { const r = b.getBoundingClientRect(); return clientY >= r.top && clientY <= r.bottom; });
  if (hit && isEmpty(hit)) {
    hit.style.marginLeft = indent > 12 ? `${Math.round(indent)}px` : '';
    place(hit);
    return true;
  }
  return false;
}

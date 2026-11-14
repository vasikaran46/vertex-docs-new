import { PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlignCenter, AlignLeft, AlignRight, ArrowLeftRight, Bell, Check, ChevronDown, CircleAlert, Combine,
  Crop, Download, Eraser, FilePlus2, FileSearch, FileText, Highlighter, ImagePlus, Languages, LayoutDashboard, LogOut,
  Menu, Moon, Search, Send, Settings2, ShieldCheck, Sparkles,
  Sun, Trash2, UploadCloud, X, Scissors, RotateCw, LockKeyhole, Pencil, Pen, Redo2, Save, Undo2,
  Mic, Volume2, BookOpen, MessageCircle, ArrowDownToLine, RefreshCw, UserRound,
} from 'lucide-react';
import { companions, conversionTools, groups, languages, palettes, tools, type ConversionTool } from './catalogue';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type PaletteId = (typeof palettes)[number]['id'];
type ThemeName = `${PaletteId}-${'light' | 'dark'}`;
type TemplateAccent = 'forest' | 'rose' | 'graphite' | 'cocoa' | 'amber' | 'ocean';
type EditorTool = 'text' | 'highlight' | 'pen' | 'pencil' | 'eraser';
type ExportFormat = 'pdf' | 'docx' | 'txt';
type ImagePosition = { x: number; y: number };
type User = {
  id: number;
  name: string;
  email: string;
  theme: string;
  language: string;
  avatar: string;
};
type DocumentItem = { id: number; name: string; size: number };
type RecentUpload = { document: DocumentItem; file: File };
type ProcessedPdf = { file: File; url: string };
type EditorSnapshot = { text: string; drawing: string; hasDrawing: boolean };
type ScanPage = { id: string; file: File; preview: string; rotation: number };
type ChatMessage = { role: 'user' | 'assistant'; text: string };
type ChatConversation = { id: number; title: string; updated_at: string };
type PageName =
  | 'Home / Workspace'
  | 'PDF Studio'
  | 'Convert'
  | 'Language Bridge'
  | 'AI Documents'
  | 'Templates'
  | 'Document History'
  | 'Account / Privacy'
  | 'Companion & Themes';
type PdfAction =
  | 'info'
  | 'merge'
  | 'split'
  | 'rotate'
  | 'remove-pages'
  | 'extract-pages'
  | 'organize'
  | 'protect'
  | 'unlock'
  | 'text'
  | 'compress'
  | 'flip';
type AdvancedToolField = {
  key: string;
  label: string;
  type?: 'text' | 'number' | 'textarea' | 'select';
  placeholder?: string;
  defaultValue?: string;
  options?: string[];
};
type AdvancedToolConfig = {
  slug?: string;
  description: string;
  fields?: AdvancedToolField[];
  fileCount?: 1 | 2;
  additionalImage?: boolean;
  mode?: 'ai' | 'provider-required';
};
type TemplateKind = 'resume' | 'cover-letter' | 'business-letter' | 'meeting-notes' | 'project-proposal' | 'invoice';
type TemplateFieldName = 'full_name' | 'title' | 'email' | 'phone' | 'location' | 'website' | 'recipient' | 'company' | 'date' | 'subject' | 'summary' | 'experience' | 'education' | 'skills' | 'body';
type TemplateDraft = Record<TemplateFieldName, string>;
type SpeechResultLike = ArrayLike<{ transcript: string }>;
type SpeechRecognitionEventLike = Event & { results: ArrayLike<SpeechResultLike> };
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: Event & { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const speechLocales: Record<string, string> = {
  en: 'en-US', ta: 'ta-IN', tanglish: 'ta-IN', hi: 'hi-IN', ml: 'ml-IN',
  te: 'te-IN', kn: 'kn-IN', ja: 'ja-JP', de: 'de-DE', sa: 'sa-IN',
  bn: 'bn-IN', fr: 'fr-FR', es: 'es-ES',
};

const templateCatalog: { id: TemplateKind; name: string; category: string; description: string }[] = [
  { id: 'resume', name: 'Resume', category: 'Career', description: 'A clear, polished layout for your experience and skills.' },
  { id: 'cover-letter', name: 'Cover letter', category: 'Career', description: 'Introduce yourself with a focused, professional letter.' },
  { id: 'business-letter', name: 'Business letter', category: 'Letters', description: 'A flexible format for formal workplace communication.' },
  { id: 'meeting-notes', name: 'Meeting notes', category: 'Work', description: 'Keep agendas, decisions, attendees and next steps together.' },
  { id: 'project-proposal', name: 'Project proposal', category: 'Work', description: 'Present an overview, deliverables and project plan.' },
  { id: 'invoice', name: 'Invoice', category: 'Business', description: 'Prepare a neat invoice with billing and item details.' },
];

const templateFields: Record<TemplateKind, { name: TemplateFieldName; label: string; placeholder: string; multiline?: boolean }[]> = {
  resume: [
    { name: 'full_name', label: 'Full name', placeholder: 'Jordan Lee' },
    { name: 'title', label: 'Professional title', placeholder: 'Product Designer' },
    { name: 'email', label: 'Email', placeholder: 'jordan@example.com' },
    { name: 'phone', label: 'Phone', placeholder: '+1 555 0100' },
    { name: 'location', label: 'Location', placeholder: 'City, Country' },
    { name: 'website', label: 'Portfolio or LinkedIn', placeholder: 'linkedin.com/in/yourname' },
    { name: 'summary', label: 'Professional summary', placeholder: 'A short introduction about your strengths…', multiline: true },
    { name: 'experience', label: 'Experience', placeholder: 'Role · Company · Dates\nAdd achievements and impact…', multiline: true },
    { name: 'education', label: 'Education', placeholder: 'Degree · Institution · Year', multiline: true },
    { name: 'skills', label: 'Skills', placeholder: 'Research, Figma, prototyping…', multiline: true },
  ],
  'cover-letter': [
    { name: 'full_name', label: 'Your name', placeholder: 'Jordan Lee' },
    { name: 'email', label: 'Your email', placeholder: 'jordan@example.com' },
    { name: 'date', label: 'Date', placeholder: '12 November 2026' },
    { name: 'recipient', label: 'Recipient', placeholder: 'Hiring Manager' },
    { name: 'company', label: 'Company', placeholder: 'Company name' },
    { name: 'subject', label: 'Position', placeholder: 'Application for Product Designer' },
    { name: 'body', label: 'Letter', placeholder: 'Write your introduction, experience and closing…', multiline: true },
  ],
  'business-letter': [
    { name: 'full_name', label: 'Your name', placeholder: 'Jordan Lee' },
    { name: 'email', label: 'Your email', placeholder: 'jordan@example.com' },
    { name: 'date', label: 'Date', placeholder: '12 November 2026' },
    { name: 'recipient', label: 'Recipient', placeholder: 'Recipient name and address' },
    { name: 'company', label: 'Organization', placeholder: 'Company or organization' },
    { name: 'subject', label: 'Subject', placeholder: 'What is this letter about?' },
    { name: 'body', label: 'Letter', placeholder: 'Write your message…', multiline: true },
  ],
  'meeting-notes': [
    { name: 'title', label: 'Meeting title', placeholder: 'Weekly project check-in' },
    { name: 'date', label: 'Date and time', placeholder: '12 November 2026 · 10:00 AM' },
    { name: 'recipient', label: 'Attendees', placeholder: 'Names separated by commas', multiline: true },
    { name: 'summary', label: 'Agenda', placeholder: 'Topics to discuss…', multiline: true },
    { name: 'body', label: 'Notes and decisions', placeholder: 'Capture the conversation and decisions…', multiline: true },
    { name: 'experience', label: 'Action items', placeholder: 'Owner · Task · Due date…', multiline: true },
  ],
  'project-proposal': [
    { name: 'title', label: 'Project title', placeholder: 'Project proposal' },
    { name: 'company', label: 'Prepared for', placeholder: 'Client or organization' },
    { name: 'summary', label: 'Overview', placeholder: 'Summarize the opportunity and goals…', multiline: true },
    { name: 'body', label: 'Proposal', placeholder: 'Describe the approach, scope and value…', multiline: true },
    { name: 'experience', label: 'Deliverables and timeline', placeholder: 'Milestones, deliverables and dates…', multiline: true },
    { name: 'skills', label: 'Team and capabilities', placeholder: 'People, skills and resources…', multiline: true },
  ],
  invoice: [
    { name: 'title', label: 'Invoice number', placeholder: 'Invoice #001' },
    { name: 'company', label: 'Business name', placeholder: 'Your business' },
    { name: 'full_name', label: 'Bill from', placeholder: 'Your name' },
    { name: 'email', label: 'Email', placeholder: 'billing@example.com' },
    { name: 'location', label: 'Address', placeholder: 'Business address' },
    { name: 'date', label: 'Invoice date and due date', placeholder: 'Issued … · Due …' },
    { name: 'recipient', label: 'Bill to', placeholder: 'Client name and address' },
    { name: 'body', label: 'Items and amounts', placeholder: 'Description — quantity — amount…', multiline: true },
    { name: 'summary', label: 'Notes', placeholder: 'Payment instructions or thank-you note…', multiline: true },
  ],
};

const emptyTemplateDraft: TemplateDraft = {
  full_name: '', title: '', email: '', phone: '', location: '', website: '',
  recipient: '', company: '', date: '', subject: '', summary: '', experience: '',
  education: '', skills: '', body: '',
};

const navItems = [
  { name: 'Home / Workspace' as const, label: 'Home / Workspace', icon: LayoutDashboard },
  { name: 'PDF Studio' as const, label: 'PDF Studio', icon: FileText },
  { name: 'Language Bridge' as const, label: 'Language Bridge', icon: Languages },
  { name: 'Convert' as const, label: 'Convert', icon: ArrowLeftRight },
  { name: 'AI Documents' as const, label: 'AI Documents', icon: Sparkles },
  { name: 'Templates' as const, label: 'Templates', icon: LayerIcon },
  { name: 'Document History' as const, label: 'Document History', icon: FileSearch },
  { name: 'Account / Privacy' as const, label: 'Account / Privacy', icon: ShieldCheck },
  { name: 'Companion & Themes' as const, label: 'Companion & Themes', icon: Settings2 },
];

const pdfActions: { id: PdfAction; name: string; description: string; icon: typeof FileText }[] = [
  { id: 'info', name: 'PDF information', description: 'View page count and metadata.', icon: FileSearch },
  { id: 'merge', name: 'Merge PDF', description: 'Combine multiple PDF files.', icon: Combine },
  { id: 'split', name: 'Split pages', description: 'Create a PDF from selected pages.', icon: Scissors },
  { id: 'rotate', name: 'Rotate pages', description: 'Rotate every page by 90°, 180° or 270°.', icon: RotateCw },
  { id: 'remove-pages', name: 'Remove pages', description: 'Remove selected pages from a PDF.', icon: Trash2 },
  { id: 'extract-pages', name: 'Extract pages', description: 'Keep only the selected pages.', icon: FileText },
  { id: 'organize', name: 'Organize PDF', description: 'Reorder, rotate, or remove individual pages.', icon: FilePlus2 },
  { id: 'protect', name: 'Protect PDF', description: 'Add a password to a PDF.', icon: LockKeyhole },
  { id: 'unlock', name: 'Unlock PDF', description: 'Remove a password you know.', icon: LockKeyhole },
  { id: 'text', name: 'Extract text', description: 'Read extractable text from a PDF.', icon: FileSearch },
  { id: 'compress', name: 'Compress PDF', description: 'Set a maximum size in KB or MB and keep text searchable unless you choose page rasterization.', icon: Download },
  { id: 'flip', name: 'Flip PDF', description: 'Flip every page horizontally or vertically.', icon: RefreshCw },
];

const advancedToolConfigs: Record<string, AdvancedToolConfig> = {
  'add page numbers': { slug: 'add-page-numbers', description: 'Stamp sequential page numbers onto the bottom-right of every page.', fields: [{ key: 'start', label: 'Start number', type: 'number', defaultValue: '1' }] },
  'add watermark': { slug: 'add-watermark', description: 'Add a translucent, rotated text watermark to every page.', fields: [{ key: 'text', label: 'Watermark text', placeholder: 'CONFIDENTIAL' }, { key: 'angle', label: 'Angle in degrees', type: 'number', defaultValue: '45' }, { key: 'font_size', label: 'Font size', type: 'number', defaultValue: '24' }] },
  'crop pdf': { slug: 'crop-pdf', description: 'Set page crop margins as percentages of each page size.', fields: [{ key: 'margin_top', label: 'Crop top (%)', type: 'number', defaultValue: '0' }, { key: 'margin_right', label: 'Crop right (%)', type: 'number', defaultValue: '0' }, { key: 'margin_bottom', label: 'Crop bottom (%)', type: 'number', defaultValue: '0' }, { key: 'margin_left', label: 'Crop left (%)', type: 'number', defaultValue: '0' }] },
  'pdf forms': { slug: 'pdf-forms', description: 'Fill existing AcroForm fields using a JSON object of field names and values.', fields: [{ key: 'values', label: 'Field values · JSON', type: 'textarea', placeholder: '{"Full name":"Alex Smith"}' }] },
  'sign pdf': { slug: 'sign-pdf', description: 'Place a typed signature or upload a transparent signature image on a chosen page.', additionalImage: true, fields: [{ key: 'signature', label: 'Typed signature', placeholder: 'Your name' }, { key: 'page', label: 'Page number', type: 'number', defaultValue: '1' }, { key: 'x', label: 'Position from left (%)', type: 'number', defaultValue: '70' }, { key: 'y', label: 'Position from top (%)', type: 'number', defaultValue: '85' }] },
  'compare pdf': { slug: 'compare-pdf', description: 'Compare extractable text page by page and show a readable change report.', fileCount: 2 },
  'repair pdf': { slug: 'repair-pdf', description: 'Rebuild and normalize a readable PDF structure. This cannot recover missing/corrupt page content.' },
  'alternate and mix pdf': { slug: 'alternate-and-mix-pdf', description: 'Interleave pages from two PDFs, starting with the first selected file.', fileCount: 2 },
  'split by bookmarks': { slug: 'split-by-bookmarks', description: 'Create a ZIP of PDFs split at top-level bookmarks.' },
  'split by half': { slug: 'split-by-half', description: 'Split pages into two PDFs, then download them together as a ZIP.' },
  'split by size': { slug: 'split-by-size', description: 'Create a ZIP of page groups no larger than the selected approximate output size.', fields: [{ key: 'max_size_mb', label: 'Maximum part size (MB)', type: 'number', defaultValue: '5' }] },
  'split by text': { slug: 'split-by-text', description: 'Start a new PDF part on each page containing the chosen text.', fields: [{ key: 'text', label: 'Text to split at', placeholder: 'Chapter' }] },
  'flatten pdf': { slug: 'flatten-pdf', description: 'Flatten each page to an image. Output text is no longer searchable or editable.', fields: [{ key: 'dpi', label: 'Render quality (DPI)', type: 'number', defaultValue: '144' }] },
  'bates numbering': { slug: 'bates-numbering', description: 'Stamp sequential Bates identifiers on each page.', fields: [{ key: 'prefix', label: 'Prefix', placeholder: 'CASE-' }, { key: 'start', label: 'Starting number', type: 'number', defaultValue: '1' }, { key: 'digits', label: 'Number of digits', type: 'number', defaultValue: '6' }] },
  'create bookmarks': { slug: 'create-bookmarks', description: 'Add PDF bookmarks. Enter one title:page pair per line.', fields: [{ key: 'bookmarks', label: 'Bookmarks', type: 'textarea', placeholder: 'Introduction:1\nAppendix:12' }] },
  'edit metadata': { slug: 'edit-metadata', description: 'Update PDF metadata fields using JSON. Allowed fields: title, author, subject, keywords, creator.', fields: [{ key: 'metadata', label: 'Metadata · JSON', type: 'textarea', placeholder: '{"title":"Project report","author":"Alex"}' }] },
  'extract images': { slug: 'extract-images', description: 'Extract embedded images into a ZIP archive, named by page and image number.' },
  'flip pdf': { slug: 'flip-pdf', description: 'Mirror every page while preserving searchable text.', fields: [{ key: 'direction', label: 'Direction', type: 'select', defaultValue: 'horizontal', options: ['horizontal', 'vertical'] }] },
  'grayscale pdf': { slug: 'grayscale-pdf', description: 'Convert each page to grayscale images. Output text is no longer searchable.', fields: [{ key: 'dpi', label: 'Render quality (DPI)', type: 'number', defaultValue: '144' }] },
  'header and footer': { slug: 'header-and-footer', description: 'Stamp text at the top and/or bottom of every page.', fields: [{ key: 'header', label: 'Header text', placeholder: 'Document title' }, { key: 'footer', label: 'Footer text', placeholder: 'Internal use only' }, { key: 'font_size', label: 'Font size', type: 'number', defaultValue: '10' }] },
  'n-up pdf': { slug: 'n-up-pdf', description: 'Place 2-9 pages on each sheet in reading order.', fields: [{ key: 'pages_per_sheet', label: 'Pages per sheet', type: 'number', defaultValue: '4' }] },
  'rename pdf': { slug: 'rename-pdf', description: 'Change the downloaded PDF filename without modifying its content.', fields: [{ key: 'filename', label: 'New filename', defaultValue: 'document.pdf' }] },
  'resize pdf': { slug: 'resize-pdf', description: 'Scale each page to a standard paper size while preserving proportions.', fields: [{ key: 'paper', label: 'Paper size', type: 'select', defaultValue: 'A4', options: ['A4', 'A3', 'Letter', 'Legal'] }] },
  'remove annotations': { slug: 'remove-annotations', description: 'Remove PDF annotations and comments from all pages.' },
  'deskew pdf': { slug: 'deskew-pdf', description: 'Estimate and correct small scan rotations. Pages are rasterized and text is no longer searchable.', fields: [{ key: 'dpi', label: 'Render quality (DPI)', type: 'number', defaultValue: '144' }] },
  'ocr pdf': { mode: 'provider-required', description: 'OCR provider endpoint and credentials are not configured. Configure the selected OCR API before enabling this operation.' },
  'request signature': { mode: 'provider-required', description: 'Email/e-sign provider details are not configured. Configure a provider before sending signature requests.' },
  'ai question generator': { mode: 'ai', description: 'Generate study questions and an answer key from an uploaded PDF, DOCX, TXT, or Markdown file.', fields: [{ key: 'count', label: 'Question count', type: 'number', defaultValue: '5' }, { key: 'language', label: 'Language', type: 'select', defaultValue: 'en', options: ['en', 'ta', 'hi', 'ml', 'te', 'kn', 'ja', 'de', 'sa', 'bn', 'fr', 'es', 'tanglish'] }] },
};

function LayerIcon({ size = 20 }: { size?: number }) {
  return <span aria-hidden="true" className="layers-icon" style={{ width: size, height: size }}>▦</span>;
}

function themeFrom(value: string | null | undefined): ThemeName {
  if (palettes.some((palette) => value === `${palette.id}-light` || value === `${palette.id}-dark`)) return value as ThemeName;
  const legacyThemes: Record<string, ThemeName> = {
    light: 'forest-light',
    dark: 'graphite-dark',
    forest: 'forest-light',
    rose: 'rose-light',
    graphite: 'graphite-light',
    cocoa: 'cocoa-light',
    amber: 'amber-light',
    ocean: 'ocean-light',
    porcelain: 'graphite-light',
    mint: 'forest-light',
    sage: 'forest-light',
    sand: 'cocoa-light',
  };
  if (value && legacyThemes[value]) return legacyThemes[value];
  return 'forest-light';
}

function companionFrom(value: string | null | undefined) {
  return companions.find((companion) => companion.id === value)
    ?? companions.find((companion) => companion.id === 'pip')
    ?? companions[0];
}

async function responseError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.message || `Request failed (${response.status})`;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function readImageData(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('Could not read the image.'));
    reader.onerror = () => reject(new Error('Could not read the image.'));
    reader.readAsDataURL(file);
  });
}

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Could not process this image.'));
    image.src = source;
  });
}

async function cropAndRotateImage(source: string, rotation: number, cropLeft: number, cropRight: number, cropTop: number, cropBottom: number) {
  const image = await loadImage(source);
  const shrink = Math.min(1, 2400 / Math.max(image.naturalWidth, image.naturalHeight));
  const sourceWidth = Math.max(1, Math.round(image.naturalWidth * shrink));
  const sourceHeight = Math.max(1, Math.round(image.naturalHeight * shrink));
  const sideways = rotation % 180 !== 0;
  const rotated = document.createElement('canvas');
  rotated.width = sideways ? sourceHeight : sourceWidth;
  rotated.height = sideways ? sourceWidth : sourceHeight;
  const rotatedContext = rotated.getContext('2d');
  if (!rotatedContext) throw new Error('Image editing is not available in this browser.');
  rotatedContext.translate(rotated.width / 2, rotated.height / 2);
  rotatedContext.rotate(rotation * Math.PI / 180);
  rotatedContext.drawImage(image, -sourceWidth / 2, -sourceHeight / 2, sourceWidth, sourceHeight);

  const left = Math.round(rotated.width * cropLeft / 100);
  const right = Math.round(rotated.width * cropRight / 100);
  const top = Math.round(rotated.height * cropTop / 100);
  const bottom = Math.round(rotated.height * cropBottom / 100);
  const cropWidth = Math.max(1, rotated.width - left - right);
  const cropHeight = Math.max(1, rotated.height - top - bottom);
  const cropped = document.createElement('canvas');
  cropped.width = cropWidth;
  cropped.height = cropHeight;
  const croppedContext = cropped.getContext('2d');
  if (!croppedContext) throw new Error('Image editing is not available in this browser.');
  croppedContext.fillStyle = '#fff';
  croppedContext.fillRect(0, 0, cropWidth, cropHeight);
  croppedContext.drawImage(rotated, left, top, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
  return cropped.toDataURL('image/png');
}

function drawEditorText(context: CanvasRenderingContext2D, width: number, height: number, text: string) {
  const scale = width / 1000;
  context.fillStyle = '#242b26';
  context.font = `${34 * scale}px Arial, sans-serif`;
  const lineHeight = 48 * scale;
  const maxWidth = 800 * scale;
  let y = 110 * scale;
  for (const paragraph of text.split('\n')) {
    let line = '';
    for (const word of paragraph.split(/\s+/)) {
      const candidate = line ? `${line} ${word}` : word;
      if (context.measureText(candidate).width > maxWidth && line) {
        context.fillText(line, 100 * scale, y);
        y += lineHeight;
        line = word;
      } else {
        line = candidate;
      }
    }
    if (line && y < height - 60 * scale) {
      context.fillText(line, 100 * scale, y);
      y += lineHeight;
    }
    y += 14 * scale;
  }
}

export default function App() {
  const [page, setPage] = useState<PageName>('Home / Workspace');
  const [theme, setTheme] = useState<ThemeName>(() => themeFrom(localStorage.getItem('vd-theme')));
  const [avatar, setAvatar] = useState(() => companionFrom(localStorage.getItem('vd-avatar')).id);
  const [language, setLanguage] = useState(localStorage.getItem('vd-language') || 'en');
  const [token, setToken] = useState(localStorage.getItem('vd-token') || '');
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All tools');
  const [activeConversion, setActiveConversion] = useState<ConversionTool | null>(null);
  const [conversionFile, setConversionFile] = useState<File | null>(null);
  const [conversionOutput, setConversionOutput] = useState<ProcessedPdf | null>(null);
  const [conversionPreviewText, setConversionPreviewText] = useState('');
  const [conversionBusy, setConversionBusy] = useState(false);
  const [conversionSaveBusy, setConversionSaveBusy] = useState(false);
  const [conversionError, setConversionError] = useState('');
  const [conversionMessage, setConversionMessage] = useState('');
  const [scanMode, setScanMode] = useState(false);
  const [scanPages, setScanPages] = useState<ScanPage[]>([]);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanDraggedPage, setScanDraggedPage] = useState<string | null>(null);
  const [selectedAdvancedTool, setSelectedAdvancedTool] = useState<string | null>(null);
  const [advancedFiles, setAdvancedFiles] = useState<File[]>([]);
  const [advancedOptions, setAdvancedOptions] = useState<Record<string, string>>({});
  const [advancedBusy, setAdvancedBusy] = useState(false);
  const [advancedError, setAdvancedError] = useState('');
  const [advancedNotice, setAdvancedNotice] = useState('');
  const [advancedOutput, setAdvancedOutput] = useState<ProcessedPdf | null>(null);
  const [advancedTextOutput, setAdvancedTextOutput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [recentUpload, setRecentUpload] = useState<RecentUpload | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [assistantToast, setAssistantToast] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatConversations, setChatConversations] = useState<ChatConversation[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [chatHistoryBusy, setChatHistoryBusy] = useState(false);
  const [chatAttachment, setChatAttachment] = useState<File | null>(null);
  const [chatAttachmentError, setChatAttachmentError] = useState('');
  const [chatConversionOutput, setChatConversionOutput] = useState<ProcessedPdf | null>(null);
  const [chatConversionFormat, setChatConversionFormat] = useState<ExportFormat>('pdf');
  const [chatConversionBusy, setChatConversionBusy] = useState(false);
  const chatAttachmentInputRef = useRef<HTMLInputElement | null>(null);
  const [aiDocMode, setAiDocMode] = useState<'summary' | 'chat' | 'translate'>('summary');
  const [selectedAiDoc, setSelectedAiDoc] = useState<number | null>(null);
  const [aiDocSummary, setAiDocSummary] = useState('');
  const [aiDocError, setAiDocError] = useState('');
  const [aiDocSummaryBusy, setAiDocSummaryBusy] = useState(false);
  const [aiDocMessages, setAiDocMessages] = useState<ChatMessage[]>([]);
  const [aiDocChatInput, setAiDocChatInput] = useState('');
  const [aiDocChatBusy, setAiDocChatBusy] = useState(false);
  const [aiDocSource, setAiDocSource] = useState('auto');
  const [aiDocTarget, setAiDocTarget] = useState('ta');
  const [aiDocTranslation, setAiDocTranslation] = useState('');
  const [aiDocTranslateBusy, setAiDocTranslateBusy] = useState(false);
  const [aiCompanionLine, setAiCompanionLine] = useState('Choose one of your documents and I’ll help you understand, discuss, or translate it.');
  const [voiceFeedback, setVoiceFeedback] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [historyQuery, setHistoryQuery] = useState('');
  const [historyFilter, setHistoryFilter] = useState<'all' | 'pdf' | 'word' | 'text'>('all');
  const [historySort, setHistorySort] = useState<'name' | 'largest'>('name');
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const [pdfAction, setPdfAction] = useState<PdfAction>('info');
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [pdfPages, setPdfPages] = useState('');
  const [organizePageOrder, setOrganizePageOrder] = useState<number[]>([]);
  const [organizeRotations, setOrganizeRotations] = useState<Record<number, number>>({});
  const [pdfDegrees, setPdfDegrees] = useState('90');
  const [pdfPassword, setPdfPassword] = useState('');
  const [pdfCompressionTarget, setPdfCompressionTarget] = useState('');
  const [pdfCompressionUnit, setPdfCompressionUnit] = useState<'kb' | 'mb'>('kb');
  const [pdfRasterizeIfNeeded, setPdfRasterizeIfNeeded] = useState(false);
  const [pdfFlipDirection, setPdfFlipDirection] = useState<'horizontal' | 'vertical'>('horizontal');
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfProcessingMessage, setPdfProcessingMessage] = useState('');
  const [pdfSaveBusy, setPdfSaveBusy] = useState(false);
  const [pdfResult, setPdfResult] = useState('');
  const [pdfOutput, setPdfOutput] = useState<ProcessedPdf | null>(null);
  const [editorText, setEditorText] = useState('');
  const [editorUndoHistory, setEditorUndoHistory] = useState<EditorSnapshot[]>([]);
  const [editorRedoHistory, setEditorRedoHistory] = useState<EditorSnapshot[]>([]);
  const [editorImageSource, setEditorImageSource] = useState('');
  const [editorImagePreview, setEditorImagePreview] = useState('');
  const [editorImageName, setEditorImageName] = useState('');
  const [editorImageSelected, setEditorImageSelected] = useState(false);
  const [editorImagePosition, setEditorImagePosition] = useState<ImagePosition>({ x: 50, y: 62 });
  const [editorImageRotation, setEditorImageRotation] = useState(0);
  const [editorCropLeft, setEditorCropLeft] = useState(0);
  const [editorCropRight, setEditorCropRight] = useState(0);
  const [editorCropTop, setEditorCropTop] = useState(0);
  const [editorCropBottom, setEditorCropBottom] = useState(0);
  const [editorTool, setEditorTool] = useState<EditorTool>('text');
  const [editorColor, setEditorColor] = useState('#fff2a1');
  const [editorExportFormat, setEditorExportFormat] = useState<ExportFormat>('pdf');
  const [editorBusy, setEditorBusy] = useState(false);
  const [editorError, setEditorError] = useState('');
  const [editorDropActive, setEditorDropActive] = useState(false);
  const [drawingHistory, setDrawingHistory] = useState<string[]>([]);
  const [pdfSourceUrl, setPdfSourceUrl] = useState('');
  const [editorPdfFile, setEditorPdfFile] = useState<File | null>(null);
  const [pdfPageImage, setPdfPageImage] = useState('');
  const [pdfPageDimensions, setPdfPageDimensions] = useState({ width: 1000, height: 1414 });
  const [pdfPageNumber, setPdfPageNumber] = useState(1);
  const [pdfPageCount, setPdfPageCount] = useState(1);
  const [pdfRendering, setPdfRendering] = useState(false);
  const [pdfRenderError, setPdfRenderError] = useState('');
  const [editorBrushSize, setEditorBrushSize] = useState(4);
  const pdfFileInputRef = useRef<HTMLInputElement | null>(null);
  const scanFileInputRef = useRef<HTMLInputElement | null>(null);
  const imageFileInputRef = useRef<HTMLInputElement | null>(null);
  const editorPageRef = useRef<HTMLDivElement | null>(null);
  const drawingCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageDragOffset = useRef<ImagePosition | null>(null);
  const drawingPointer = useRef(false);
  const [translationText, setTranslationText] = useState('');
  const [translationSource, setTranslationSource] = useState('auto');
  const [translationTarget, setTranslationTarget] = useState('en');
  const [translationFile, setTranslationFile] = useState<File | null>(null);
  const [translationResult, setTranslationResult] = useState('');
  const [translationOutput, setTranslationOutput] = useState<ProcessedPdf | null>(null);
  const [translationSaveBusy, setTranslationSaveBusy] = useState(false);
  const [translationMessage, setTranslationMessage] = useState('');
  const [translationBusy, setTranslationBusy] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateKind | null>(null);
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft>(emptyTemplateDraft);
  const [templateAccent, setTemplateAccent] = useState<TemplateAccent>('forest');
  const [templateLayout, setTemplateLayout] = useState<'modern' | 'classic' | 'compact'>('modern');
  const [templatePhotoData, setTemplatePhotoData] = useState('');
  const [templatePhotoPreview, setTemplatePhotoPreview] = useState('');
  const [templatePhotoName, setTemplatePhotoName] = useState('');
  const [templateBusy, setTemplateBusy] = useState(false);

  const companion = companionFrom(avatar);
  const themeMode: 'light' | 'dark' = theme.endsWith('-dark') ? 'dark' : 'light';
  const paletteId = theme.slice(0, -(themeMode.length + 1)) as PaletteId;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('vd-theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('vd-avatar', avatar);
  }, [avatar]);

  useEffect(() => {
    localStorage.setItem('vd-language', language);
  }, [language]);

  useEffect(() => {
    if (page === 'AI Documents') {
      setAssistantToast('');
      setChatOpen(false);
    }
  }, [page]);

  useEffect(() => {
    if (!assistantToast || page === 'AI Documents') return;
    const timer = window.setTimeout(() => setAssistantToast(''), 6500);
    return () => window.clearTimeout(timer);
  }, [assistantToast, page]);

  useEffect(() => {
    if (!pdfOutput) return;
    return () => URL.revokeObjectURL(pdfOutput.url);
  }, [pdfOutput]);

  useEffect(() => {
    if (!translationOutput) return;
    return () => URL.revokeObjectURL(translationOutput.url);
  }, [translationOutput]);

  useEffect(() => {
    if (!chatConversionOutput) return;
    return () => URL.revokeObjectURL(chatConversionOutput.url);
  }, [chatConversionOutput]);

  useEffect(() => {
    if (!advancedOutput) return;
    return () => URL.revokeObjectURL(advancedOutput.url);
  }, [advancedOutput]);

  useEffect(() => {
    if (chatOpen && token) void loadChatHistory();
  }, [chatOpen, token]);

  useEffect(() => {
    if (!pdfFiles.length) {
      setPdfSourceUrl('');
      return;
    }
    const url = URL.createObjectURL(pdfFiles[0]);
    setPdfSourceUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [pdfFiles]);

  useEffect(() => {
    if (!editorImageSource) {
      setEditorImagePreview('');
      return;
    }
    let active = true;
    cropAndRotateImage(editorImageSource, editorImageRotation, editorCropLeft, editorCropRight, editorCropTop, editorCropBottom)
      .then((preview) => { if (active) { setEditorImagePreview(preview); setEditorError(''); } })
      .catch((error: unknown) => { if (active) setEditorError(error instanceof Error ? error.message : 'Could not edit this image.'); });
    return () => { active = false; };
  }, [editorImageSource, editorImageRotation, editorCropLeft, editorCropRight, editorCropTop, editorCropBottom]);

  useEffect(() => {
    const canvas = drawingCanvasRef.current;
    if (!canvas) return;
    canvas.width = editorPdfFile ? pdfPageDimensions.width : 1000;
    canvas.height = editorPdfFile ? pdfPageDimensions.height : 1414;
    const context = canvas.getContext('2d');
    if (context) context.clearRect(0, 0, canvas.width, canvas.height);
    setDrawingHistory([]);
    setEditorUndoHistory([]);
    setEditorRedoHistory([]);
  }, [editorPdfFile, pdfPageDimensions]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response));
        return response.json() as Promise<User>;
      })
      .then((profile) => {
        setUser(profile);
        setTheme(themeFrom(profile.theme));
        setAvatar(companionFrom(profile.avatar).id);
        setLanguage(profile.language || 'en');
      })
      .catch(() => {
        setToken('');
        localStorage.removeItem('vd-token');
      });
  }, [token]);

  const loadDocuments = useCallback(async () => {
    if (!token) {
      setDocuments([]);
      return;
    }
    try {
      const response = await fetch(`${API}/api/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setDocuments(await response.json() as DocumentItem[]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load documents.');
    }
  }, [token]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const filteredTools = useMemo(() => {
    const query = search.trim().toLowerCase();
    return Object.entries(groups).flatMap(([group, names]) =>
      (category === 'All tools' || group === category ? names : [])
        .filter((toolName) => !query || toolName.toLowerCase().includes(query))
        .map((toolName) => ({ name: toolName, category: group })),
    );
  }, [category, search]);

  async function savePreferences(values: Partial<Pick<User, 'theme' | 'language' | 'avatar'>>) {
    if (values.theme) setTheme(themeFrom(values.theme));
    if (values.language) setLanguage(values.language);
    if (values.avatar) setAvatar(values.avatar);
    setNotice('');
    if (!token) {
      setNotice('Saved on this device. Sign in to sync your preferences.');
      return;
    }
    try {
      const response = await fetch(`${API}/api/settings/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(values),
      });
      if (!response.ok) throw new Error(await responseError(response));
      setUser(await response.json() as User);
      setNotice('Your preferences are saved.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save your preferences.');
    }
  }

  function encourageUser(message: string) {
    if (page === 'AI Documents') {
      setNotice(message);
      return;
    }
    setNotice('');
    setAssistantToast(message);
  }

  async function submitAuth() {
    try {
      const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/login';
      const payload = authMode === 'signup' ? { name, email, password } : { email, password };
      const response = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      localStorage.setItem('vd-token', result.access_token);
      setToken(result.access_token);
      setPassword('');
      setUser(result.user as User);
      setTheme(themeFrom(result.user.theme));
      setAvatar(companionFrom(result.user.avatar).id);
      setLanguage(result.user.language || 'en');
      setPage('Home / Workspace');
      setNotice(authMode === 'signup' ? 'Account created. You are signed in.' : 'You are signed in.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not sign in.');
    }
  }

  function signOut() {
    window.speechSynthesis?.cancel();
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setIsListening(false);
    setIsSpeaking(false);
    setToken('');
    setUser(null);
    setDocuments([]);
    setRecentUpload(null);
    setSelectedAiDoc(null);
    setAiDocMessages([]);
    setAiDocSummary('');
    setAiDocTranslation('');
    setChatMessages([]);
    setChatConversations([]);
    setActiveChatId(null);
    setChatAttachment(null);
    setChatConversionOutput(null);
    setName('');
    setEmail('');
    setPassword('');
    setAuthMode('login');
    localStorage.removeItem('vd-token');
    setNotice('You have signed out. The next person can sign in with their own account.');
  }

  async function uploadDocument(file?: File) {
    if (!file) return;
    if (!token) {
      setNotice('Sign in before uploading a document.');
      setPage('Account / Privacy');
      return;
    }
    const data = new FormData();
    data.append('file', file);
    try {
      setNotice(`Uploading ${file.name}…`);
      const response = await fetch(`${API}/api/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: data,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const uploaded = await response.json() as DocumentItem;
      setRecentUpload({ document: uploaded, file });
      encourageUser(`Nice work! “${uploaded.name}” is safely in your workspace.`);
      await loadDocuments();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Upload failed.');
    }
  }

  function renderUploadNextSteps() {
    if (!recentUpload) return null;
    const extension = recentUpload.document.name.split('.').pop()?.toLowerCase() ?? '';
    const canStudy = ['pdf', 'docx', 'txt', 'md'].includes(extension);
    const canConvert = conversionTools.some((tool) => tool.inputExtensions.includes(extension));
    const canEdit = extension === 'pdf';
    return (
      <section className="panel upload-next-steps" aria-labelledby="upload-next-steps-title">
        <div className="upload-next-steps-heading">
          <div>
            <span className="eyebrow">YOUR FILE IS READY</span>
            <h2 id="upload-next-steps-title">What would you like to do with {recentUpload.document.name}?</h2>
            <p>Your original is saved in your workspace. Choose a next step, or come back to this file later.</p>
          </div>
          <button className="upload-next-steps-close" aria-label="Dismiss next steps" onClick={() => setRecentUpload(null)}><X size={17} /></button>
        </div>
        <div className="upload-next-step-grid">
          <button disabled={!canEdit} onClick={() => {
            setPdfAction('info');
            setPage('PDF Studio');
            selectPdfFiles([recentUpload.file]);
          }}>
            <FileText size={19} /><b>Edit in PDF Studio</b><small>{canEdit ? 'Open this PDF to annotate or edit its page.' : 'PDF files only. Convert this file to PDF first.'}</small>
          </button>
          <button disabled={!canStudy} onClick={() => {
            chooseAiDocument(String(recentUpload.document.id));
            setAiDocMode('summary');
            setPage('AI Documents');
          }}>
            <BookOpen size={19} /><b>Study with AI</b><small>{canStudy ? 'Summarize, ask questions, or translate this document.' : 'Supports PDF, DOCX, TXT, and Markdown.'}</small>
          </button>
          <button disabled={!canConvert} onClick={() => {
            setActiveConversion(null);
            setConversionFile(recentUpload.file);
            setPage('Convert');
          }}>
            <ArrowLeftRight size={19} /><b>Convert file</b><small>{canConvert ? 'Choose the output format that fits your needs.' : 'No conversion is available for this file type.'}</small>
          </button>
          <button onClick={() => setPage('Templates')}>
            <LayoutDashboard size={19} /><b>Start from a template</b><small>Create a resume, letter, proposal, or another document.</small>
          </button>
        </div>
      </section>
    );
  }

  async function downloadDocument(item: DocumentItem) {
    try {
      const response = await fetch(`${API}/api/documents/${item.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = item.name;
      link.click();
      URL.revokeObjectURL(url);
      encourageUser(`Your download is ready. Keep up the great work with “${item.name}”!`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Download failed.');
    }
  }

  async function deleteDocument(item: DocumentItem) {
    try {
      const response = await fetch(`${API}/api/documents/${item.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      encourageUser(`All set! “${item.name}” is removed from your workspace. Nice and tidy!`);
      await loadDocuments();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Delete failed.');
    }
  }

  async function createChatConversation() {
    if (!token) throw new Error('Sign in to create a private chat.');
    const response = await fetch(`${API}/api/ai/conversations`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error(await responseError(response));
    const conversation = await response.json() as ChatConversation;
    setChatConversations((items) => [conversation, ...items]);
    setActiveChatId(conversation.id);
    setChatMessages([]);
    setChatAttachment(null);
    setChatConversionOutput(null);
    return conversation;
  }

  async function selectChatConversation(id: number) {
    if (!token) return;
    setChatHistoryBusy(true);
    try {
      const response = await fetch(`${API}/api/ai/conversations/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      const conversation = await response.json() as { id: number; messages: ChatMessage[] };
      setActiveChatId(conversation.id);
      setChatMessages(conversation.messages);
      setChatAttachment(null);
      setChatConversionOutput(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not open this chat.');
    } finally {
      setChatHistoryBusy(false);
    }
  }

  async function loadChatHistory() {
    if (!token || chatHistoryBusy) return;
    setChatHistoryBusy(true);
    try {
      const response = await fetch(`${API}/api/ai/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      const conversations = await response.json() as ChatConversation[];
      setChatConversations(conversations);
      const selected = conversations.find((item) => item.id === activeChatId) ?? conversations[0];
      if (selected) {
        const detailResponse = await fetch(`${API}/api/ai/conversations/${selected.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!detailResponse.ok) throw new Error(await responseError(detailResponse));
        const detail = await detailResponse.json() as { id: number; messages: ChatMessage[] };
        setActiveChatId(detail.id);
        setChatMessages(detail.messages);
      } else {
        const createdResponse = await fetch(`${API}/api/ai/conversations`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!createdResponse.ok) throw new Error(await responseError(createdResponse));
        const created = await createdResponse.json() as ChatConversation;
        setChatConversations([created]);
        setActiveChatId(created.id);
        setChatMessages([]);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load chat history.');
    } finally {
      setChatHistoryBusy(false);
    }
  }

  async function deleteChatConversation(id: number) {
    if (!token) return;
    try {
      const response = await fetch(`${API}/api/ai/conversations/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      const remaining = chatConversations.filter((item) => item.id !== id);
      setChatConversations(remaining);
      if (activeChatId === id) {
        setActiveChatId(null);
        setChatMessages([]);
        if (remaining[0]) await selectChatConversation(remaining[0].id);
        else await createChatConversation();
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not delete this chat.');
    }
  }

  async function sendChat() {
    if ((!chatInput.trim() && !chatAttachment) || chatBusy) return;
    if (!token) {
      setNotice('Sign in to use the assistant.');
      setPage('Account / Privacy');
      return;
    }
    const attachment = chatAttachment;
    const message = chatInput.trim() || (attachment?.type.startsWith('image/') ? 'Please describe the attached image.' : 'Please read the attached document and help me understand it.');
    setChatBusy(true);
    try {
      let conversationId = activeChatId;
      if (!conversationId) conversationId = (await createChatConversation()).id;
      setChatInput('');
      setChatAttachment(null);
      setChatMessages((current) => [...current, { role: 'user', text: attachment ? `${message}\n\n[${attachment.name}]` : message }]);
      let context: string | undefined;
      let imageData: string | undefined;
      if (attachment && attachment.type.startsWith('image/')) {
        const imageTypes = ['image/png', 'image/jpeg', 'image/webp'];
        if (!imageTypes.includes(attachment.type) || attachment.size > 4 * 1024 * 1024) {
          throw new Error('Attach a PNG, JPEG, or WebP image smaller than 4 MB.');
        }
        imageData = (await readImageData(attachment)).split(',')[1];
      } else if (attachment) {
        const form = new FormData();
        form.append('file', attachment);
        const response = await fetch(`${API}/api/ai/chat/attachment-text`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        if (!response.ok) throw new Error(await responseError(response));
        context = (await response.json() as { text: string }).text;
      }
      const response = await fetch(`${API}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message, language, conversation_id: conversationId, context, image_data: imageData, image_media_type: attachment?.type.startsWith('image/') ? attachment.type : 'image/png' }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { reply: string; conversation_id: number; title: string };
      setChatMessages((current) => [...current, { role: 'assistant', text: result.reply }]);
      setActiveChatId(result.conversation_id);
      setChatConversations((items) => items.map((item) => item.id === result.conversation_id ? { ...item, title: result.title, updated_at: new Date().toISOString() } : item));
    } catch (error) {
      if (attachment) setChatAttachment(attachment);
      setChatMessages((current) => [...current, {
        role: 'assistant',
        text: error instanceof Error ? error.message : 'The assistant could not respond.',
      }]);
    } finally {
      setChatBusy(false);
    }
  }

  async function convertChatAttachment() {
    if (!token || !chatAttachment || chatConversionBusy) return;
    setChatConversionBusy(true);
    setChatAttachmentError('');
    try {
      const form = new FormData();
      form.append('file', chatAttachment);
      form.append('output_format', chatConversionFormat);
      const response = await fetch(`${API}/api/pdf/convert`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const file = new File([blob], `vertex-converted.${chatConversionFormat}`, { type: blob.type });
      setChatConversionOutput({ file, url: URL.createObjectURL(file) });
      setChatMessages((current) => [...current, { role: 'assistant', text: `Your ${chatConversionFormat.toUpperCase()} conversion of “${chatAttachment.name}” is ready. Download it below.` }]);
    } catch (error) {
      setChatAttachmentError(error instanceof Error ? error.message : 'The file could not be converted.');
    } finally {
      setChatConversionBusy(false);
    }
  }

  function speakText(text: string, languageCode = language) {
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
      setVoiceFeedback('Speech playback is not supported in this browser.');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = speechLocales[languageCode] ?? 'en-US';
    utterance.onstart = () => { setIsSpeaking(true); setVoiceFeedback(''); };
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => { setIsSpeaking(false); setVoiceFeedback('Speech playback could not start. Check the voices available on this device.'); };
    window.speechSynthesis.speak(utterance);
  }

  function startVoiceInput(onText: (text: string) => void) {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }
    const SpeechRecognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceFeedback('Voice input is not supported in this browser. You can still type your message.');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = speechLocales[language] ?? 'en-US';
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((result) => result[0]?.transcript ?? '').join(' ').trim();
      if (transcript) onText(transcript);
    };
    recognition.onerror = (event) => {
      setVoiceFeedback(event.error === 'not-allowed' ? 'Allow microphone access in your browser to use voice input.' : `Voice input stopped: ${event.error}.`);
    };
    recognition.onend = () => { setIsListening(false); recognitionRef.current = null; };
    recognitionRef.current = recognition;
    setVoiceFeedback('');
    setIsListening(true);
    try {
      recognition.start();
    } catch (error) {
      setIsListening(false);
      recognitionRef.current = null;
      setVoiceFeedback(error instanceof Error ? error.message : 'Voice input could not start.');
    }
  }

  function chooseAiDocument(value: string) {
    const documentId = value.trim() ? Number(value) : null;
    setSelectedAiDoc(documentId !== null && Number.isInteger(documentId) && documentId > 0 ? documentId : null);
    setAiDocSummary('');
    setAiDocError('');
    setAiDocMessages([]);
    setAiDocChatInput('');
    setAiDocTranslation('');
    setAiCompanionLine('Ready when you are! Choose summarize, chat, or translate to get started.');
    setVoiceFeedback('');
  }

  async function summarizeAiDocument() {
    if (!token || !selectedAiDoc || aiDocSummaryBusy) return;
    setAiDocSummaryBusy(true);
    setAiDocSummary('');
    setAiDocError('');
    setVoiceFeedback('');
    try {
      const response = await fetch(`${API}/api/ai/documents/${selectedAiDoc}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ language }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { summary: string };
      setAiDocSummary(result.summary);
      setAiCompanionLine('Your summary is ready! I pulled out the main ideas so you can get to the important parts faster.');
    } catch (error) {
      setAiDocError(error instanceof Error ? error.message : 'Could not summarize this document.');
      setAiCompanionLine('I couldn’t finish that just now. Check the message below and try again when ready.');
    } finally {
      setAiDocSummaryBusy(false);
    }
  }

  async function sendAiDocumentChat() {
    const message = aiDocChatInput.trim();
    if (!message || !selectedAiDoc || !token || aiDocChatBusy) return;
    const history = aiDocMessages.slice(-12).map((item) => ({ role: item.role, content: item.text }));
    setAiDocChatInput('');
    setAiDocMessages((current) => [...current, { role: 'user', text: message }]);
    setAiDocChatBusy(true);
    try {
      const response = await fetch(`${API}/api/ai/documents/${selectedAiDoc}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message, language, history }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { reply: string };
      setAiDocMessages((current) => [...current, { role: 'assistant', text: result.reply }]);
      setAiCompanionLine('I’m here with you—ask another question about this document any time.');
    } catch (error) {
      setAiDocMessages((current) => [...current, { role: 'assistant', text: error instanceof Error ? error.message : 'The document assistant could not respond.' }]);
      setAiCompanionLine('The connection didn’t work this time. Your document is safe; please try again.');
    } finally {
      setAiDocChatBusy(false);
    }
  }

  async function translateAiDocument() {
    if (!token || !selectedAiDoc || aiDocTranslateBusy) return;
    setAiDocTranslateBusy(true);
    setAiDocTranslation('');
    setAiDocError('');
    try {
      const response = await fetch(`${API}/api/ai/documents/${selectedAiDoc}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ source_language: aiDocSource, target_language: aiDocTarget }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { translation: string };
      setAiDocTranslation(result.translation);
      const targetName = languages.find(([code]) => code === aiDocTarget)?.[1] ?? 'your chosen language';
      setAiCompanionLine(`Your ${targetName} translation is ready. Have a look, and you can download it as a text file.`);
    } catch (error) {
      setAiDocError(error instanceof Error ? error.message : 'Could not translate this document.');
      setAiCompanionLine('I couldn’t translate that document just now. Check that the file has readable text and try again.');
    } finally {
      setAiDocTranslateBusy(false);
    }
  }

  function downloadAiTranslation() {
    if (!aiDocTranslation) return;
    const targetName = languages.find(([code]) => code === aiDocTarget)?.[1]?.toLowerCase() ?? 'translation';
    const blob = new Blob([aiDocTranslation], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `vertex-translation-${targetName}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    setAiCompanionLine('Your translated text file is downloaded and ready to use!');
  }

  async function runTranslation() {
    if (!token) {
      setTranslationResult('Sign in to use translation.');
      setPage('Account / Privacy');
      return;
    }
    if (!translationFile && !translationText.trim()) {
      setTranslationResult('Enter text or choose a PDF, DOCX, TXT, or Markdown file.');
      return;
    }
    setTranslationBusy(true);
    setTranslationResult('');
    setTranslationMessage('');
    setTranslationOutput(null);
    try {
      const body = translationFile ? new FormData() : JSON.stringify({
        text: translationText.trim(),
        source_language: translationSource,
        target_language: translationTarget,
      });
      if (translationFile && body instanceof FormData) {
        body.append('file', translationFile);
        body.append('source_language', translationSource);
        body.append('target_language', translationTarget);
      }
      const response = await fetch(`${API}/api/ai/${translationFile ? 'translate-file' : 'translate'}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          ...(!translationFile ? { 'Content-Type': 'application/json' } : {}),
        },
        body,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { translation: string };
      setTranslationResult(result.translation);
      if (translationFile) {
        const baseName = translationFile.name.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9-_]+/g, '-').replace(/^-|-$/g, '') || 'document';
        const targetCode = translationTarget.replace(/[^a-zA-Z0-9-]/g, '') || 'translated';
        const file = new File([result.translation], `vertex-${baseName}-${targetCode}.txt`, { type: 'text/plain;charset=utf-8' });
        setTranslationOutput({ file, url: URL.createObjectURL(file) });
        setTranslationMessage('Translation is ready. Download it or save it to your workspace history.');
      }
      const targetName = languages.find(([code]) => code === translationTarget)?.[1] ?? 'your chosen language';
      encourageUser(`Your ${targetName} translation is ready. Take a look—you’re doing great!`);
    } catch (error) {
      setTranslationResult(error instanceof Error ? error.message : 'Translation failed.');
    } finally {
      setTranslationBusy(false);
    }
  }

  function clearTranslationOutput() {
    setTranslationOutput(null);
    setTranslationResult('');
    setTranslationMessage('Translation result deleted.');
  }

  function downloadTranslationOutput() {
    if (!translationOutput) return;
    triggerDownload(translationOutput.file, translationOutput.url);
    setTranslationMessage(`Downloaded “${translationOutput.file.name}”.`);
  }

  async function saveTranslationOutput() {
    if (!translationOutput || !token || translationSaveBusy) return;
    setTranslationSaveBusy(true);
    try {
      const saved = await saveFileToWorkspace(translationOutput.file);
      setTranslationMessage(`Saved “${saved}” to Document History.`);
      encourageUser(`Your translated file is saved as “${saved}”. You can find it in Document History.`);
    } catch (error) {
      setTranslationMessage(error instanceof Error ? error.message : 'The translation could not be saved.');
    } finally {
      setTranslationSaveBusy(false);
    }
  }

  function chooseTemplate(template: TemplateKind) {
    setSelectedTemplate(template);
    setPdfOutput(null);
    setPdfResult('');
    setTemplatePhotoData('');
    setTemplatePhotoPreview('');
    setTemplatePhotoName('');
    setTemplateDraft({
      ...emptyTemplateDraft,
      full_name: user?.name ?? '',
      title: template === 'resume' ? '' : (templateCatalog.find((item) => item.id === template)?.name ?? ''),
    });
    if (template === 'resume') {
      resetEditor();
      setPdfAction('info');
      setPage('PDF Studio');
    }
  }

  function chooseTemplatePhoto(file?: File) {
    if (!file) return;
    if (!['image/png','image/jpeg','image/webp'].includes(file.type)) {
      setPdfResult('Choose a PNG, JPEG, or WebP profile photo.');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setPdfResult('Profile photos must be 2 MB or smaller.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== 'string') {
        setPdfResult('The profile photo could not be read.');
        return;
      }
      const separator = reader.result.indexOf(',');
      if (separator < 0) {
        setPdfResult('The profile photo could not be encoded.');
        return;
      }
      setTemplatePhotoData(reader.result.slice(separator + 1));
      setTemplatePhotoPreview(reader.result);
      setTemplatePhotoName(file.name);
      setPdfResult('');
    };
    reader.onerror = () => setPdfResult('The profile photo could not be read.');
    reader.readAsDataURL(file);
  }

  async function generateTemplatePdf() {
    if (!selectedTemplate || !token || templateBusy) return;
    setTemplateBusy(true);
    setPdfOutput(null);
    setPdfResult('');
    try {
      const response = await fetch(`${API}/api/templates/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ...templateDraft, template: selectedTemplate, layout: templateLayout, accent: templateAccent, photo_data: selectedTemplate === 'resume' ? templatePhotoData || null : null }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const file = new File([blob], `vertex-${selectedTemplate}.pdf`, { type: 'application/pdf' });
      const url = URL.createObjectURL(file);
      setPdfOutput({ file, url });
      setPdfResult('Your template PDF is ready to preview. Review it, then save, download, or delete it.');
      if (selectedTemplate === 'resume') {
        setPage('PDF Studio');
        setPdfFiles([file]);
        setEditorPdfFile(file);
        setPdfPageNumber(1);
        void renderPdfPage(file, 1);
      }
      encourageUser('Your document is taking shape! The PDF preview is ready—have a look and choose what works for you.');
    } catch (error) {
      setPdfResult(error instanceof Error ? error.message : 'Could not create this template PDF.');
    } finally {
      setTemplateBusy(false);
    }
  }

  function renderPdfPreview() {
    if (!pdfOutput) return null;
    return (
      <section className="panel pdf-preview-panel">
        <div className="section-title">
          <div><span className="eyebrow">REVIEW YOUR CHANGES</span><h2>Preview edited PDF</h2><p>{pdfOutput.file.name} · Check the result, then choose what to do with it.</p></div>
        </div>
        {pdfResult && <p className="operation-notice">{pdfResult}</p>}
        <iframe className="pdf-preview-frame" src={pdfOutput.url} title="Preview of edited PDF" />
        <div className="pdf-output-actions">
          <button className="primary" disabled={!token || pdfSaveBusy} onClick={() => void savePdfOutput()}><Check size={16} /> {pdfSaveBusy ? 'Saving…' : 'Save to workspace'}</button>
          <button onClick={downloadPdfOutput}><Download size={16} /> Download PDF</button>
          <button className="discard-button" onClick={discardPdfOutput}><Trash2 size={16} /> Delete preview</button>
          {!token && <small>Sign in to save this PDF to your workspace. Download is available now.</small>}
        </div>
      </section>
    );
  }

  function renderTemplates() {
    if (!selectedTemplate) {
      return (
        <>
          <PageHeading eyebrow="READY-MADE DOCUMENTS" title="Start with a template" subtitle="Choose a layout, personalize the content and create a PDF you can save or download." />
          <div className="template-gallery">
            {templateCatalog.map((item) => (
              <button className="template-card" key={item.id} onClick={() => chooseTemplate(item.id)}>
                <TemplateArtwork template={item.id} />
                <span className="template-card-category">{item.category}</span>
                <b>{item.name}</b>
                <small>{item.description}</small>
                <span className="template-card-link">Customize template <ChevronDown size={14} /></span>
              </button>
            ))}
          </div>
        </>
      );
    }
    const activeTemplate = templateCatalog.find((item) => item.id === selectedTemplate);
    const fields = templateFields[selectedTemplate];
    const visiblePreviewFields = fields.filter((field) => (
      !['full_name','title','email','phone','location','website'].includes(field.name)
      && templateDraft[field.name].trim()
    ));
    const contact = [templateDraft.email,templateDraft.phone,templateDraft.location,templateDraft.website].filter(Boolean).join(' · ');
    return (
      <>
        <div className="template-editor-heading">
          <button onClick={() => { setSelectedTemplate(null); setPdfOutput(null); setPdfResult(''); }}><ChevronDown size={15} /> All templates</button>
          <PageHeading eyebrow={`${activeTemplate?.category.toUpperCase() ?? 'TEMPLATE'} · EDITOR`} title={`Edit ${activeTemplate?.name ?? 'template'}`} subtitle="Update the content and style. Generate a PDF when the preview looks right." />
        </div>
        <div className="template-editor-grid">
          <section className="panel template-form-panel">
            <div className="section-title"><div><h2>Customize your document</h2><p>Changes appear in the preview as you type.</p></div></div>
            <div className="template-style-options">
              <label className="field-label">Layout<select value={templateLayout} onChange={(event) => setTemplateLayout(event.target.value as 'modern' | 'classic' | 'compact')}><option value="modern">Modern</option><option value="classic">Classic</option><option value="compact">Compact</option></select></label>
              <label className="field-label">Accent color<select value={templateAccent} onChange={(event) => setTemplateAccent(event.target.value as TemplateAccent)}>{palettes.slice(0, 6).map((palette) => <option key={palette.id} value={palette.id}>{palette.name}</option>)}</select></label>
            </div>
            <div className="template-fields">
              {fields.map((field) => (
                <label className={`field-label ${field.multiline ? 'template-field-wide' : ''}`} key={field.name}>{field.label}
                  {field.multiline
                    ? <textarea value={templateDraft[field.name]} onChange={(event) => setTemplateDraft((current) => ({ ...current, [field.name]: event.target.value }))} placeholder={field.placeholder} />
                    : <input value={templateDraft[field.name]} onChange={(event) => setTemplateDraft((current) => ({ ...current, [field.name]: event.target.value }))} placeholder={field.placeholder} />}
                </label>
              ))}
            </div>
            {selectedTemplate === 'resume' && <div className="template-photo-uploader">
              <span className="template-photo-label">Profile photo <small>Optional · PNG, JPEG or WebP · up to 2 MB</small></span>
              <div>
                <label className="template-photo-pick"><UploadCloud size={15}/>{templatePhotoName || 'Choose a photo'}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event)=>chooseTemplatePhoto(event.target.files?.[0])}/></label>
                {templatePhotoPreview&&<button className="template-photo-remove" onClick={()=>{setTemplatePhotoData('');setTemplatePhotoPreview('');setTemplatePhotoName('');}}>Remove</button>}
              </div>
            </div>}
            <button className="primary full-button" disabled={!token || templateBusy} onClick={() => void generateTemplatePdf()}>{templateBusy ? 'Creating PDF…' : 'Generate PDF preview'}</button>
            {!token && <p className="inline-hint">Sign in to generate and save templates. You can still edit and preview the layout here.</p>}
            {pdfResult && !pdfOutput && <p className="operation-notice">{pdfResult}</p>}
          </section>
          <section className="template-live-panel">
            <div className="template-live-caption"><span className="eyebrow">LIVE PREVIEW</span><small>{templateLayout} · {palettes.find((palette) => palette.id === templateAccent)?.name}</small></div>
            <article className={`template-paper ${templateLayout} accent-${templateAccent} ${templatePhotoPreview?'has-photo':''}`}>
              <span className="paper-kicker">{activeTemplate?.category}</span>
              {templatePhotoPreview&&selectedTemplate==='resume'&&<img className="template-photo-preview" src={templatePhotoPreview} alt="Resume profile preview"/>}
              <h2>{selectedTemplate === 'resume' ? (templateDraft.full_name || 'Your Name') : (templateDraft.title || activeTemplate?.name)}</h2>
              {selectedTemplate === 'resume' && templateDraft.title && <h3>{templateDraft.title}</h3>}
              {contact && <p className="paper-contact">{contact}</p>}
              {selectedTemplate !== 'resume' && templateDraft.full_name && <p className="paper-author">{templateDraft.full_name}</p>}
              {visiblePreviewFields.length ? visiblePreviewFields.map((field) => (
                <section key={field.name}><h4>{field.label}</h4><p>{templateDraft[field.name]}</p></section>
              )) : <p className="paper-placeholder">Fill in the fields to see your document take shape.</p>}
            </article>
          </section>
        </div>
        {renderPdfPreview()}
      </>
    );
  }

  function renderResumeStudioPanel() {
    const fields = templateFields.resume;
    const previewFields = fields.filter((field) => (
      !['full_name', 'title', 'email', 'phone', 'location', 'website'].includes(field.name)
      && templateDraft[field.name].trim()
    ));
    const contact = [templateDraft.email, templateDraft.phone, templateDraft.location, templateDraft.website].filter(Boolean).join(' · ');
    return (
      <section className="panel resume-studio-panel">
        <div className="section-title">
          <div><span className="eyebrow">RESUME EDITOR</span><h2>Customize your resume</h2><p>Edit the resume content while keeping the PDF Studio tools available above.</p></div>
          <button onClick={() => { setSelectedTemplate(null); setPage('Templates'); }}>Back to templates</button>
        </div>
        <div className="resume-studio-grid">
          <div className="resume-studio-form">
            <div className="template-style-options">
              <label className="field-label">Layout<select value={templateLayout} onChange={(event) => setTemplateLayout(event.target.value as 'modern' | 'classic' | 'compact')}><option value="modern">Modern</option><option value="classic">Classic</option><option value="compact">Compact</option></select></label>
              <label className="field-label">Accent color<select value={templateAccent} onChange={(event) => setTemplateAccent(event.target.value as TemplateAccent)}>{palettes.slice(0, 6).map((palette) => <option key={palette.id} value={palette.id}>{palette.name}</option>)}</select></label>
            </div>
            <div className="template-fields">
              {fields.map((field) => (
                <label className={`field-label ${field.multiline ? 'template-field-wide' : ''}`} key={field.name}>{field.label}
                  {field.multiline
                    ? <textarea value={templateDraft[field.name]} onChange={(event) => setTemplateDraft((current) => ({ ...current, [field.name]: event.target.value }))} placeholder={field.placeholder} />
                    : <input value={templateDraft[field.name]} onChange={(event) => setTemplateDraft((current) => ({ ...current, [field.name]: event.target.value }))} placeholder={field.placeholder} />}
                </label>
              ))}
            </div>
            <div className="template-photo-uploader">
              <span className="template-photo-label">Profile photo <small>Optional · PNG, JPEG or WebP · up to 2 MB</small></span>
              <div>
                <label className="template-photo-pick"><UploadCloud size={15}/>{templatePhotoName || 'Choose a photo'}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { chooseTemplatePhoto(event.target.files?.[0]); event.target.value = ''; }} /></label>
                {templatePhotoPreview && <button className="template-photo-remove" onClick={() => { setTemplatePhotoData(''); setTemplatePhotoPreview(''); setTemplatePhotoName(''); }}>Remove</button>}
              </div>
            </div>
            <button className="primary full-button" disabled={!token || templateBusy} onClick={() => void generateTemplatePdf()}>{templateBusy ? 'Creating resume PDF…' : 'Create resume PDF'}</button>
            {!token && <p className="inline-hint">Sign in to generate and save a resume PDF.</p>}
          </div>
          <div className="template-live-panel">
            <div className="template-live-caption"><span className="eyebrow">RESUME PREVIEW</span><small>{templateLayout} · {palettes.find((palette) => palette.id === templateAccent)?.name}</small></div>
            <article className={`template-paper ${templateLayout} accent-${templateAccent} ${templatePhotoPreview ? 'has-photo' : ''}`}>
              <span className="paper-kicker">Career</span>
              {templatePhotoPreview && <img className="template-photo-preview" src={templatePhotoPreview} alt="Resume profile preview" />}
              <h2>{templateDraft.full_name || 'Your Name'}</h2>
              {templateDraft.title && <h3>{templateDraft.title}</h3>}
              {contact && <p className="paper-contact">{contact}</p>}
              {previewFields.length ? previewFields.map((field) => <section key={field.name}><h4>{field.label}</h4><p>{templateDraft[field.name]}</p></section>) : <p className="paper-placeholder">Fill in the fields to see your resume take shape.</p>}
            </article>
          </div>
        </div>
      </section>
    );
  }

  function moveOrganizePage(pageNumber: number, offset: number) {
    setOrganizePageOrder((current) => {
      const currentIndex = current.indexOf(pageNumber);
      const nextIndex = currentIndex + offset;
      if (currentIndex < 0 || nextIndex < 0 || nextIndex >= current.length) return current;
      const next = [...current];
      [next[currentIndex], next[nextIndex]] = [next[nextIndex], next[currentIndex]];
      return next;
    });
  }

  function rotateOrganizePage(pageNumber: number) {
    setOrganizeRotations((current) => ({ ...current, [pageNumber]: ((current[pageNumber] ?? 0) + 90) % 360 }));
  }

  function removeOrganizePage(pageNumber: number) {
    setOrganizePageOrder((current) => current.filter((page) => page !== pageNumber));
    setOrganizeRotations((current) => {
      const next = { ...current };
      delete next[pageNumber];
      return next;
    });
  }

  async function runPdfAction() {
    if (!pdfFiles.length) {
      setPdfResult('Choose a PDF file first.');
      return;
    }
    if (pdfAction === 'merge' && pdfFiles.length < 2) {
      setPdfResult('Choose at least two PDF files to merge.');
      return;
    }
    if (['split', 'remove-pages', 'extract-pages'].includes(pdfAction) && !pdfPages.trim()) {
      setPdfResult('Enter page numbers separated by commas, for example 1,3,5.');
      return;
    }
    if (['protect', 'unlock'].includes(pdfAction) && !pdfPassword) {
      setPdfResult('Enter the PDF password.');
      return;
    }
    if (pdfAction === 'organize' && !organizePageOrder.length) {
      setPdfResult('Open a PDF and choose at least one page to keep.');
      return;
    }
    let targetSizeBytes: number | null = null;
    if (pdfAction === 'compress' && pdfCompressionTarget.trim()) {
      const targetSize = Number(pdfCompressionTarget);
      const multiplier = pdfCompressionUnit === 'mb' ? 1024 * 1024 : 1024;
      targetSizeBytes = Math.round(targetSize * multiplier);
      if (!Number.isFinite(targetSize) || targetSize <= 0 || targetSizeBytes < 1 || targetSizeBytes > 50 * 1024 * 1024) {
        setPdfResult('Enter a compression target greater than zero and no larger than 50 MB.');
        return;
      }
    }
    setPdfBusy(true);
    setPdfProcessingMessage(pdfAction === 'flip'
      ? `Flipping every page ${pdfFlipDirection}…`
      : `Running ${pdfActions.find((action) => action.id === pdfAction)?.name ?? 'PDF operation'}…`);
    setPdfOutput(null);
    setPdfResult('');
    const data = new FormData();
    if (pdfAction === 'merge') {
      pdfFiles.forEach((file) => data.append('files', file));
    } else {
      data.append('file', pdfFiles[0]);
    }
    if (['split', 'remove-pages', 'extract-pages'].includes(pdfAction)) data.append('pages', pdfPages);
    if (pdfAction === 'organize') {
      data.append('page_order', organizePageOrder.join(','));
      data.append('rotations', Object.entries(organizeRotations).map(([pageNumber, degrees]) => `${pageNumber}:${degrees}`).join(','));
    }
    if (pdfAction === 'rotate') data.append('degrees', pdfDegrees);
    if (['protect', 'unlock'].includes(pdfAction)) data.append('password', pdfPassword);
    if (pdfAction === 'compress') {
      if (targetSizeBytes !== null) data.append('target_size_bytes', String(targetSizeBytes));
      data.append('rasterize_if_needed', String(pdfRasterizeIfNeeded));
    }
    if (pdfAction === 'flip') data.append('options', JSON.stringify({ direction: pdfFlipDirection }));

    try {
      const endpoint = pdfAction === 'flip' ? `${API}/api/pdf/tools/flip-pdf` : `${API}/api/pdf/${pdfAction}`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: data,
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (pdfAction === 'info' || pdfAction === 'text') {
        const result = await response.json();
        setPdfResult(pdfAction === 'text' ? result.text || 'No extractable text found.' : JSON.stringify(result, null, 2));
        if (pdfAction === 'text') encourageUser('I pulled the readable text out for you. You’re ready for the next step!');
      } else {
        const blob = await response.blob();
        const fileName = pdfAction === 'flip' ? `vertex-flipped-${pdfFlipDirection}.pdf` : `vertex-${pdfAction}.pdf`;
        const file = new File([blob], fileName, { type: 'application/pdf' });
        const url = URL.createObjectURL(file);
        setPdfOutput({ file, url });
        setPdfFiles([file]);
        setEditorPdfFile(file);
        setPdfPageNumber(1);
        if (pdfAction === 'organize') {
          setOrganizePageOrder([]);
          setOrganizeRotations({});
        }
        void renderPdfPage(file, 1);
        if (pdfAction === 'compress') {
          const originalSize = pdfFiles[0].size;
          const reduction = originalSize ? Math.round((1 - blob.size / originalSize) * 100) : 0;
          const targetSummary = targetSizeBytes === null
            ? ''
            : ` Target met: ${formatSize(blob.size)} is within the ${formatSize(targetSizeBytes)} maximum.`;
          const rasterSummary = response.headers.get('X-Compression-Mode') === 'rasterized'
            ? ' Pages were flattened to images, so text is no longer searchable or editable.'
            : '';
          setPdfResult(`${reduction > 0
            ? `Compression complete: ${formatSize(originalSize)} → ${formatSize(blob.size)} (${reduction}% smaller).`
            : `This PDF was already optimized. The result is ${formatSize(blob.size)}.`}${targetSummary}${rasterSummary}`);
        } else {
          setPdfResult('Your edited PDF is ready to preview. Choose what you would like to do next.');
        }
        const messages: Record<PdfAction, string> = {
          info: 'I found the details you need.',
          merge: 'Great job! I combined your PDFs. Take a look at the preview, then save or download it when you’re happy.',
          split: 'Nice work! Your selected pages are ready to review. You can save, download or discard them.',
          rotate: 'All set! Your rotated pages are ready for a quick look.',
          'remove-pages': 'Your updated PDF is ready to preview. Check it over before saving or downloading.',
          'extract-pages': 'Great choice! Your extracted pages are ready to review.',
          organize: 'Your reordered PDF is ready to preview. Check the page order and rotations before saving.',
          protect: 'Your protected PDF is ready. Preview it, then choose where to keep it.',
          unlock: 'Your unlocked PDF is ready. Have a look before saving or downloading.',
          text: 'I pulled the readable text out for you.',
          compress: 'Your optimized PDF is ready to preview. Take a look before you save it.',
          flip: `Your PDF is flipped ${pdfFlipDirection}. Review the centered preview, then save or download it.`,
        };
        encourageUser(messages[pdfAction]);
      }
    } catch (error) {
      setPdfResult(error instanceof Error ? error.message : 'PDF operation failed.');
    } finally {
      setPdfBusy(false);
      setPdfProcessingMessage('');
    }
  }

  async function runConversion() {
    if (!activeConversion || !conversionFile || !token || conversionBusy) return;
    setConversionBusy(true);
    setPdfBusy(true);
    setPdfProcessingMessage(`Converting ${conversionFile.name} with ${activeConversion.name}…`);
    setPdfOutput(null);
    setPdfResult('');
    setPdfFiles([]);
    setEditorPdfFile(null);
    setPdfPageImage('');
    setPdfAction('info');
    setPage('PDF Studio');
    setConversionError('');
    setConversionMessage('');
    try {
      const form = new FormData();
      form.append('file', conversionFile);
      form.append('output_format', activeConversion.outputFormat);
      const response = await fetch(`${API}/api/pdf/convert`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const fallbackExtension = blob.type === 'application/zip'
        ? 'zip'
        : blob.type === 'application/pdf'
          ? 'pdf'
          : activeConversion.outputFormat;
      const fileName = response.headers.get('Content-Disposition')
        ?.match(/filename="?([^";]+)"?/i)?.[1] ?? `vertex-converted.${fallbackExtension}`;
      const file = new File([blob], fileName, { type: blob.type });
      const url = URL.createObjectURL(file);
      setPdfOutput({ file, url });
      setPdfResult(`${activeConversion.name} is ready in PDF Studio. Review it, then save or download the result.`);
      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        setPdfFiles([file]);
        setEditorPdfFile(file);
        setPdfPageNumber(1);
        void renderPdfPage(file, 1);
      }
      if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
      setConversionOutput(null);
      setConversionPreviewText('');
      encourageUser(`${activeConversion.name} is complete. Your result is centered in PDF Studio and ready to review.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The file could not be converted.';
      setConversionError(message);
      setPdfResult(message);
    } finally {
      setConversionBusy(false);
      setPdfBusy(false);
      setPdfProcessingMessage('');
    }
  }

  async function saveConversionOutput() {
    if (!conversionOutput || !token || conversionSaveBusy) return;
    const form = new FormData();
    form.append('file', conversionOutput.file);
    setConversionSaveBusy(true);
    try {
      const response = await fetch(`${API}/api/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const saved = await response.json() as { name: string };
      setConversionMessage(`Saved “${saved.name}” to your workspace.`);
      await loadDocuments();
    } catch (error) {
      setConversionError(error instanceof Error ? error.message : 'The converted file could not be saved.');
    } finally {
      setConversionSaveBusy(false);
    }
  }

  function discardConversionOutput() {
    if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
    setConversionOutput(null);
    setConversionPreviewText('');
    setConversionMessage('');
  }

  async function addScanPages(files: File[]) {
    if (!files.length) return;
    const invalid = files.find((file) => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024);
    if (invalid) {
      setConversionError(`${invalid.name}: choose a PNG, JPEG, or WebP image up to 10 MB.`);
      return;
    }
    const totalBytes = [...scanPages.map((page) => page.file.size), ...files.map((file) => file.size)]
      .reduce((total, size) => total + size, 0);
    if (scanPages.length + files.length > 30 || totalBytes > 50 * 1024 * 1024) {
      setConversionError('A scan can contain up to 30 images and 50 MB total.');
      return;
    }
    try {
      const added = await Promise.all(files.map(async (file, index) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}-${index}`,
        file,
        preview: await readImageData(file),
        rotation: 0,
      })));
      setScanPages((current) => [...current, ...added]);
      setConversionError('');
      if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
      setConversionOutput(null);
      setConversionMessage('');
    } catch (error) {
      setConversionError(error instanceof Error ? error.message : 'One or more scan images could not be opened.');
    }
  }

  function moveScanPageTo(pageId: string, targetIndex: number) {
    setScanPages((current) => {
      const sourceIndex = current.findIndex((page) => page.id === pageId);
      if (sourceIndex < 0 || targetIndex < 0 || targetIndex >= current.length) return current;
      const next = [...current];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
  }

  function rotateScanPage(pageId: string) {
    setScanPages((current) => current.map((page) => page.id === pageId
      ? { ...page, rotation: (page.rotation + 90) % 360 }
      : page));
  }

  function removeScanPage(pageId: string) {
    setScanPages((current) => current.filter((page) => page.id !== pageId));
    if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
    setConversionOutput(null);
    setConversionMessage('');
  }

  async function createScanPdf() {
    if (!token || !scanPages.length || scanBusy) return;
    setScanBusy(true);
    setConversionError('');
    setConversionMessage('');
    try {
      const form = new FormData();
      scanPages.forEach((page) => form.append('files', page.file));
      form.append('rotations', scanPages.map((page) => String(page.rotation)).join(','));
      const response = await fetch(`${API}/api/pdf/scan`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const file = new File([blob], 'vertex-scanned.pdf', { type: blob.type || 'application/pdf' });
      if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
      setConversionOutput({ file, url: URL.createObjectURL(file) });
      setConversionPreviewText('');
      setConversionMessage(`${scanPages.length} page${scanPages.length === 1 ? '' : 's'} are ready. Review, save, or download your scanned PDF.`);
    } catch (error) {
      setConversionError(error instanceof Error ? error.message : 'The scanned PDF could not be created.');
    } finally {
      setScanBusy(false);
    }
  }

  function renderScanPanel() {
    return (
      <section className="panel conversion-panel scan-panel">
        <div className="section-title">
          <div><h2>Scan to PDF</h2><p>Capture pages with your camera or add images, then arrange them into one PDF.</p></div>
          <button onClick={() => {
            if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
            setScanMode(false);
            setScanPages([]);
            setConversionOutput(null);
            setConversionError('');
            setConversionMessage('');
          }}>Clear selection</button>
        </div>
        <label className="file-drop scan-file-picker" onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
          event.preventDefault();
          void addScanPages(Array.from(event.dataTransfer.files));
        }}>
          <ImagePlus size={22} />
          <b>Add photos or capture a page</b>
          <small>PNG, JPEG or WebP · up to 10 MB each · 30 pages maximum</small>
          <input ref={scanFileInputRef} type="file" accept="image/png,image/jpeg,image/webp" capture="environment" multiple onChange={(event) => {
            void addScanPages(Array.from(event.target.files ?? []));
            event.target.value = '';
          }} />
        </label>
        {!!scanPages.length && <div className="scan-page-list" aria-label="Scanned pages">
          {scanPages.map((page, index) => (
            <article className="scan-page-card" key={page.id} draggable onDragStart={(event) => {
              setScanDraggedPage(page.id);
              event.dataTransfer.setData('text/plain', page.id);
            }} onDragEnd={() => setScanDraggedPage(null)} onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
              event.preventDefault();
              const draggedId = event.dataTransfer.getData('text/plain') || scanDraggedPage;
              if (draggedId) moveScanPageTo(draggedId, index);
              setScanDraggedPage(null);
            }}>
              <img src={page.preview} alt={`Scan page ${index + 1}`} style={{ transform: `rotate(${page.rotation}deg)` }} />
              <div className="scan-page-description"><b>Page {index + 1}</b><small>{page.file.name}</small></div>
              <div className="scan-page-actions">
                <button disabled={index === 0} onClick={() => moveScanPageTo(page.id, index - 1)} aria-label={`Move scan page ${index + 1} up`}>Up</button>
                <button disabled={index === scanPages.length - 1} onClick={() => moveScanPageTo(page.id, index + 1)} aria-label={`Move scan page ${index + 1} down`}>Down</button>
                <button onClick={() => rotateScanPage(page.id)} aria-label={`Rotate scan page ${index + 1}`}>Rotate {page.rotation}°</button>
                <button className="remove-page-button" onClick={() => removeScanPage(page.id)} aria-label={`Remove scan page ${index + 1}`}>Remove</button>
              </div>
            </article>
          ))}
        </div>}
        <button className="primary full-button" disabled={!token || !scanPages.length || scanBusy} onClick={() => void createScanPdf()}>
          {scanBusy ? 'Creating PDF…' : `Create PDF${scanPages.length ? ` · ${scanPages.length} page${scanPages.length === 1 ? '' : 's'}` : ''}`}
        </button>
        {!token && <p className="inline-hint">Sign in to create and save a scanned PDF.</p>}
        {conversionMessage && <p className="operation-notice" role="status">{conversionMessage}</p>}
        {conversionError && <p className="ai-error" role="alert">{conversionError}</p>}
        {conversionOutput && <div className="conversion-result">
          <iframe className="conversion-preview-frame" src={conversionOutput.url} title={`Preview of ${conversionOutput.file.name}`} />
          <div className="conversion-result-actions">
            <button className="primary" disabled={!token || conversionSaveBusy} onClick={() => void saveConversionOutput()}><Save size={15} />{conversionSaveBusy ? 'Saving…' : 'Save to workspace'}</button>
            <a href={conversionOutput.url} download={conversionOutput.file.name}><Download size={15} /> Download</a>
            <button className="discard-button" onClick={discardConversionOutput}><Trash2 size={15} /> Delete preview</button>
          </div>
        </div>}
      </section>
    );
  }

  async function saveFileToWorkspace(file: File) {
    const data = new FormData();
    data.append('file', file);
    const response = await fetch(`${API}/api/documents/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: data,
    });
    if (!response.ok) throw new Error(await responseError(response));
    const saved = await response.json() as { name: string };
    await loadDocuments();
    return saved.name;
  }

  function triggerDownload(file: File, url: string) {
    const link = document.createElement('a');
    link.href = url;
    link.download = file.name;
    link.rel = 'noopener';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  async function savePdfOutput() {
    if (!pdfOutput || !token || pdfSaveBusy) return;
    setPdfSaveBusy(true);
    try {
      const savedName = await saveFileToWorkspace(pdfOutput.file);
      setPdfResult(`Saved “${savedName}” to your workspace. You can still download it or discard this preview.`);
      encourageUser(`Perfect! “${savedName}” is saved in your workspace. You can find it again anytime.`);
    } catch (error) {
      setPdfResult(error instanceof Error ? error.message : 'Could not save this file to your workspace.');
    } finally {
      setPdfSaveBusy(false);
    }
  }

  function downloadPdfOutput() {
    if (!pdfOutput) return;
    triggerDownload(pdfOutput.file, pdfOutput.url);
    setPdfResult(`Downloaded “${pdfOutput.file.name}”. Your preview is still here if you want to save it to your workspace too.`);
    encourageUser('Your file is downloaded and ready to use. Great work!');
  }

  function discardPdfOutput() {
    if (!pdfOutput) return;
    setPdfOutput(null);
    setPdfResult('Preview deleted. Your original file is unchanged, so you can try again anytime.');
    encourageUser('No worries! I cleared the temporary result, and your original file is safe. Ready when you are!');
  }

  function pushEditorHistory() {
    const canvas = drawingCanvasRef.current;
    const snapshot: EditorSnapshot = {
      text: editorText,
      drawing: canvas?.toDataURL('image/png') ?? '',
      hasDrawing: drawingHistory.length > 0,
    };
    setEditorUndoHistory((history) => [...history.slice(-39), snapshot]);
    setEditorRedoHistory([]);
  }

  function updateEditorText(value: string) {
    pushEditorHistory();
    setEditorText(value);
  }

  async function saveEditor() {
    const hasEdits = Boolean(editorText.trim() || editorImagePreview || drawingHistory.length);
    if (pdfOutput && !hasEdits) {
      await savePdfOutput();
      return;
    }
    if (!token || pdfSaveBusy || editorBusy) return;
    if (editorPdfFile && !hasEdits) {
      setPdfSaveBusy(true);
      try {
        const savedName = await saveFileToWorkspace(editorPdfFile);
        setPdfResult(`Saved “${savedName}” to your workspace.`);
      } catch (error) {
        setPdfResult(error instanceof Error ? error.message : 'Could not save this file to your workspace.');
      } finally {
        setPdfSaveBusy(false);
      }
      return;
    }
    await exportEditor({ save: true });
  }

  async function downloadEditor() {
    const hasEdits = Boolean(editorText.trim() || editorImagePreview || drawingHistory.length);
    if (pdfOutput && !hasEdits) {
      downloadPdfOutput();
      return;
    }
    if (editorPdfFile && !hasEdits) {
      const url = URL.createObjectURL(editorPdfFile);
      triggerDownload(editorPdfFile, url);
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setPdfResult(`Downloaded “${editorPdfFile.name}”.`);
      return;
    }
    await exportEditor({ download: true });
  }

  function resetEditor() {
    setEditorText('');
    setEditorUndoHistory([]);
    setEditorRedoHistory([]);
    setEditorImageSource('');
    setEditorImageName('');
    setEditorImageSelected(false);
    setEditorImagePosition({ x: 50, y: 62 });
    setEditorImageRotation(0);
    setEditorCropLeft(0);
    setEditorCropRight(0);
    setEditorCropTop(0);
    setEditorCropBottom(0);
    setPdfFiles([]);
    setEditorPdfFile(null);
    setPdfPageImage('');
    setPdfPageNumber(1);
    setPdfPageCount(1);
    setPdfPageDimensions({ width: 1000, height: 1414 });
    setPdfOutput(null);
    setPdfResult('');
    setPdfRenderError('');
    setEditorError('');
    setDrawingHistory([]);
    const canvas = drawingCanvasRef.current;
    const context = canvas?.getContext('2d');
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    encourageUser('A fresh page is ready. Add text, a picture, or a few marks whenever you like.');
  }

  async function renderPdfPage(file: File, pageNumber: number) {
    if (!token) {
      setPdfRenderError('Sign in to edit or preview PDF pages in the workspace.');
      return;
    }
    setPdfRendering(true);
    setPdfRenderError('');
    const form = new FormData();
    form.append('file', file);
    form.append('page', String(pageNumber));
    try {
      const response = await fetch(`${API}/api/pdf/preview`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { page_number: number; page_count: number; width: number; height: number; image_data: string };
      setEditorPdfFile(file);
      setPdfPageImage(`data:image/png;base64,${result.image_data}`);
      setPdfPageNumber(result.page_number);
      setPdfPageCount(result.page_count);
      setPdfPageDimensions({ width: result.width, height: result.height });
      if (pdfAction === 'organize') {
        setOrganizePageOrder((current) => current.length === result.page_count
          ? current
          : Array.from({ length: result.page_count }, (_, index) => index + 1));
      }
    } catch (error) {
      setPdfRenderError(error instanceof Error ? error.message : 'The PDF page could not be opened.');
    } finally {
      setPdfRendering(false);
    }
  }

  function changePdfPage(pageNumber: number) {
    if (!editorPdfFile || pageNumber < 1 || pageNumber > pdfPageCount || pageNumber === pdfPageNumber) return;
    if (editorText.trim() || editorImageSource || drawingHistory.length) {
      setPdfRenderError('Apply your current page edits as a PDF before moving to another page.');
      return;
    }
    setEditorUndoHistory([]);
    setEditorRedoHistory([]);
    setDrawingHistory([]);
    setPdfPageNumber(pageNumber);
    void renderPdfPage(editorPdfFile, pageNumber);
  }

  function selectPdfFiles(files: File[]) {
    const selected = files.filter((file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'));
    if (!selected.length) {
      setPdfResult('Choose a PDF file to open in the workspace.');
      return;
    }
    if (selected.some((file) => file.size > 50 * 1024 * 1024)) {
      setPdfResult('Each PDF must be 50 MB or smaller.');
      return;
    }
    const chosen = pdfAction === 'merge' ? selected : selected.slice(0, 1);
    setPdfFiles(chosen);
    setEditorPdfFile(chosen[0]);
    setEditorText('');
    setEditorUndoHistory([]);
    setEditorRedoHistory([]);
    setEditorImageSource('');
    setEditorImageName('');
    setEditorImageSelected(false);
    setDrawingHistory([]);
    setPdfPageNumber(1);
    setOrganizePageOrder([]);
    setOrganizeRotations({});
    setPdfOutput(null);
    setPdfResult('');
    setPdfRenderError('');
    void renderPdfPage(chosen[0], 1);
  }

  async function loadEditorImage(file?: File) {
    if (!file) return;
    const allowed = ['image/png', 'image/jpeg', 'image/webp'];
    if (!allowed.includes(file.type) || file.size > 10 * 1024 * 1024) {
      setEditorError('Choose a PNG, JPEG, or WebP image under 10 MB.');
      return;
    }
    try {
      setEditorImageSource(await readImageData(file));
      setEditorImageName(file.name);
      setEditorImageSelected(false);
      setEditorImagePosition({ x: 50, y: 62 });
      setEditorImageRotation(0);
      setEditorCropLeft(0);
      setEditorCropRight(0);
      setEditorCropTop(0);
      setEditorCropBottom(0);
      setEditorTool('text');
      setPdfOutput(null);
      setPdfResult('');
      setEditorError('');
      encourageUser(`“${file.name}” is on your page. Drag it into place, or click it for crop and rotation tools.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : 'Could not load this image.');
    }
  }

  function editorImagePointerDown(event: ReactPointerEvent<HTMLImageElement>) {
    event.preventDefault();
    event.stopPropagation();
    setEditorImageSelected(true);
    const page = editorPageRef.current?.getBoundingClientRect();
    const image = event.currentTarget.getBoundingClientRect();
    if (!page) return;
    imageDragOffset.current = {
      x: (event.clientX - (image.left + image.width / 2)) / page.width * 100,
      y: (event.clientY - (image.top + image.height / 2)) / page.height * 100,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function editorPagePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!imageDragOffset.current) return;
    const page = editorPageRef.current?.getBoundingClientRect();
    if (!page) return;
    const x = (event.clientX - page.left) / page.width * 100 - imageDragOffset.current.x;
    const y = (event.clientY - page.top) / page.height * 100 - imageDragOffset.current.y;
    setEditorImagePosition({ x: Math.max(4, Math.min(96, x)), y: Math.max(4, Math.min(96, y)) });
  }

  function editorPagePointerUp() {
    imageDragOffset.current = null;
  }

  function restoreDrawing(data: string) {
    const canvas = drawingCanvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!data) return;
    const image = new Image();
    image.onload = () => context.drawImage(image, 0, 0, canvas.width, canvas.height);
    image.src = data;
  }

  function undoEditor() {
    const canvas = drawingCanvasRef.current;
    const previous = editorUndoHistory[editorUndoHistory.length - 1];
    if (!previous) return;
    setEditorRedoHistory((history) => [...history, {
      text: editorText,
      drawing: canvas?.toDataURL('image/png') ?? '',
      hasDrawing: drawingHistory.length > 0,
    }]);
    setEditorUndoHistory((history) => history.slice(0, -1));
    setEditorText(previous.text);
    setDrawingHistory(previous.hasDrawing ? [previous.drawing] : []);
    restoreDrawing(previous.drawing);
  }

  function redoEditor() {
    const canvas = drawingCanvasRef.current;
    const next = editorRedoHistory[editorRedoHistory.length - 1];
    if (!next) return;
    setEditorUndoHistory((history) => [...history, {
      text: editorText,
      drawing: canvas?.toDataURL('image/png') ?? '',
      hasDrawing: drawingHistory.length > 0,
    }]);
    setEditorRedoHistory((history) => history.slice(0, -1));
    setEditorText(next.text);
    setDrawingHistory(next.hasDrawing ? [next.drawing] : []);
    restoreDrawing(next.drawing);
  }

  function editorCanvasPoint(event: ReactPointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) / bounds.width * canvas.width,
      y: (event.clientY - bounds.top) / bounds.height * canvas.height,
    };
  }

  function startEditorStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (editorTool === 'text') return;
    event.preventDefault();
    const canvas = event.currentTarget;
    const context = canvas.getContext('2d');
    if (!context) {
      setEditorError('Drawing is not available in this browser.');
      return;
    }
    pushEditorHistory();
    setDrawingHistory((history) => [...history.slice(-39), canvas.toDataURL('image/png')]);
    const point = editorCanvasPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.globalCompositeOperation = editorTool === 'eraser' ? 'destination-out' : 'source-over';
    context.globalAlpha = editorTool === 'highlight' ? 0.2 : editorTool === 'pencil' ? 0.7 : 1;
    context.strokeStyle = editorColor;
    context.lineWidth = editorTool === 'highlight' ? Math.max(8, editorBrushSize * 2) : editorTool === 'eraser' ? editorBrushSize * 4 : editorTool === 'pencil' ? editorBrushSize * 0.65 : editorBrushSize;
    context.lineTo(point.x + 0.01, point.y + 0.01);
    context.stroke();
    drawingPointer.current = true;
    canvas.setPointerCapture(event.pointerId);
  }

  function continueEditorStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drawingPointer.current) return;
    const canvas = event.currentTarget;
    const context = canvas.getContext('2d');
    if (!context) return;
    const point = editorCanvasPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
  }

  function endEditorStroke() {
    drawingPointer.current = false;
  }

  async function editorPagePreview() {
    const preview = document.createElement('canvas');
    preview.width = 1000;
    preview.height = 1414;
    const context = preview.getContext('2d');
    if (!context) throw new Error('Document export is not available in this browser.');
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, preview.width, preview.height);
    const drawing = drawingCanvasRef.current;
    if (drawing) context.drawImage(drawing, 0, 0, preview.width, preview.height);
    drawEditorText(context, preview.width, preview.height, editorText);
    if (editorImagePreview) {
      const image = await loadImage(editorImagePreview);
      const scale = Math.min(320 / image.width, 390 / image.height, 1);
      const width = image.width * scale;
      const height = image.height * scale;
      const centerX = editorImagePosition.x / 100 * preview.width;
      const centerY = editorImagePosition.y / 100 * preview.height;
      context.drawImage(image, centerX - width / 2, centerY - height / 2, width, height);
    }
    return preview.toDataURL('image/png').split(',')[1];
  }

  async function editorPdfOverlay() {
    const overlay = document.createElement('canvas');
    overlay.width = pdfPageDimensions.width;
    overlay.height = pdfPageDimensions.height;
    const context = overlay.getContext('2d');
    if (!context) throw new Error('Document editing is not available in this browser.');
    const scale = overlay.width / 1000;
    const drawing = drawingCanvasRef.current;
    if (drawing) context.drawImage(drawing, 0, 0, overlay.width, overlay.height);
    drawEditorText(context, overlay.width, overlay.height, editorText);
    if (editorImagePreview) {
      const image = await loadImage(editorImagePreview);
      const imageScale = Math.min(320 * scale / image.width, 390 * scale / image.height, 1);
      const width = image.width * imageScale;
      const height = image.height * imageScale;
      const centerX = editorImagePosition.x / 100 * overlay.width;
      const centerY = editorImagePosition.y / 100 * overlay.height;
      context.drawImage(image, centerX - width / 2, centerY - height / 2, width, height);
    }
    return overlay.toDataURL('image/png').split(',')[1];
  }

  async function exportEditor(options: { save?: boolean; download?: boolean } = {}) {
    if (!token) {
      setEditorError('Sign in to export documents to the backend.');
      return;
    }
    const canvas = drawingCanvasRef.current;
    const hasDrawing = Boolean(canvas && drawingHistory.length);
    if (editorExportFormat === 'txt' && (editorImagePreview || hasDrawing)) {
      setEditorError('TXT keeps text only. Choose PDF or DOCX to include the image or annotations.');
      return;
    }
    setEditorBusy(true);
    if (options.save) setPdfSaveBusy(true);
    setEditorError('');
    try {
      let response: Response;
      if (editorPdfFile && editorExportFormat === 'pdf') {
        const form = new FormData();
        form.append('file', editorPdfFile);
        form.append('page', String(pdfPageNumber));
        form.append('overlay_data', await editorPdfOverlay());
        response = await fetch(`${API}/api/pdf/annotate`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
      } else if (editorPdfFile) {
        if (editorText.trim() || editorImagePreview || hasDrawing) {
          throw new Error('To keep edits on the opened PDF, export as PDF. DOCX and TXT conversions extract the original file content.');
        }
        const form = new FormData();
        form.append('file', editorPdfFile);
        form.append('output_format', editorExportFormat);
        response = await fetch(`${API}/api/pdf/convert`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
      } else {
        const body: Record<string, string> = { content: editorText, output_format: editorExportFormat, page_size: 'A4' };
        if (editorImagePreview) body.image_data = editorImagePreview.split(',')[1];
        if (editorExportFormat === 'pdf') body.page_preview_data = await editorPagePreview();
        if (editorExportFormat === 'docx' && hasDrawing && canvas) body.drawing_data = canvas.toDataURL('image/png').split(',')[1];
        response = await fetch(`${API}/api/pdf/editor-export`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify(body),
        });
      }
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const file = new File([blob], `vertex-document.${editorExportFormat}`, { type: blob.type });
      const url = URL.createObjectURL(file);
      setPdfOutput({ file, url });
      let resultMessage = `${editorExportFormat.toUpperCase()} export is ready. Review it, then save it to your workspace, download, or discard it.`;
      if (options.save) {
        const savedName = await saveFileToWorkspace(file);
        resultMessage = `Created and saved “${savedName}” to your workspace.`;
      }
      if (options.download) {
        triggerDownload(file, url);
        resultMessage = `Created and downloaded “${file.name}”.`;
      }
      setPdfResult(resultMessage);
      encourageUser(`Your ${editorExportFormat.toUpperCase()} is ready. Take a look before saving or downloading.`);
      if (editorExportFormat === 'pdf') {
        setEditorText('');
        setEditorUndoHistory([]);
        setEditorRedoHistory([]);
        setEditorImageSource('');
        setEditorImageName('');
        setEditorImageSelected(false);
        setDrawingHistory([]);
        setPdfFiles([file]);
        void renderPdfPage(file, editorPdfFile ? pdfPageNumber : 1);
      }
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : 'The document could not be exported.');
    } finally {
      setEditorBusy(false);
      if (options.save) setPdfSaveBusy(false);
    }
  }

  function renderDocuments() {
    if (!token) return <div className="empty-state">Sign in to manage your documents.</div>;
    if (!documents.length) return <div className="empty-state">No documents yet. Upload a PDF or document to get started.</div>;
    return (
      <div className="document-list">
        {documents.map((item) => (
          <div className="document-row" key={item.id}>
            <span className="document-icon"><FileText size={19} /></span>
            <span className="document-name"><b>{item.name}</b><small>{formatSize(item.size)}</small></span>
            <button title={`Download ${item.name}`} onClick={() => void downloadDocument(item)}><Download size={17} /></button>
            <button title={`Delete ${item.name}`} onClick={() => void deleteDocument(item)}><Trash2 size={17} /></button>
          </div>
        ))}
      </div>
    );
  }

  function renderDocumentHistory() {
    const visibleDocuments = documents
      .filter((item) => {
        const extension = item.name.split('.').pop()?.toLowerCase() ?? '';
        const matchesType = historyFilter === 'all'
          || (historyFilter === 'pdf' && extension === 'pdf')
          || (historyFilter === 'word' && ['doc','docx'].includes(extension))
          || (historyFilter === 'text' && ['txt','md'].includes(extension));
        return matchesType && item.name.toLowerCase().includes(historyQuery.trim().toLowerCase());
      })
      .sort((a,b) => historySort === 'name' ? a.name.localeCompare(b.name) : b.size-a.size);
    const totalBytes = documents.reduce((sum,item) => sum + item.size,0);
    const pdfCount = documents.filter((item) => item.name.toLowerCase().endsWith('.pdf')).length;
    return (
      <>
        <PageHeading eyebrow="YOUR PRIVATE LIBRARY" title="Document history" subtitle="Find, organize and reuse the files in your workspace." />
        {renderUploadNextSteps()}
        <div className="history-stat-grid">
          <article><span className="history-stat-icon"><FileText size={17} /></span><span><b>{documents.length}</b><small>Documents</small></span></article>
          <article><span className="history-stat-icon"><BookOpen size={17} /></span><span><b>{pdfCount}</b><small>PDF files</small></span></article>
          <article><span className="history-stat-icon"><ArrowDownToLine size={17} /></span><span><b>{formatSize(totalBytes)}</b><small>Workspace storage</small></span></article>
        </div>
        <section className="panel history-panel">
          <div className="history-panel-heading">
            <div><h2>Your documents</h2><p>{documents.length ? `${documents.length} saved ${documents.length === 1 ? 'file' : 'files'}` : 'Your uploaded files will appear here.'}</p></div>
            <label className="primary button-label"><UploadCloud size={16} /> Upload<input type="file" onChange={(event) => { void uploadDocument(event.target.files?.[0]); event.target.value = ''; }} /></label>
          </div>
          <div className="history-controls">
            <label className="history-search"><Search size={16} /><input value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Search your documents..." /></label>
            <label className="history-sort">Sort by<select value={historySort} onChange={(event) => setHistorySort(event.target.value as 'name' | 'largest')}><option value="name">Name</option><option value="largest">Largest</option></select></label>
          </div>
          <div className="history-filters" role="group" aria-label="Filter documents by type">
            {([['all','All files'],['pdf','PDF'],['word','Word'],['text','Text']] as const).map(([id,label]) => <button key={id} className={historyFilter===id?'active':''} aria-pressed={historyFilter===id} onClick={() => setHistoryFilter(id)}>{label}</button>)}
          </div>
          {!token ? <div className="empty-state">Sign in to view your private document history.</div>
            : !documents.length ? <div className="history-empty"><FileText size={28} /><b>Your workspace is ready</b><span>Upload a PDF or document to start building your library.</span></div>
              : !visibleDocuments.length ? <div className="history-empty"><Search size={26} /><b>No matches found</b><span>Try another search or file type filter.</span></div>
                : <div className="history-card-list">{visibleDocuments.map((item) => {
                  const extension = item.name.split('.').pop()?.toUpperCase() || 'FILE';
                  return (
                    <article className="history-card" key={item.id}>
                      <span className="history-file-icon"><FileText size={20} /><small>{extension}</small></span>
                      <div className="history-file-main"><b title={item.name}>{item.name}</b><small>{extension} document · {formatSize(item.size)}</small></div>
                      <div className="history-card-actions">
                        <button title={`Ask AI about ${item.name}`} onClick={() => { chooseAiDocument(String(item.id)); setPage('AI Documents'); }}><Sparkles size={16} /><span>Use with AI</span></button>
                        <button title={`Download ${item.name}`} onClick={() => void downloadDocument(item)}><Download size={16} /><span>Download</span></button>
                        <button className="history-delete" title={`Delete ${item.name}`} onClick={() => void deleteDocument(item)}><Trash2 size={16} /><span>Delete</span></button>
                      </div>
                    </article>
                  );
                })}</div>}
        </section>
      </>
    );
  }

  function renderAiDocuments() {
    const selectedDocument = documents.find((item) => item.id === selectedAiDoc);
    const selectedLabel = selectedDocument?.name ?? '';
    return (
      <>
        <PageHeading eyebrow="DOCUMENT INTELLIGENCE" title="Your AI document companion" subtitle="Get a clear summary, ask questions about your file, or translate it into another language." />
        <section className="ai-companion-card">
          <span className="ai-companion-character" aria-hidden="true">{companion.emoji}</span>
          <div className="ai-companion-copy"><b>{companion.name} is here to help</b><p role="status" aria-live="polite">{aiCompanionLine}</p></div>
          <button onClick={() => speakText(aiCompanionLine)} title="Read companion message aloud"><Volume2 size={16} /><span>{isSpeaking?'Speaking…':'Listen'}</span></button>
        </section>
        <section className="panel ai-document-picker">
          <div className="ai-document-picker-copy"><span className="eyebrow">CHOOSE A DOCUMENT</span><h2>What would you like to work on?</h2><p>Select a file already in your workspace. Your document stays private to your account.</p></div>
          <div className="ai-document-picker-actions">
            <label className="field-label">Workspace document
              <select value={selectedAiDoc ?? ''} onChange={(event) => chooseAiDocument(event.target.value)} disabled={!documents.length}>
                <option value="">Select a document</option>
                {documents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="primary button-label"><UploadCloud size={16} /> Upload a document<input type="file" accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={async (event) => {
              const file=event.target.files?.[0];
              if (!file || !token) { setAiCompanionLine('Sign in before uploading a document for AI features.'); return; }
              const form=new FormData(); form.append('file',file);
              try {
                const response=await fetch(`${API}/api/documents/upload`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:form});
                if (!response.ok) throw new Error(await responseError(response));
                const uploaded=await response.json() as {id:number;name:string};
                await loadDocuments();
                chooseAiDocument(String(uploaded.id));
                setAiCompanionLine(`“${uploaded.name}” is ready. Choose what you’d like to do with it!`);
              } catch (error) {
                setAiCompanionLine(error instanceof Error ? error.message : 'The document could not be uploaded.');
              }
            }} /></label>
          </div>
          {selectedDocument && <div className="selected-document-chip"><FileText size={16} /><span><b>{selectedLabel}</b><small>{formatSize(selectedDocument.size)} · Your private file</small></span></div>}
          {!token && <p className="inline-hint">Sign in to upload files and use secure AI document features.</p>}
        </section>
        <div className="ai-document-workspace">
          <nav className="ai-mode-tabs" role="tablist" aria-label="AI document actions">
            {([['summary','Summarize',BookOpen],['chat','Ask your document',MessageCircle],['translate','Translate',Languages]] as const).map(([mode,label,Icon]) => <button key={mode} className={aiDocMode===mode?'active':''} role="tab" aria-selected={aiDocMode===mode} onClick={() => {setAiDocMode(mode);setVoiceFeedback('');}}><Icon size={16}/>{label}</button>)}
          </nav>
          <div className="panel ai-document-panel">
            <div className="ai-language-choice"><label className="field-label">Assistant language
              <select value={language} onChange={(event) => void savePreferences({language:event.target.value})}>{languages.map(([code,label]) => <option key={code} value={code}>{label}</option>)}</select>
            </label><small>13 choices, including Tanglish. Voice input and playback use your device’s available language voices.</small></div>
            {!selectedDocument ? <div className="ai-select-prompt"><span>{companion.emoji}</span><b>Pick a document to begin</b><p>Choose an uploaded PDF, DOCX, TXT, or Markdown file above.</p></div>
              : aiDocMode==='summary' ? <div className="ai-summary-workspace">
                <div className="ai-feature-intro"><span className="ai-feature-icon"><BookOpen size={20}/></span><div><h2>A helpful summary, in your language</h2><p>Get the main ideas, key details and action items from <b>{selectedLabel}</b>.</p></div></div>
                <button className="primary ai-action-button" disabled={!token||aiDocSummaryBusy} onClick={() => void summarizeAiDocument()}>{aiDocSummaryBusy?<RefreshCw className="spin" size={16}/>:<Sparkles size={16}/>} {aiDocSummaryBusy?'Reading your document…':'Summarize document'}</button>
                {aiDocSummary && <section className="ai-response-card"><div className="ai-response-heading"><span className="ai-response-avatar">{companion.emoji}</span><span><b>{companion.name}’s summary</b><small>{selectedLabel}</small></span><button aria-label="Read summary aloud" onClick={() => speakText(aiDocSummary)}><Volume2 size={16}/><span>Listen</span></button></div><p>{aiDocSummary}</p></section>}
              </div>
                : aiDocMode==='chat' ? <div className="ai-chat-workspace">
                  <div className="ai-feature-intro"><span className="ai-feature-icon"><MessageCircle size={20}/></span><div><h2>Ask questions about your file</h2><p>Your answers are grounded in <b>{selectedLabel}</b> and reply in the selected assistant language.</p></div></div>
                  <div className="ai-chat-transcript" role="log" aria-live="polite">
                    {!aiDocMessages.length && <div className="ai-chat-welcome"><span>{companion.emoji}</span><div><b>Hi, I’m {companion.name}!</b><p>Ask me to explain a section, find a date, or clarify an idea from this document.</p></div></div>}
                    {aiDocMessages.map((message,index)=><div className={`ai-chat-line ${message.role}`} key={`${message.role}-${index}`}><span className="ai-chat-avatar">{message.role==='assistant'?companion.emoji:'You'}</span><div className="ai-chat-bubble"><p>{message.text}</p>{message.role==='assistant'&&<button aria-label="Read assistant reply aloud" onClick={() => speakText(message.text)}><Volume2 size={14}/> Listen</button>}</div></div>)}
                    {aiDocChatBusy&&<div className="ai-chat-line assistant"><span className="ai-chat-avatar">{companion.emoji}</span><div className="ai-chat-bubble typing-indicator">Thinking it through…</div></div>}
                  </div>
                  <div className="ai-chat-compose"><textarea value={aiDocChatInput} onChange={(event)=>setAiDocChatInput(event.target.value)} onKeyDown={(event)=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();void sendAiDocumentChat();}}} placeholder={`Ask ${selectedLabel} a question…`} aria-label="Message about the selected document" />
                    <button className={isListening?'voice-active':''} aria-label={isListening?'Stop voice input':'Speak your question'} aria-pressed={isListening} onClick={()=>startVoiceInput((text)=>setAiDocChatInput((current)=>[current,text].filter(Boolean).join(' ')))}><Mic size={17}/></button>
                    <button className="primary" aria-label="Send question" disabled={!aiDocChatInput.trim()||aiDocChatBusy} onClick={()=>void sendAiDocumentChat()}><Send size={17}/></button>
                  </div>
                </div>
                  : <div className="ai-translate-workspace">
                    <div className="ai-feature-intro"><span className="ai-feature-icon"><Languages size={20}/></span><div><h2>Translate the whole document</h2><p>Keep the original untouched and get a translated text file you can download.</p></div></div>
                    <div className="translation-language-row ai-translation-language-row">
                      <label className="field-label">From<select value={aiDocSource} onChange={(event)=>setAiDocSource(event.target.value)}><option value="auto">Detect language</option>{languages.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label>
                      <ArrowLeftRight className="translation-arrow" size={18}/>
                      <label className="field-label">To<select value={aiDocTarget} onChange={(event)=>setAiDocTarget(event.target.value)}>{languages.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label>
                    </div>
                    <button className="primary ai-action-button" disabled={!token||aiDocTranslateBusy} onClick={()=>void translateAiDocument()}>{aiDocTranslateBusy?<RefreshCw className="spin" size={16}/>:<Languages size={16}/>} {aiDocTranslateBusy?'Translating document…':'Translate document'}</button>
                    {aiDocTranslation&&<section className="ai-response-card"><div className="ai-response-heading"><span className="ai-response-avatar">{companion.emoji}</span><span><b>Translation ready</b><small>{languages.find(([code])=>code===aiDocTarget)?.[1]}</small></span><button onClick={()=>speakText(aiDocTranslation,aiDocTarget)}><Volume2 size={16}/><span>Listen</span></button></div><p>{aiDocTranslation}</p><button className="download-translation-button" onClick={downloadAiTranslation}><Download size={15}/>Download translated text</button></section>}
                  </div>}
            {!token&&<p className="inline-hint">Sign in to summarize, chat with, or translate your documents. Add an LLM_API_KEY in the backend environment to enable AI.</p>}
            {aiDocError&&<p className="ai-error" role="alert">{aiDocError}</p>}
            {voiceFeedback&&<p className="voice-feedback" role="status">{voiceFeedback}</p>}
          </div>
        </div>
      </>
    );
  }

  function renderPdfStudio() {
    const selectedAction = pdfActions.find((action) => action.id === pdfAction) ?? pdfActions[0];
    const hasPdfCanvas = Boolean(editorPdfFile && pdfPageImage);
    const textTools: { id: EditorTool; label: string; icon: typeof FileText }[] = [
      { id: 'text', label: 'Text', icon: FileText },
      { id: 'highlight', label: 'Highlight', icon: Highlighter },
      { id: 'pen', label: 'Pen', icon: Pen },
      { id: 'pencil', label: 'Pencil', icon: Pencil },
      { id: 'eraser', label: 'Eraser', icon: Eraser },
    ];
    const drawCanvas = drawingCanvasRef.current;
    const hasDrawing = Boolean(drawCanvas && drawingHistory.length);
    const hasEditorWork = Boolean(pdfOutput || pdfFiles.length || editorText.trim() || editorImagePreview || drawingHistory.length);
    return (
      <>
        <PageHeading eyebrow="PDF STUDIO" title="A clear space for document work" subtitle="Edit a new page or run a PDF tool. Results appear here for review before you keep them." />
        <div className="pdf-editor-toolbar">
          <button onClick={resetEditor}><FilePlus2 size={15} /> New page</button>
          <button onClick={() => pdfFileInputRef.current?.click()}><UploadCloud size={15} /> Open PDF</button>
          <input ref={pdfFileInputRef} type="file" accept="application/pdf,.pdf" multiple={pdfAction === 'merge'} onChange={(event) => { selectPdfFiles(Array.from(event.target.files ?? [])); event.target.value = ''; }} />
          <button disabled={!token || pdfSaveBusy || editorBusy || (!pdfOutput && !hasEditorWork)} onClick={() => void saveEditor()}><Save size={15} /> {pdfSaveBusy ? 'Saving…' : 'Save'}</button>
          <button disabled={!editorUndoHistory.length} onClick={undoEditor}><Undo2 size={15} /> Undo</button>
          <button disabled={!editorRedoHistory.length} onClick={redoEditor}><Redo2 size={15} /> Redo</button>
          <select className="editor-format-choice" aria-label="Export format" value={editorExportFormat} onChange={(event) => setEditorExportFormat(event.target.value as ExportFormat)}>
            <option value="pdf">PDF</option><option value="docx">DOCX</option><option value="txt">TXT</option>
          </select>
          <button className="primary" disabled={!token || editorBusy} onClick={() => void exportEditor()}>{editorBusy ? 'Creating…' : `Create ${editorExportFormat.toUpperCase()}`}</button>
          <button disabled={!hasEditorWork || (!token && !editorPdfFile && !pdfOutput)} onClick={() => void downloadEditor()}><Download size={15} /> Download</button>
        </div>
        <div className="pdf-editor-layout">
          <section className="panel pdf-tool-panel">
            <div className="section-title"><div><h2>PDF tools</h2><p>Select an action, choose your file, and review its result in this page.</p></div></div>
            <div className="pdf-tool-grid">
              {pdfActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button className={`pdf-tool-card ${pdfAction === action.id ? 'selected' : ''}`} key={action.id} onClick={() => {
                    setPdfAction(action.id);
                    if (action.id === 'organize' && editorPdfFile) {
                      setOrganizePageOrder(Array.from({ length: pdfPageCount }, (_, index) => index + 1));
                      setOrganizeRotations({});
                    }
                    setPdfOutput(null);
                    setPdfResult('');
                  }}>
                    <span className="tool-icon"><Icon size={18} /></span>
                    <b>{action.name}</b>
                    <small>{action.description}</small>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="panel pdf-editor-canvas">
            <div className="pdf-editor-canvas-heading">
              <b>{pdfOutput?.file.name || pdfFiles[0]?.name || 'Untitled document'}</b>
              <small>{hasPdfCanvas ? `Page ${pdfPageNumber} of ${pdfPageCount}` : 'A4 · 1 page'}</small>
            </div>
            <div className={`editor-stage ${editorDropActive ? 'editor-drop-active' : ''}`} onDragOver={(event) => { event.preventDefault(); setEditorDropActive(true); }} onDragLeave={() => setEditorDropActive(false)} onDrop={(event) => { event.preventDefault(); setEditorDropActive(false); const file = event.dataTransfer.files[0]; if (file?.type === 'application/pdf' || file?.name.toLowerCase().endsWith('.pdf')) selectPdfFiles(Array.from(event.dataTransfer.files)); else void loadEditorImage(file); }}>
              {pdfOutput && pdfOutput.file.type !== 'application/pdf' ? <div className="editor-nonpdf-result"><FileText size={32} /><b>{pdfOutput.file.name} is ready</b><span>Preview is available after you download or open this file.</span></div>
                : hasPdfCanvas || (!pdfSourceUrl && !pdfOutput) ? <div className="editor-page" ref={editorPageRef} style={hasPdfCanvas ? { aspectRatio: `${pdfPageDimensions.width} / ${pdfPageDimensions.height}` } : undefined} onClick={(event) => { if (!(event.target instanceof Element) || !event.target.closest('.editor-page-photo, .editor-image-float-tools')) setEditorImageSelected(false); }} onPointerMove={editorPagePointerMove} onPointerUp={editorPagePointerUp} onPointerCancel={editorPagePointerUp}>
                      {hasPdfCanvas && <img className="editor-page-pdf-bg" src={pdfPageImage} alt={`PDF page ${pdfPageNumber}`} draggable={false} />}
                      <textarea className="editor-page-text" aria-label="Document text" value={editorText} onChange={(event) => updateEditorText(event.target.value)} style={{ pointerEvents: editorTool === 'text' ? 'auto' : 'none' }} placeholder="Click here and start typing…" />
                      {editorImagePreview && <img className={`editor-page-photo ${editorImageSelected ? 'selected' : ''}`} src={editorImagePreview} alt={editorImageName || 'Inserted document image'} draggable={false} style={{ left: `${editorImagePosition.x}%`, top: `${editorImagePosition.y}%`, transform: 'translate(-50%, -50%)' }} onClick={() => setEditorImageSelected(true)} onPointerDown={editorImagePointerDown} onPointerUp={editorPagePointerUp} />}
                      {editorImageSelected && editorImagePreview && <div className="editor-image-float-tools" style={{ left: `${Math.min(editorImagePosition.x, 78)}%`, top: `${Math.max(3, editorImagePosition.y - 7)}%` }} onPointerDown={(event) => event.stopPropagation()}>
                        <button title="Crop image" aria-label="Open crop options" onClick={() => setEditorTool('text')}><Crop size={14} /></button>
                        <button title="Rotate image 90 degrees" aria-label="Rotate image 90 degrees" onClick={() => setEditorImageRotation((rotation) => (rotation + 90) % 360)}><RotateCw size={14} /></button>
                        <button title="Align image left" aria-label="Align image left" onClick={() => setEditorImagePosition((position) => ({ ...position, x: 18 }))}><AlignLeft size={14} /></button>
                        <button title="Center image" aria-label="Center image" onClick={() => setEditorImagePosition((position) => ({ ...position, x: 50 }))}><AlignCenter size={14} /></button>
                        <button title="Align image right" aria-label="Align image right" onClick={() => setEditorImagePosition((position) => ({ ...position, x: 82 }))}><AlignRight size={14} /></button>
                        <button title="Remove image" aria-label="Remove image" onClick={() => { setEditorImageSource(''); setEditorImageSelected(false); }}><Trash2 size={14} /></button>
                      </div>}
                      <canvas className={`editor-page-drawing ${editorTool !== 'text' ? 'interactive' : ''}`} ref={drawingCanvasRef} aria-label="Drawing and highlighter canvas" onPointerDown={startEditorStroke} onPointerMove={continueEditorStroke} onPointerUp={endEditorStroke} onPointerCancel={endEditorStroke} onPointerLeave={endEditorStroke} style={{ pointerEvents: editorTool === 'text' ? 'none' : 'auto' }} />
                    </div> : null}
                    {!hasPdfCanvas && (pdfSourceUrl || pdfOutput?.file.type === 'application/pdf') && <iframe className="editor-pdf-frame" src={pdfOutput?.url || pdfSourceUrl} title="Preview of the selected PDF" />}
              {pdfBusy && <div className="pdf-processing-overlay" role="status" aria-live="polite">
                <span className="pdf-processing-spinner"><RefreshCw className="spin" size={22} /></span>
                <b>{pdfProcessingMessage || 'Preparing your document…'}</b>
                <small>Your result will appear here as soon as processing is complete.</small>
                <span className="pdf-processing-track"><i /></span>
              </div>}
            </div>
            {pdfOutput && <div className="pdf-output-actions">
              <button className="primary" disabled={!token || pdfSaveBusy || editorBusy} onClick={() => void saveEditor()}><Save size={15} /> {pdfSaveBusy ? 'Saving…' : 'Save to workspace'}</button>
              <button disabled={editorBusy} onClick={() => void downloadEditor()}><Download size={15} /> Download</button>
              <button className="discard-button" onClick={discardPdfOutput}><Trash2 size={15} /> Delete preview</button>
              <small>{pdfResult || 'Your original file is unchanged until you choose to save the result.'}</small>
            </div>}
            {!pdfOutput && pdfResult && <pre className="operation-result">{pdfResult}</pre>}
            {editorError && <p className="ai-error" role="alert">{editorError}</p>}
          </section>

          <aside className="panel pdf-run-panel">
            <div className="section-title"><div><h2>{selectedAction.name}</h2><p>{selectedAction.description}</p></div></div>
            <label className="file-drop" onClick={() => pdfFileInputRef.current?.click()}>
              <UploadCloud size={22} />
              <b>{pdfFiles.length ? pdfFiles.map((file) => file.name).join(', ') : pdfAction === 'merge' ? 'Choose two or more PDF files' : 'Choose a PDF file'}</b>
              <small>{pdfFiles.length ? `${pdfFiles.length} file${pdfFiles.length === 1 ? '' : 's'} selected` : 'PDF files only'}</small>
            </label>
            {editorPdfFile && <div className="editor-page-navigation">
              <button disabled={pdfRendering || pdfPageNumber <= 1} onClick={() => changePdfPage(pdfPageNumber - 1)}>Previous</button>
              <span>{pdfRendering ? 'Opening…' : `${pdfPageNumber} / ${pdfPageCount}`}</span>
              <button disabled={pdfRendering || pdfPageNumber >= pdfPageCount} onClick={() => changePdfPage(pdfPageNumber + 1)}>Next</button>
            </div>}
            {pdfAction === 'organize' && editorPdfFile && <section className="organize-page-list" aria-label="Organize PDF pages">
              <div><b>Keep and order pages</b><small>Use the controls to rearrange, rotate, or remove pages.</small></div>
              {organizePageOrder.map((pageNumber, index) => (
                <article className={`organize-page-row ${pdfPageNumber === pageNumber ? 'selected' : ''}`} key={pageNumber}>
                  <button className="organize-page-number" onClick={() => changePdfPage(pageNumber)} aria-label={`Preview page ${pageNumber}`}>Page {pageNumber}</button>
                  <div className="organize-page-controls">
                    <button disabled={index === 0} onClick={() => moveOrganizePage(pageNumber, -1)} aria-label={`Move page ${pageNumber} up`}>Up</button>
                    <button disabled={index === organizePageOrder.length - 1} onClick={() => moveOrganizePage(pageNumber, 1)} aria-label={`Move page ${pageNumber} down`}>Down</button>
                    <button onClick={() => rotateOrganizePage(pageNumber)} aria-label={`Rotate page ${pageNumber}`}>Rotate {organizeRotations[pageNumber] ?? 0}°</button>
                    <button className="remove-page-button" disabled={organizePageOrder.length === 1} onClick={() => removeOrganizePage(pageNumber)} aria-label={`Remove page ${pageNumber}`}>Remove</button>
                  </div>
                </article>
              ))}
            </section>}
            {pdfRenderError && <p className="ai-error" role="alert">{pdfRenderError}</p>}
            {['split', 'remove-pages', 'extract-pages'].includes(pdfAction) && <label className="field-label">Page numbers<input value={pdfPages} onChange={(event) => setPdfPages(event.target.value)} placeholder="e.g. 1, 3, 5" /></label>}
            {pdfAction === 'rotate' && <label className="field-label">Rotation<select value={pdfDegrees} onChange={(event) => setPdfDegrees(event.target.value)}><option value="90">90° clockwise</option><option value="180">180°</option><option value="270">270° clockwise</option></select></label>}
            {['protect', 'unlock'].includes(pdfAction) && <label className="field-label">PDF password<input type="password" value={pdfPassword} onChange={(event) => setPdfPassword(event.target.value)} placeholder="Enter password" /></label>}
            {pdfAction === 'compress' && <>
              <label className="field-label" htmlFor="pdf-compression-target">Maximum output size <small>Optional. Leave empty for standard compression.</small></label>
              <div className="compression-size-fields">
                <input id="pdf-compression-target" type="number" min="0.001" step="any" max={pdfCompressionUnit === 'mb' ? 50 : 51200} value={pdfCompressionTarget} onChange={(event) => setPdfCompressionTarget(event.target.value)} placeholder="e.g. 500" />
                <select aria-label="Compression target unit" value={pdfCompressionUnit} onChange={(event) => setPdfCompressionUnit(event.target.value as 'kb' | 'mb')}>
                  <option value="kb">KB</option>
                  <option value="mb">MB</option>
                </select>
              </div>
              <p className="inline-hint">The target is a maximum. Text stays searchable by default; very small targets may not be possible without reducing quality.</p>
              {pdfCompressionTarget.trim() && <label className="compression-raster-option">
                <input type="checkbox" checked={pdfRasterizeIfNeeded} onChange={(event) => setPdfRasterizeIfNeeded(event.target.checked)} />
                <span>Allow flattening pages if needed <small>Reduces searchability and text editing.</small></span>
              </label>}
            </>}
            {pdfAction === 'flip' && <label className="field-label">Flip direction<select value={pdfFlipDirection} onChange={(event) => setPdfFlipDirection(event.target.value as 'horizontal' | 'vertical')}><option value="horizontal">Horizontal · mirror left to right</option><option value="vertical">Vertical · mirror top to bottom</option></select></label>}
            <button className="primary full-button" disabled={pdfBusy || !token} onClick={() => void runPdfAction()}>{pdfBusy ? 'Working…' : 'Run operation'}</button>
            {!token && <p className="inline-hint">Sign in to run backend PDF operations.</p>}
            <hr className="editor-workspace-divider" />
            <div className="section-title"><div><h2>Page tools</h2><p>Type, mark up, and place a picture on your page.</p></div></div>
            <div className="editor-tool-group" role="group" aria-label="Document editing tools">
              {textTools.map(({ id, label, icon: Icon }) => <button key={id} className={editorTool === id ? 'active' : ''} aria-pressed={editorTool === id} onClick={() => setEditorTool(id)}><Icon size={14} />{label}</button>)}
            </div>
            {editorTool !== 'text' && <label className="editor-range-label">Brush size · {editorBrushSize}<input type="range" min="1" max="24" value={editorBrushSize} onChange={(event) => setEditorBrushSize(Number(event.target.value))} /></label>}
            <div className="editor-color-row" aria-label="Drawing colors">
              {['#fff2a1', '#ffdbe1', '#d9f0df', '#dceaff', '#252b28'].map((color) => <button key={color} type="button" className={editorColor === color ? 'active' : ''} style={{ backgroundColor: color }} aria-label={`Set drawing color ${color}`} onClick={() => setEditorColor(color)} />)}
              <input type="color" value={editorColor} aria-label="Choose a custom drawing color" onChange={(event) => setEditorColor(event.target.value)} />
            </div>
            <button className="editor-tool-group" onClick={() => imageFileInputRef.current?.click()}><ImagePlus size={15} /> Insert image</button>
            <input ref={imageFileInputRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => { void loadEditorImage(event.target.files?.[0]); event.target.value = ''; }} />
            {editorImagePreview && editorImageSelected && <>
              <p className="editor-file-note">Selected: {editorImageName}. Drag it on the page, or choose crop, rotate, and alignment options.</p>
              <label className="editor-range-label">Crop left<input type="range" min="0" max={95-editorCropRight} value={editorCropLeft} onChange={(event) => setEditorCropLeft(Number(event.target.value))} /></label>
              <label className="editor-range-label">Crop right<input type="range" min="0" max={95-editorCropLeft} value={editorCropRight} onChange={(event) => setEditorCropRight(Number(event.target.value))} /></label>
              <label className="editor-range-label">Crop top<input type="range" min="0" max={95-editorCropBottom} value={editorCropTop} onChange={(event) => setEditorCropTop(Number(event.target.value))} /></label>
              <label className="editor-range-label">Crop bottom<input type="range" min="0" max={95-editorCropTop} value={editorCropBottom} onChange={(event) => setEditorCropBottom(Number(event.target.value))} /></label>
              <div className="editor-tool-group">
                <button onClick={() => setEditorImageRotation((rotation) => (rotation + 270) % 360)}><RotateCw size={14} /> Rotate left</button>
                <button onClick={() => setEditorImageRotation((rotation) => (rotation + 90) % 360)}><RotateCw size={14} /> Rotate right</button>
                <button onClick={() => setEditorImagePosition((position) => ({ ...position, y: 18 }))}>Move to top</button>
                <button onClick={() => { setEditorCropLeft(0); setEditorCropRight(0); setEditorCropTop(0); setEditorCropBottom(0); }}>Reset crop</button>
              </div>
            </>}
            <hr className="editor-workspace-divider" />
            <label className="field-label">Export as<select value={editorExportFormat} onChange={(event) => setEditorExportFormat(event.target.value as ExportFormat)}><option value="pdf">PDF · page layout and marks</option><option value="docx">DOCX · editable text and image</option><option value="txt">TXT · text only</option></select></label>
            <button className="primary full-button" disabled={!token || editorBusy} onClick={() => void exportEditor()}>{editorBusy ? 'Creating…' : `Create ${editorExportFormat.toUpperCase()}`}</button>
            {editorExportFormat === 'docx' && hasDrawing && <p className="editor-file-note">DOCX includes annotations on a following page; PDF preserves the full page layout.</p>}
            {editorExportFormat === 'txt' && (editorImagePreview || hasDrawing) && <p className="editor-file-note">TXT contains text only. Choose PDF or DOCX to include images or marks.</p>}
          </aside>
        </div>
        {selectedTemplate === 'resume' && renderResumeStudioPanel()}
      </>
    );
  }

  function selectAdvancedTool(toolName: string) {
    const config = advancedToolConfigs[toolName.toLowerCase()];
    if (!config) return;
    if (advancedOutput) URL.revokeObjectURL(advancedOutput.url);
    if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
    setSelectedAdvancedTool(toolName);
    setActiveConversion(null);
    setScanMode(false);
    setConversionOutput(null);
    setAdvancedFiles([]);
    setAdvancedOptions(Object.fromEntries((config.fields ?? []).map((field) => [field.key, field.defaultValue ?? ''])));
    setAdvancedError('');
    setAdvancedNotice('');
    setAdvancedTextOutput('');
    setAdvancedOutput(null);
  }

  function advancedOptionsPayload(config: AdvancedToolConfig) {
    const values: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(advancedOptions)) {
      if (!value.trim()) continue;
      if (key === 'metadata' || key === 'values') {
        try {
          values[key] = JSON.parse(value);
        } catch {
          throw new Error(`${config.fields?.find((field) => field.key === key)?.label ?? key} must be valid JSON.`);
        }
      } else if (key.startsWith('margin_')) {
        const side = key.slice('margin_'.length);
        const margins = (values.margins ?? {}) as Record<string, number>;
        margins[side] = Number(value);
        values.margins = margins;
      } else if (key === 'max_size_mb') {
        values.max_size_bytes = Math.round(Number(value) * 1024 * 1024);
      } else if (['start', 'digits', 'page', 'x', 'y', 'angle', 'font_size', 'dpi', 'pages_per_sheet'].includes(key)) {
        values[key] = Number(value);
      } else {
        values[key] = value;
      }
    }
    return values;
  }

  async function runAdvancedTool() {
    if (!selectedAdvancedTool || advancedBusy) return;
    const config = advancedToolConfigs[selectedAdvancedTool.toLowerCase()];
    if (!config) return;
    if (config.mode === 'provider-required') {
      setAdvancedError(config.description);
      return;
    }
    if (!advancedFiles.length) {
      setAdvancedError('Choose a PDF file first.');
      return;
    }
    if (config.fileCount === 2 && advancedFiles.length < 2) {
      setAdvancedError('Choose two files for this operation.');
      return;
    }
    const showInPdfStudio = config.mode !== 'ai' && config.slug !== 'compare-pdf';
    setAdvancedBusy(true);
    if (showInPdfStudio) {
      setPdfBusy(true);
      setPdfProcessingMessage(`Running ${selectedAdvancedTool}…`);
      setPdfOutput(null);
      setPdfResult('');
      setPdfFiles([]);
      setEditorPdfFile(null);
      setPdfPageImage('');
      setPdfAction('info');
      setPage('PDF Studio');
    }
    setAdvancedError('');
    setAdvancedNotice('');
    setAdvancedTextOutput('');
    try {
      const form = new FormData();
      form.append('file', advancedFiles[0]);
      if (config.mode === 'ai') {
        form.append('count', advancedOptions.count || '5');
        form.append('language', advancedOptions.language || 'en');
      } else {
        advancedFiles.slice(1).forEach((file) => form.append('files', file));
        form.append('options', JSON.stringify(advancedOptionsPayload(config)));
      }
      const endpoint = config.mode === 'ai'
        ? `${API}/api/ai/question-generator`
        : `${API}/api/pdf/tools/${config.slug}`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json() as { questions?: string } | Record<string, unknown>;
        setAdvancedTextOutput('questions' in result && typeof result.questions === 'string'
          ? result.questions
          : JSON.stringify(result, null, 2));
      } else {
        const blob = await response.blob();
        const filename = response.headers.get('Content-Disposition')
          ?.match(/filename="?([^";]+)"?/i)?.[1] ?? 'vertex-result.pdf';
        const outputFile = new File([blob], filename, { type: blob.type });
        const url = URL.createObjectURL(outputFile);
        if (showInPdfStudio) {
          setPdfOutput({ file: outputFile, url });
          setPdfResult(`${selectedAdvancedTool} is ready in PDF Studio. Review it, then save or download the result.`);
          if (outputFile.type === 'application/pdf' || outputFile.name.toLowerCase().endsWith('.pdf')) {
            setPdfFiles([outputFile]);
            setEditorPdfFile(outputFile);
            setPdfPageNumber(1);
            void renderPdfPage(outputFile, 1);
          }
          encourageUser(`${selectedAdvancedTool} is complete. Your result is centered in PDF Studio and ready to review.`);
        } else {
          setAdvancedOutput({ file: outputFile, url });
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The PDF operation failed.';
      setAdvancedError(message);
      if (showInPdfStudio) setPdfResult(message);
    } finally {
      setAdvancedBusy(false);
      if (showInPdfStudio) {
        setPdfBusy(false);
        setPdfProcessingMessage('');
      }
    }
  }

  async function saveAdvancedOutput() {
    if (!advancedOutput || !token) return;
    const form = new FormData();
    form.append('file', advancedOutput.file);
    try {
      const response = await fetch(`${API}/api/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const saved = await response.json() as { name: string };
      setAdvancedNotice(`Saved "${saved.name}" to your workspace.`);
      await loadDocuments();
    } catch (error) {
      setAdvancedError(error instanceof Error ? error.message : 'The result could not be saved.');
    }
  }

  function chooseConversion(tool: ConversionTool) {
    const reusableFile = conversionFile;
    const extension = reusableFile?.name.split('.').pop()?.toLowerCase();
    const canReuseFile = Boolean(reusableFile && extension && tool.inputExtensions.includes(extension));
    if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
    setScanMode(false);
    setActiveConversion(tool);
    setConversionFile(canReuseFile ? reusableFile : null);
    setConversionOutput(null);
    setConversionPreviewText('');
    setConversionError('');
    setConversionMessage('');
  }

  function renderConversionPanel() {
    if (!activeConversion) return null;
    const accept = activeConversion.inputExtensions.map((extension) => `.${extension}`).join(',');
    return (
      <section className="panel conversion-panel">
        <div className="section-title">
          <div>
            <h2>{activeConversion.name}</h2>
            <p>Choose a supported source file to create a downloadable result.</p>
          </div>
          <button onClick={() => {
            if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
            setActiveConversion(null);
            setConversionFile(null);
            setConversionOutput(null);
            setConversionPreviewText('');
            setConversionError('');
            setConversionMessage('');
          }}>Clear selection</button>
        </div>
        <label className="file-drop conversion-file-picker">
          <UploadCloud size={22} />
          <b>{conversionFile?.name ?? `Choose ${activeConversion.inputExtensions.join(', ').toUpperCase()} file`}</b>
          <small>{conversionFile ? `${formatSize(conversionFile.size)} selected` : 'Files up to 50 MB'}</small>
          <input type="file" accept={accept} onChange={(event) => {
            const file = event.target.files?.[0] ?? null;
            event.target.value = '';
            if (file && file.size > 50 * 1024 * 1024) {
              setConversionFile(null);
              setConversionError('Choose a file that is 50 MB or smaller.');
              return;
            }
            setConversionFile(file);
            setConversionOutput(null);
            setConversionPreviewText('');
            setConversionError('');
            setConversionMessage('');
          }} />
        </label>
        <button className="primary full-button" disabled={!token || !conversionFile || conversionBusy} onClick={() => void runConversion()}>
          {conversionBusy ? 'Converting…' : `Convert to ${activeConversion.outputFormat.toUpperCase()}`}
        </button>
        {!token && <p className="inline-hint">Sign in to convert files securely.</p>}
        {conversionMessage && <p className="operation-notice" role="status">{conversionMessage}</p>}
        {conversionError && <p className="ai-error" role="alert">{conversionError}</p>}
        {conversionOutput && (
          <div className="conversion-result">
            {conversionOutput.file.type === 'application/pdf'
              ? <iframe className="conversion-preview-frame" src={conversionOutput.url} title={`Preview of ${conversionOutput.file.name}`} />
              : conversionPreviewText
                ? <pre className="conversion-text-preview">{conversionPreviewText}</pre>
                : <div className="conversion-file-ready"><FileText size={28} /><b>{conversionOutput.file.name}</b><span>Conversion complete. Download or save the file to your workspace.</span></div>}
            <div className="conversion-result-actions">
              <button className="primary" disabled={!token || conversionSaveBusy} onClick={() => void saveConversionOutput()}>
                <Save size={15} />{conversionSaveBusy ? 'Saving…' : 'Save to workspace'}
              </button>
              <a href={conversionOutput.url} download={conversionOutput.file.name}><Download size={15} /> Download</a>
              <button className="discard-button" onClick={discardConversionOutput}><Trash2 size={15} /> Delete preview</button>
            </div>
          </div>
        )}
      </section>
    );
  }

  function renderAdvancedToolPanel() {
    if (!selectedAdvancedTool) return null;
    const config = advancedToolConfigs[selectedAdvancedTool.toLowerCase()];
    if (!config) return null;
    const multiple = config.fileCount === 2;
    const accepts = config.mode === 'ai' ? '.pdf,.docx,.txt,.md' : '.pdf';
    const requiresProvider = config.mode === 'provider-required';
    return (
      <section className="panel conversion-panel advanced-tool-panel">
        <div className="section-title">
          <div><h2>{selectedAdvancedTool}</h2><p>{config.description}</p></div>
          <button onClick={() => {
            if (advancedOutput) URL.revokeObjectURL(advancedOutput.url);
            setSelectedAdvancedTool(null);
            setAdvancedFiles([]);
            setAdvancedOutput(null);
            setAdvancedTextOutput('');
            setAdvancedError('');
            setAdvancedNotice('');
          }}>Clear selection</button>
        </div>
        {requiresProvider ? <p className="ai-error" role="status">{config.description}</p> : <>
          <label className="file-drop conversion-file-picker">
            <UploadCloud size={22} />
            <b>{advancedFiles.length
              ? advancedFiles.map((file) => file.name).join(', ')
              : multiple ? 'Choose two PDF files' : 'Choose a PDF file'}</b>
            <small>{advancedFiles.length
              ? `${advancedFiles.length} file${advancedFiles.length === 1 ? '' : 's'} selected`
              : config.mode === 'ai' ? 'PDF, DOCX, TXT or Markdown · up to 50 MB' : 'PDF · up to 50 MB'}</small>
            <input type="file" accept={accepts} multiple={multiple} onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              event.target.value = '';
              if (files.some((file) => file.size > 50 * 1024 * 1024)) {
                setAdvancedFiles([]);
                setAdvancedError('Each file must be 50 MB or smaller.');
                return;
              }
              setAdvancedFiles(files);
              setAdvancedError('');
              setAdvancedNotice('');
              if (advancedOutput) URL.revokeObjectURL(advancedOutput.url);
              setAdvancedOutput(null);
              setAdvancedTextOutput('');
            }} />
          </label>
          {config.additionalImage && <label className="field-label">Optional signature image
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => {
              const image = event.target.files?.[0];
              event.target.value = '';
              if (image && image.size > 10 * 1024 * 1024) {
                setAdvancedError('Signature images must be 10 MB or smaller.');
                return;
              }
              if (image) setAdvancedFiles((current) => current.length ? [current[0], image] : current);
            }} />
          </label>}
          <div className="advanced-tool-fields">
            {(config.fields ?? []).map((field) => <label className="field-label" key={field.key}>{field.label}
              {field.type === 'textarea'
                ? <textarea rows={4} value={advancedOptions[field.key] ?? ''} placeholder={field.placeholder} onChange={(event) => setAdvancedOptions((current) => ({ ...current, [field.key]: event.target.value }))} />
                : field.type === 'select'
                  ? <select value={advancedOptions[field.key] ?? field.defaultValue ?? ''} onChange={(event) => setAdvancedOptions((current) => ({ ...current, [field.key]: event.target.value }))}>{(field.options ?? []).map((option) => <option key={option} value={option}>{option}</option>)}</select>
                  : <input type={field.type === 'number' ? 'number' : 'text'} min={field.type === 'number' ? '0' : undefined} value={advancedOptions[field.key] ?? ''} placeholder={field.placeholder} onChange={(event) => setAdvancedOptions((current) => ({ ...current, [field.key]: event.target.value }))} />}
            </label>)}
          </div>
          <button className="primary full-button" disabled={!token || advancedBusy || !advancedFiles.length} onClick={() => void runAdvancedTool()}>
            {advancedBusy ? 'Working…' : config.mode === 'ai' ? 'Generate questions' : selectedAdvancedTool.toLowerCase() === 'pdf forms' && !advancedOptions.values ? 'Read form fields' : 'Run operation'}
          </button>
          {!token && <p className="inline-hint">Sign in to run this secure backend operation.</p>}
        </>}
        {advancedError && <p className="ai-error" role="alert">{advancedError}</p>}
        {advancedNotice && <p className="operation-notice" role="status">{advancedNotice}</p>}
        {advancedTextOutput && <pre className="advanced-text-output">{advancedTextOutput}</pre>}
        {advancedOutput && <div className="conversion-result">
          {advancedOutput.file.type === 'application/pdf'
            ? <iframe className="conversion-preview-frame" src={advancedOutput.url} title={`Preview of ${advancedOutput.file.name}`} />
            : <div className="conversion-file-ready"><FileText size={28} /><b>{advancedOutput.file.name}</b><span>Operation complete. Download or save the result to your workspace.</span></div>}
          <div className="conversion-result-actions">
            <button className="primary" disabled={!token} onClick={() => void saveAdvancedOutput()}><Save size={15} /> Save to workspace</button>
            <a href={advancedOutput.url} download={advancedOutput.file.name}><Download size={15} /> Download</a>
            <button className="discard-button" onClick={() => { URL.revokeObjectURL(advancedOutput.url); setAdvancedOutput(null); }}><Trash2 size={15} /> Delete preview</button>
          </div>
        </div>}
      </section>
    );
  }

  function renderTools() {
    return (
      <>
        <PageHeading eyebrow="CONVERT & ORGANIZE" title={page} subtitle="Search the complete tool catalogue. Working tools are marked and connected to the backend." />
        {selectedAdvancedTool ? renderAdvancedToolPanel() : scanMode ? renderScanPanel() : renderConversionPanel()}
        <div className="search-bar"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents, tools or features..." /></div>
        <div className="category-tabs" role="tablist" aria-label="Tool categories">
          {['All tools', ...Object.keys(groups)].map((item) => (
            <button className={category === item ? 'active' : ''} key={item} role="tab" aria-selected={category === item} onClick={() => setCategory(item)}>{item}</button>
          ))}
        </div>
        <div className="catalogue-grid">
          {filteredTools.map((item) => {
            const capability = tools.find((tool) => tool.name.toLowerCase() === item.name.toLowerCase());
            const conversion = conversionTools.find((tool) => tool.name.toLowerCase() === item.name.toLowerCase());
            const toolName = item.name.toLowerCase();
            const advancedConfig = advancedToolConfigs[toolName];
            const providerRequired = advancedConfig?.mode === 'provider-required';
            const supported = Boolean(conversion)
              || (capability?.supported ?? false)
              || Boolean(advancedConfig && !providerRequired);
            const actionByTool: Record<string, PdfAction> = {
              'merge pdf': 'merge',
              'split pdf': 'split',
              'rotate pdf': 'rotate',
              'remove pages': 'remove-pages',
              'extract pages': 'extract-pages',
              'organize pdf': 'organize',
              'protect pdf': 'protect',
              'unlock pdf': 'unlock',
              'pdf to text': 'text',
              'compress pdf': 'compress',
              'flip pdf': 'flip',
            };
            const supportedAction = actionByTool[item.name.toLowerCase()];
            const icon = supported ? <FileText size={20} /> : <CircleAlert size={20} />;
            return (
              <button className={`catalogue-card ${supported ? '' : 'not-ready'}`} key={`${item.category}-${item.name}`} onClick={() => {
                if (conversion) {
                  setSelectedAdvancedTool(null);
                  chooseConversion(conversion);
                  setPage('Convert');
                  return;
                }
                if (toolName === 'scan to pdf') {
                  if (conversionOutput) URL.revokeObjectURL(conversionOutput.url);
                  setSelectedAdvancedTool(null);
                  setScanMode(true);
                  setActiveConversion(null);
                  setConversionFile(null);
                  setConversionOutput(null);
                  setConversionPreviewText('');
                  setConversionError('');
                  setConversionMessage('');
                  setPage('Convert');
                  return;
                }
                if (supportedAction) {
                  setSelectedAdvancedTool(null);
                  setScanMode(false);
                  setPdfAction(supportedAction);
                  setPage('PDF Studio');
                  return;
                }
                if (['read pdf', 'pdf reader', 'pdf annotator', 'edit pdf'].includes(toolName)) {
                  setSelectedAdvancedTool(null);
                  setScanMode(false);
                  setPdfAction(toolName === 'read pdf' || toolName === 'pdf reader' ? 'text' : 'info');
                  setPage('PDF Studio');
                  return;
                }
                if (advancedConfig) {
                  selectAdvancedTool(item.name);
                  setPage('Convert');
                  return;
                }
                setScanMode(false);
                setNotice(`${item.name} needs a configured processing engine before it can be used.`);
              }}>
                <span className="catalogue-icon">{icon}</span><b>{item.name}</b><small>{item.category}</small>
                <span className="tool-status">{providerRequired ? 'Provider required' : supported ? 'Ready to use' : 'Engine required'}</span>
              </button>
            );
          })}
        </div>
      </>
    );
  }

  function renderPage() {
    switch (page) {
      case 'Home / Workspace':
        return (
          <>
            <section className="welcome-panel">
              <div>
                <span className="eyebrow">YOUR DOCUMENT WORKSPACE</span>
                <h1>All your PDF tools,<br /><em>one simple workspace.</em></h1>
                <p>Convert, organize and improve your documents with a clean set of tools that are easy to find and use.</p>
                <div className="welcome-actions">
                  <label className="primary button-label"><UploadCloud size={17} /> Upload a document<input type="file" onChange={(event) => { void uploadDocument(event.target.files?.[0]); event.target.value = ''; }} /></label>
                  <button onClick={() => setPage('PDF Studio')}>Open PDF Studio <ChevronDown className="chevron-side" size={16} /></button>
                </div>
              </div>
              <div className="welcome-art" aria-hidden="true"><span>{companion.emoji}</span><small>Here to help</small></div>
            </section>
            {renderUploadNextSteps()}
            <section className="panel documents-panel">
              <div className="section-title"><div><span className="eyebrow">YOUR FILES</span><h2>Recent documents</h2><p>Uploaded files are private to your account.</p></div><button onClick={() => setPage('Document History')}>View all <ChevronDown className="chevron-side" size={15} /></button></div>
              {renderDocuments()}
            </section>
            <section className="quick-tools">
              <div className="section-title"><div><span className="eyebrow">GET STARTED</span><h2>Popular tools</h2></div></div>
              <div className="quick-tool-grid">
                {pdfActions.slice(0, 4).map((action) => {
                  const Icon = action.icon;
                  return <button key={action.id} onClick={() => { setPdfAction(action.id); setPage('PDF Studio'); }}><Icon size={19} /><b>{action.name}</b><small>{action.description}</small></button>;
                })}
              </div>
            </section>
          </>
        );
      case 'PDF Studio':
        return renderPdfStudio();
      case 'Convert':
        return renderTools();
      case 'Templates':
        return renderTemplates();
      case 'Document History':
        return renderDocumentHistory();
      case 'AI Documents':
        return renderAiDocuments();
      case 'Language Bridge':
        return (
          <>
            <PageHeading eyebrow="LANGUAGE BRIDGE" title="Translate your way" subtitle="Write in any supported language or upload a document, then choose the language you want." />
            <section className="panel translation-panel">
              <div className="translation-language-row">
                <label className="field-label">From
                  <select value={translationSource} onChange={(event) => { setTranslationSource(event.target.value); setTranslationResult(''); setTranslationOutput(null); setTranslationMessage(''); }}>
                    <option value="auto">Detect language</option>
                    {languages.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                  </select>
                </label>
                <ArrowLeftRight className="translation-arrow" size={18} />
                <label className="field-label">To
                  <select value={translationTarget} onChange={(event) => { setTranslationTarget(event.target.value); setTranslationResult(''); setTranslationOutput(null); setTranslationMessage(''); }}>
                    {languages.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                  </select>
                </label>
              </div>
              <label className="field-label translation-input-label">Text to translate
                <textarea value={translationText} onChange={(event) => { setTranslationText(event.target.value); setTranslationFile(null); setTranslationResult(''); setTranslationOutput(null); setTranslationMessage(''); }} maxLength={20000} placeholder="Type or paste text in any language…" />
              </label>
              <div className="translation-or">or upload a document</div>
              <label className="file-drop translation-file">
                <UploadCloud size={21} />
                <b>{translationFile ? translationFile.name : 'Choose a PDF, DOCX, TXT, or Markdown file'}</b>
                <small>We extract text and translate it. Max 20,000 characters.</small>
                <input type="file" accept=".pdf,.docx,.txt,.md,application/pdf,text/plain" onChange={(event) => { setTranslationFile(event.target.files?.[0] ?? null); setTranslationText(''); setTranslationResult(''); setTranslationOutput(null); setTranslationMessage(''); event.target.value = ''; }} />
              </label>
              <div className="translation-actions">
                <span>13 targets, including Tanglish</span>
                <button className="primary" disabled={translationBusy} onClick={() => void runTranslation()}>{translationBusy ? (translationFile ? 'Translating file sections…' : 'Translating…') : 'Translate'}</button>
              </div>
              {translationBusy && translationFile && <p className="translation-progress" role="status">Reading and translating the document in shorter sections. You can stay on this page while it finishes.</p>}
              {translationResult && <section className="translation-result"><b>{translationFile ? 'Translated document' : 'Translation'}</b><pre>{translationResult}</pre></section>}
              {translationOutput && <div className="translation-output-actions">
                <button className="primary" onClick={downloadTranslationOutput}><Download size={15} /> Download translated file</button>
                <button disabled={!token || translationSaveBusy} onClick={() => void saveTranslationOutput()}><Save size={15} /> {translationSaveBusy ? 'Saving…' : 'Save to Document History'}</button>
                <button className="discard-button" onClick={clearTranslationOutput}><Trash2 size={15} /> Delete result</button>
              </div>}
              {translationMessage && <p className="operation-notice" role="status">{translationMessage}</p>}
              {!token && <p className="inline-hint">Sign in and configure an LLM_API_KEY in the backend to translate.</p>}
            </section>
          </>
        );
      case 'Account / Privacy':
        return (
          <>
            <PageHeading eyebrow="ACCOUNT & PRIVACY" title={user ? 'Account & security' : 'Sign in to your workspace'} subtitle={user ? 'Your identity, session and document privacy in one place.' : 'Create a personal account or sign in to return to your private workspace.'} />
            {user ? <div className="account-page-content">
              <section className="panel account-profile-card">
                <div className="account-profile-avatar">{companion.emoji}</div>
                <div className="account-profile-info"><span className="eyebrow">PERSONAL ACCOUNT</span><h2>{user.name}</h2><p>{user.email}</p></div>
                <span className="account-active-badge"><Check size={14}/> Active</span>
                <button className="account-signout" onClick={signOut}><LogOut size={16}/>Sign out</button>
              </section>
              <div className="account-security-grid">
                <section className="panel account-security-card"><span className="account-security-icon"><ShieldCheck size={19}/></span><h3>Your documents are private</h3><p>Files in your workspace are linked to your account. Other signed-in users cannot list, download, or delete them.</p><small>{documents.length} {documents.length===1?'document':'documents'} in your workspace</small></section>
                <section className="panel account-security-card"><span className="account-security-icon"><LockKeyhole size={19}/></span><h3>Sign-in stays personal</h3><p>Use your own email and password. Sign out on shared devices; your account and saved files remain available when you sign in again.</p><small>Signed in as {user.email}</small></section>
                <section className="panel account-security-card"><span className="account-security-icon"><Settings2 size={19}/></span><h3>Workspace preferences</h3><p>Your theme, assistant language, and companion are saved to your account.</p><button onClick={()=>setPage('Companion & Themes')}>Manage appearance <ChevronDown className="chevron-side" size={14}/></button></section>
                <section className="panel account-security-card"><span className="account-security-icon"><Sparkles size={19}/></span><h3>AI document processing</h3><p>AI features send the selected document text to the provider configured by this workspace. They require the administrator’s API configuration.</p><small>AI is only used when you request a summary, chat, or translation.</small></section>
              </div>
            </div> : <div className="auth-page-layout">
              <section className="auth-welcome-card">
                <span className="auth-welcome-icon"><ShieldCheck size={23}/></span>
                <span className="eyebrow">YOUR PRIVATE WORKSPACE</span>
                <h2>Pick up right where you left off.</h2>
                <p>Your uploaded documents and saved preferences are tied to your account—not to a temporary browser session.</p>
                <div className="auth-benefit"><Check size={15}/><span>Sign in again to find your files and settings</span></div>
                <div className="auth-benefit"><Check size={15}/><span>Every account sees only its own documents</span></div>
                <div className="auth-benefit"><Check size={15}/><span>Use any valid email when creating your account</span></div>
              </section>
              <form className="auth-panel panel" onSubmit={(event)=>{event.preventDefault();void submitAuth();}}>
                <div className="auth-tabs"><button type="button" className={authMode === 'login' ? 'active' : ''} onClick={() => { setAuthMode('login'); setNotice(''); }}>Sign in</button><button type="button" className={authMode === 'signup' ? 'active' : ''} onClick={() => { setAuthMode('signup'); setNotice(''); }}>Create account</button></div>
                <div><h2 className="auth-form-title">{authMode==='signup'?'Create your account':'Welcome back'}</h2><p className="auth-form-subtitle">{authMode==='signup'?'Use any valid email address and create a password.':'Use the email and password you registered with.'}</p></div>
                {authMode === 'signup' && <label className="field-label">Name<input required minLength={2} maxLength={120} value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder="Your name" /></label>}
                <label className="field-label">Email address<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" placeholder="you@example.com" /></label>
                <label className="field-label">Password<input required minLength={8} maxLength={128} type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'} placeholder="At least 8 characters" /></label>
                <button className="primary full-button" type="submit">{authMode === 'signup' ? 'Create account' : 'Sign in securely'}</button>
                {notice && <p className="inline-hint" role="status">{notice}</p>}
                <small className="auth-footnote"><LockKeyhole size={13}/> Passwords are stored as secure hashes, never as plain text.</small>
              </form>
            </div>}
          </>
        );
      case 'Companion & Themes':
        return (
          <>
            <PageHeading eyebrow="MAKE VERTEX YOURS" title="Companion & appearance" subtitle="Choose your animated companion and give your workspace a colour palette that feels right." />
            <div className="appearance-grid">
              <section className="panel companion-panel">
                <div className="section-title"><div><h2>Your companion</h2><p>{companion.name} is your Vertex assistant.</p></div><div className="companion-preview">{companion.emoji}</div></div>
                <div className="companion-grid">
                  {companions.map((item) => (
                    <button className={`companion-card ${avatar === item.id ? 'selected' : ''}`} key={item.id} onClick={() => void savePreferences({ avatar: item.id })}>
                      <span className="character-art">{item.emoji}</span><b>{item.name}</b><small>{item.description}</small>
                      {avatar === item.id && <Check className="selected-check" size={17} />}
                    </button>
                  ))}
                </div>
                {!user && <p className="inline-hint">Your choice is saved on this device. Sign in to sync it to your account.</p>}
              </section>
              <section className="panel themes-panel">
                <div className="section-title"><div><h2>Workspace colours</h2><p>Pick a real-world palette, then choose its light or dark look.</p></div></div>
                <div className="theme-mode-switch" role="group" aria-label="Theme brightness">
                  {(['light', 'dark'] as const).map((mode) => (
                    <button className={themeMode === mode ? 'active' : ''} key={mode} onClick={() => void savePreferences({ theme: `${paletteId}-${mode}` as ThemeName })}>
                      {mode === 'light' ? <Sun size={15} /> : <Moon size={15} />}{mode === 'light' ? 'Light' : 'Dark'}
                    </button>
                  ))}
                </div>
                <div className="theme-list">
                  {palettes.map((item) => (
                    <button className={`theme-option ${paletteId === item.id ? 'selected' : ''}`} key={item.id} onClick={() => void savePreferences({ theme: `${item.id}-${themeMode}` as ThemeName })}>
                      <span className="theme-swatch"><i style={{ backgroundColor: item.light }} /><i style={{ backgroundColor: item.dark }} /></span>
                      <span className="theme-name"><b>{item.name}</b><small>Soft light and balanced dark</small></span>
                      {paletteId === item.id && <Check size={17} />}
                    </button>
                  ))}
                </div>
                <p className="theme-confirmation">{notice || 'Your selection updates the workspace immediately.'}</p>
              </section>
            </div>
          </>
        );
    }
  }

  return (
    <div className={`app-shell ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      <header className="topbar">
        <button className="icon-button menu-button" aria-label="Toggle navigation" onClick={() => setSidebarOpen((open) => !open)}><Menu size={19} /></button>
        <button className="brand" onClick={() => setPage('Home / Workspace')}><span className="brand-mark"><img src="/jm-logo.png" alt="JM logo" /></span><span><b>Vertex Docs</b><small>JM Vertex Technologies</small></span></button>
        <div className="top-search"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') setPage('Convert'); }} placeholder="Search documents, tools or features..." /></div>
        <div className="top-actions">
          <button className="icon-button" aria-label="Appearance settings" onClick={() => setPage('Companion & Themes')}>{themeMode === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="icon-button notification-button" aria-label="Notifications" onClick={() => setNotice(token ? 'You are all caught up.' : 'Sign in to see account notifications.')}><Bell size={18} /></button>
          {user ? (
            <button className="profile-button" onClick={() => setPage('Account / Privacy')}><span>{user.name.slice(0, 1).toUpperCase()}</span><b>{user.name}</b><ChevronDown size={15} /></button>
          ) : <button className="profile-button" onClick={() => setPage('Account / Privacy')}><span><UserRound size={15} /></span><b>Sign in</b><ChevronDown size={15} /></button>}
        </div>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <span className="sidebar-caption">WORKSPACE</span>
          <nav>          {navItems.slice(0, 7).map(({ name: itemName, label, icon: Icon }) => (
            <button className={page === itemName ? 'active' : ''} key={itemName} onClick={() => { setPage(itemName); if (itemName === 'AI Documents') setChatOpen(false); }}><Icon size={18} /><span>{label}</span></button>
          ))}</nav>
          {page !== 'AI Documents' && <section className="sidebar-assistant">
              <span className="sidebar-companion">{companion.emoji}</span>
              <b>Need a hand?</b>
              <small>Ask the Vertex assistant</small>
              <button onClick={() => setChatOpen(true)}>Open assistant</button>
            </section>}
          <nav className="sidebar-bottom">{navItems.slice(7).map(({ name: itemName, label, icon: Icon }) => (
            <button className={page === itemName ? 'active' : ''} key={itemName} onClick={() => setPage(itemName)}><Icon size={18} /><span>{label}</span></button>
          ))}</nav>
        </aside>
        <main className="main-content">
          {renderPage()}
          {notice && !['Account / Privacy', 'Companion & Themes'].includes(page) && <Notice message={notice} onClose={() => setNotice('')} />}
        </main>
      </div>
      {page !== 'AI Documents' && assistantToast && (
        <div className="assistant-toast" role="status" aria-live="polite">
          <span className="toast-character">{companion.emoji}</span>
          <span className="toast-copy"><b>{companion.name} says</b><small>{assistantToast}</small></span>
          <button aria-label="Dismiss assistant message" onClick={() => setAssistantToast('')}><X size={15} /></button>
        </div>
      )}
      {page !== 'AI Documents' && <button className="assistant-fab" aria-label="Open Vertex Assistant" onClick={() => setChatOpen((open) => !open)}><span>{companion.emoji}</span><small>AI</small></button>}
      {page !== 'AI Documents' && chatOpen && (
        <section className="assistant-panel">
          <header className="assistant-header">
            <span className="assistant-star"><Sparkles size={17} /></span>
            <span><b>Vertex Assistant</b><small>{chatConversations.find((item) => item.id === activeChatId)?.title || 'Private chat'} · {companion.name}</small></span>
            <button className="assistant-new-chat" disabled={!token || chatHistoryBusy} onClick={() => void createChatConversation().catch((error: unknown) => setNotice(error instanceof Error ? error.message : 'Could not start a new chat.'))}><FilePlus2 size={15} /> New chat</button>
            <button className="icon-button" aria-label="Close assistant" onClick={() => setChatOpen(false)}><X size={18} /></button>
          </header>
          <div className="assistant-workspace">
            <aside className="assistant-history">
              <b>Chat history</b>
              {chatHistoryBusy && <small>Loading chats…</small>}
              {!chatHistoryBusy && !chatConversations.length && <small>Your chats will appear here.</small>}
              {chatConversations.map((conversation) => <div className={`assistant-history-item ${activeChatId === conversation.id ? 'active' : ''}`} key={conversation.id}>
                <button title={conversation.title} onClick={() => void selectChatConversation(conversation.id)}>{conversation.title}</button>
                <button aria-label={`Delete ${conversation.title}`} title="Delete chat" onClick={() => void deleteChatConversation(conversation.id)}><Trash2 size={13} /></button>
              </div>)}
              {!token && <small>Sign in to keep private chat history.</small>}
            </aside>
            <div className="assistant-chat-main">
              <div className="assistant-messages">
                {!chatMessages.length && <div className="assistant-welcome"><b>{companion.emoji} {companion.name}</b><p>Hello! Ask a question, attach a document or image, or convert a supported file.</p><button className="chat-speak-button" onClick={() => speakText('Hello! I am your Vertex assistant. Ask a question, attach a document or image, or convert a supported file.')}><Volume2 size={14}/> Listen</button>{!token && <small>Sign in to chat. Add an LLM_API_KEY to backend/.env to enable AI replies.</small>}</div>}
                {chatMessages.map((message, index) => <div className={`chat-message-row ${message.role}`} key={`${message.role}-${index}`}><p className={`chat-message ${message.role}`}>{message.text}</p>{message.role==='assistant'&&<button className="chat-speak-button" aria-label="Read response aloud" onClick={() => speakText(message.text)}><Volume2 size={14}/></button>}</div>)}
                {chatBusy && <p className="chat-message assistant">Thinking…</p>}
                {voiceFeedback&&<small className="voice-feedback">{voiceFeedback}</small>}
              </div>
              {chatConversionOutput && <div className="assistant-conversion-result"><FileText size={16} /><span><b>{chatConversionOutput.file.name}</b><small>Conversion complete</small></span><a href={chatConversionOutput.url} download={chatConversionOutput.file.name}><Download size={15} /> Download</a></div>}
            </div>
          </div>
          <div className="assistant-attachment-row">
            <button onClick={() => chatAttachmentInputRef.current?.click()}><UploadCloud size={14} /> Attach file or image</button>
            <input ref={chatAttachmentInputRef} type="file" accept=".pdf,.docx,.txt,.md,image/png,image/jpeg,image/webp" hidden onChange={(event) => { const file = event.target.files?.[0] ?? null; setChatAttachmentError(file && file.size > 50 * 1024 * 1024 ? 'Files must be 50 MB or smaller.' : ''); setChatAttachment(file && file.size <= 50 * 1024 * 1024 ? file : null); event.target.value = ''; }} />
            {chatAttachment && <span className="assistant-attachment-chip" title={chatAttachment.name}>{chatAttachment.name}<button aria-label="Remove attachment" onClick={() => setChatAttachment(null)}><X size={12} /></button></span>}
            <select aria-label="Convert attached file to" value={chatConversionFormat} onChange={(event) => setChatConversionFormat(event.target.value as ExportFormat)}><option value="pdf">Convert to PDF</option><option value="docx">Convert to DOCX</option><option value="txt">Convert to TXT</option></select>
            <button disabled={!chatAttachment || chatConversionBusy || !token} onClick={() => void convertChatAttachment()}>{chatConversionBusy ? 'Converting…' : 'Convert'}</button>
            {chatAttachmentError && <small role="alert">{chatAttachmentError}</small>}
          </div>
          <div className="assistant-compose">
            <label className="language-select"><Languages size={15} /><select value={language} onChange={(event) => void savePreferences({ language: event.target.value })} aria-label="Assistant language">{languages.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
            <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendChat(); } }} placeholder="Message Vertex Assistant…" aria-label="Message Vertex Assistant" />
            <button className={`voice-button ${isListening?'voice-active':''}`} aria-label={isListening?'Stop voice input':'Speak your message'} aria-pressed={isListening} onClick={() => startVoiceInput((text) => setChatInput((current) => [current,text].filter(Boolean).join(' ')))}><Mic size={16}/></button>
            <button className="send-button" aria-label="Send message" disabled={chatBusy || (!chatInput.trim() && !chatAttachment) || !token} onClick={() => void sendChat()}><Send size={17} /></button>
          </div>
        </section>
      )}
    </div>
  );
}

function TemplateArtwork({ template }: { template: TemplateKind }) {
  return (
    <span className={`template-card-art ${template}`} aria-hidden="true">
      <span className="template-mini-page">
        {template==='resume'&&<><span className="template-mini-profile"><i/><span><b/><i/></span></span><i className="template-mini-rule"/><b className="template-mini-heading"/><i/><i/><b className="template-mini-heading"/><i/><i/></>}
        {(template==='cover-letter'||template==='business-letter')&&<><b className="template-mini-heading"/><i/><i/><i className="template-mini-space"/><i/><i/><i/><i/></>}
        {template==='meeting-notes'&&<><b className="template-mini-heading"/><i className="template-mini-date"/><b className="template-mini-heading"/><i/><i/><i className="template-mini-check"/><i className="template-mini-check"/></>}
        {template==='project-proposal'&&<><span className="template-mini-banner"/><b className="template-mini-heading"/><i/><i/><b className="template-mini-heading"/><i/><i/></>}
        {template==='invoice'&&<><span className="template-mini-invoice-head"><b/><i/></span><span className="template-mini-invoice-table"><b/><i/><i/><i/><i/><i/></span><i className="template-mini-total"/></>}
      </span>
    </span>
  );
}

function PageHeading({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) {
  return <div className="page-heading"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></div>;
}

function Notice({ message, onClose }: { message: string; onClose: () => void }) {
  return <div className="notice" role="status"><span>{message}</span><button aria-label="Dismiss" onClick={onClose}><X size={15} /></button></div>;
}

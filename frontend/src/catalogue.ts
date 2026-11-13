export type Companion = {
  id: string;
  name: string;
  description: string;
  emoji: string;
};

export const companions: Companion[] = [
  { id: 'robo', name: 'Robo', description: 'Professional assistant', emoji: '🤖' },
  { id: 'nova', name: 'Nova', description: 'Space explorer', emoji: '🧑‍🚀' },
  { id: 'finn', name: 'Finn', description: 'Clever fox', emoji: '🦊' },
  { id: 'milo', name: 'Milo', description: 'Curious cat', emoji: '🐱' },
  { id: 'pip', name: 'Pip', description: 'Playful ghost', emoji: '👻' },
  { id: 'wiz', name: 'Wiz', description: 'Friendly wizard', emoji: '🧙' },
];

export const palettes = [
  { id: 'forest', name: 'Forest', light: '#eaf3ec', dark: '#29372e', accent: '#3d855b' },
  { id: 'rose', name: 'Rose', light: '#f8edf1', dark: '#3b3036', accent: '#b65379' },
  { id: 'graphite', name: 'Graphite', light: '#eef0f3', dark: '#34383f', accent: '#737d90' },
  { id: 'cocoa', name: 'Cocoa', light: '#f5eee7', dark: '#3b332d', accent: '#9b6b46' },
  { id: 'amber', name: 'Amber', light: '#f7f1df', dark: '#3b382b', accent: '#9c7d27' },
  { id: 'ocean', name: 'Ocean', light: '#eaf2f4', dark: '#303c40', accent: '#438794' },
  { id: 'green-white', name: 'Green & White', light: '#f1f7f1', dark: '#29382f', accent: '#34734b' },
  { id: 'midnight-luxury', name: 'Midnight Luxury', light: '#f0f2f8', dark: '#292e40', accent: '#465789' },
  { id: 'sage-balance', name: 'Sage Balance', light: '#eff4ef', dark: '#303a34', accent: '#5b7c68' },
  { id: 'nordic-espresso', name: 'Nordic Espresso', light: '#f6f0e8', dark: '#38312b', accent: '#805b3c' },
  { id: 'steel-minimalist', name: 'Steel Minimalist', light: '#eef1f4', dark: '#32373d', accent: '#596877' },
  { id: 'warm-plum', name: 'Warm Plum', light: '#f7eff2', dark: '#3b2e37', accent: '#8a5a70' },
  { id: 'deep-teal', name: 'Deep Teal', light: '#edf4f4', dark: '#2d3d40', accent: '#38757a' },
] as const;

export const languages: [string, string][] = [
  ['en', 'English'],
  ['ta', 'Tamil'],
  ['hi', 'Hindi'],
  ['ml', 'Malayalam'],
  ['te', 'Telugu'],
  ['kn', 'Kannada'],
  ['ja', 'Japanese'],
  ['de', 'German'],
  ['sa', 'Sanskrit'],
  ['bn', 'Bengali'],
  ['fr', 'French'],
  ['es', 'Spanish'],
  ['tanglish', 'Tanglish'],
];

export const groups: Record<string, string[]> = {
  'Organize PDF': ['Merge PDF', 'Split PDF', 'Remove Pages', 'Extract Pages', 'Organize PDF', 'Scan to PDF'],
  'Advanced PDF Editing': ['Rotate PDF', 'Add Page Numbers', 'Add Watermark', 'Crop PDF', 'Edit PDF', 'PDF Forms'],
  'PDF Security': ['Protect PDF', 'Unlock PDF', 'Sign PDF', 'Read PDF', 'Compare PDF'],
  'PDF Optimization': ['Compress PDF', 'Repair PDF', 'OCR PDF'],
  'Convert to PDF': ['JPG to PDF', 'Word to PDF', 'PPT to PDF', 'Excel to PDF', 'HTML to PDF'],
  'Convert from PDF': ['PDF to JPG', 'PDF to Word', 'PDF to PPT', 'PDF to Excel', 'PDF to PDF/A'],
  'AI PDF Intelligence': ['AI PDF Summarizer', 'PDF Translator', 'PDF to Markdown'],
  Productivity: ['Vertex AI Assistant', 'AI Documents', 'Document History', 'Word and Document Editor'],
  'Advanced Features': [
    'Alternate and Mix PDF', 'Split by Bookmarks', 'Split by Half', 'Split by Size', 'Split by Text',
    'Flatten PDF', 'PDF to Text', 'Bates Numbering', 'Create Bookmarks', 'Edit Metadata',
    'Extract Images', 'Flip PDF', 'Grayscale PDF', 'Header and Footer', 'N-up PDF', 'Rename PDF',
    'Resize PDF', 'Remove Annotations', 'Deskew PDF',
  ],
  'Additional Tools': [
    'PDF to PNG', 'TXT to PDF', 'RTF to PDF', 'HWP to PDF', 'ZIP to PDF', 'Share PDF',
    'Request Signature', 'AI Question Generator', 'PDF Reader', 'PDF Annotator', 'ODT to PDF',
    'ODS to PDF', 'ODP to PDF', 'Pages to PDF', 'CSV to PDF', 'EPUB to PDF',
  ],
};

export type ConversionFormat = 'pdf' | 'pdfa' | 'jpg' | 'png' | 'docx' | 'pptx' | 'xlsx' | 'txt' | 'md';

export type ConversionTool = {
  name: string;
  inputExtensions: string[];
  outputFormat: ConversionFormat;
};

export const conversionTools: ConversionTool[] = [
  { name: 'JPG to PDF', inputExtensions: ['jpg', 'jpeg', 'png', 'webp'], outputFormat: 'pdf' },
  { name: 'Word to PDF', inputExtensions: ['doc', 'docx'], outputFormat: 'pdf' },
  { name: 'PPT to PDF', inputExtensions: ['ppt', 'pptx'], outputFormat: 'pdf' },
  { name: 'Excel to PDF', inputExtensions: ['xls', 'xlsx'], outputFormat: 'pdf' },
  { name: 'HTML to PDF', inputExtensions: ['html', 'htm'], outputFormat: 'pdf' },
  { name: 'PDF to JPG', inputExtensions: ['pdf'], outputFormat: 'jpg' },
  { name: 'PDF to Word', inputExtensions: ['pdf'], outputFormat: 'docx' },
  { name: 'PDF to PPT', inputExtensions: ['pdf'], outputFormat: 'pptx' },
  { name: 'PDF to Excel', inputExtensions: ['pdf'], outputFormat: 'xlsx' },
  { name: 'PDF to PDF/A', inputExtensions: ['pdf'], outputFormat: 'pdfa' },
  { name: 'PDF to Markdown', inputExtensions: ['pdf'], outputFormat: 'md' },
  { name: 'PDF to Text', inputExtensions: ['pdf'], outputFormat: 'txt' },
  { name: 'PDF to PNG', inputExtensions: ['pdf'], outputFormat: 'png' },
  { name: 'TXT to PDF', inputExtensions: ['txt', 'md'], outputFormat: 'pdf' },
  { name: 'RTF to PDF', inputExtensions: ['rtf'], outputFormat: 'pdf' },
  { name: 'HWP to PDF', inputExtensions: ['hwp'], outputFormat: 'pdf' },
  { name: 'ZIP to PDF', inputExtensions: ['zip'], outputFormat: 'pdf' },
  { name: 'ODT to PDF', inputExtensions: ['odt'], outputFormat: 'pdf' },
  { name: 'ODS to PDF', inputExtensions: ['ods'], outputFormat: 'pdf' },
  { name: 'ODP to PDF', inputExtensions: ['odp'], outputFormat: 'pdf' },
  { name: 'Pages to PDF', inputExtensions: ['pages'], outputFormat: 'pdf' },
  { name: 'CSV to PDF', inputExtensions: ['csv'], outputFormat: 'pdf' },
  { name: 'EPUB to PDF', inputExtensions: ['epub'], outputFormat: 'pdf' },
];

export const tools = [
  { name: 'Merge PDF', supported: true },
  { name: 'Split PDF', supported: true },
  { name: 'Rotate PDF', supported: true },
  { name: 'Remove pages', supported: true },
  { name: 'Extract pages', supported: true },
  { name: 'Organize PDF', supported: true },
  { name: 'Scan to PDF', supported: true },
  { name: 'Protect PDF', supported: true },
  { name: 'Unlock PDF', supported: true },
  { name: 'PDF to Text', supported: true },
  { name: 'Compress PDF', supported: true },
  { name: 'Office, image and ebook conversions', supported: false },
  { name: 'OCR and translation', supported: false },
  { name: 'Signatures and advanced editing', supported: false },
];

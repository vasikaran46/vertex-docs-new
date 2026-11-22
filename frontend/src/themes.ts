// Colour themes. Every theme is light (the dark mode was removed on request) and is described by two
// colours: `a` (primary) and `b` (second gradient stop). All other shades (page, surface, border, text...)
// are derived in themes.css with color-mix(), so adding a theme is a one-line change.

export type ThemeDef = { id: string; name: string; a: string; b: string; group: 'gradient' | 'solid' };

export const themes: ThemeDef[] = [
  // Gradient themes - the purple fintech look first, then more colour stories.
  { id: 'violet', name: 'Violet Fintech', a: '#6a3df0', b: '#a56bff', group: 'gradient' },
  { id: 'aurora', name: 'Aurora', a: '#7c3aed', b: '#ec4899', group: 'gradient' },
  { id: 'candy', name: 'Candy Pop', a: '#db2777', b: '#8b5cf6', group: 'gradient' },
  { id: 'sunset', name: 'Sunset', a: '#ea580c', b: '#db2777', group: 'gradient' },
  { id: 'lagoon', name: 'Lagoon', a: '#2563eb', b: '#06b6d4', group: 'gradient' },
  { id: 'oceanic', name: 'Oceanic', a: '#0284c7', b: '#6366f1', group: 'gradient' },
  { id: 'meadow', name: 'Meadow', a: '#059669', b: '#65a30d', group: 'gradient' },
  { id: 'goldrush', name: 'Gold Rush', a: '#b45309', b: '#eab308', group: 'gradient' },
  // Solid themes
  { id: 'indigo', name: 'Indigo', a: '#4f46e5', b: '#6366f1', group: 'solid' },
  { id: 'royal', name: 'Royal Blue', a: '#1d4ed8', b: '#3b82f6', group: 'solid' },
  { id: 'sky', name: 'Sky', a: '#0369a1', b: '#0ea5e9', group: 'solid' },
  { id: 'teal', name: 'Teal', a: '#0f766e', b: '#14b8a6', group: 'solid' },
  { id: 'emerald', name: 'Emerald', a: '#047857', b: '#10b981', group: 'solid' },
  { id: 'forest', name: 'Forest', a: '#3d855b', b: '#5aa77a', group: 'solid' },
  { id: 'olive', name: 'Olive', a: '#4d7c0f', b: '#84cc16', group: 'solid' },
  { id: 'amber', name: 'Amber', a: '#b45309', b: '#f59e0b', group: 'solid' },
  { id: 'copper', name: 'Copper', a: '#9a5b34', b: '#c98a5e', group: 'solid' },
  { id: 'crimson', name: 'Crimson', a: '#b91c1c', b: '#ef4444', group: 'solid' },
  { id: 'rose', name: 'Rose', a: '#be185d', b: '#ec4899', group: 'solid' },
  { id: 'plum', name: 'Plum', a: '#86198f', b: '#c026d3', group: 'solid' },
  { id: 'slate', name: 'Slate', a: '#475569', b: '#64748b', group: 'solid' },
  { id: 'graphite', name: 'Graphite', a: '#374151', b: '#6b7280', group: 'solid' },
];

export const DEFAULT_THEME = 'violet';
export const CUSTOM_THEME = 'custom';
const CUSTOM_KEY = 'vd-custom-theme';

export type CustomColours = { a: string; b: string };

export function readCustomColours(): CustomColours {
  try {
    const parsed = JSON.parse(localStorage.getItem(CUSTOM_KEY) || '');
    if (/^#[0-9a-f]{6}$/i.test(parsed?.a) && /^#[0-9a-f]{6}$/i.test(parsed?.b)) return parsed;
  } catch { /* fall through */ }
  return { a: '#6a3df0', b: '#a56bff' };
}

export function saveCustomColours(colours: CustomColours) {
  try { localStorage.setItem(CUSTOM_KEY, JSON.stringify(colours)); } catch { /* storage unavailable */ }
}

// Old saved values (including every former "-dark" theme) are mapped to the closest new theme.
const LEGACY_FAMILIES: Record<string, string> = {
  forest: 'forest', 'green-white': 'emerald', 'sage-balance': 'emerald', sage: 'emerald', mint: 'emerald',
  rose: 'rose', 'warm-plum': 'plum',
  graphite: 'graphite', 'steel-minimalist': 'slate', porcelain: 'slate',
  cocoa: 'copper', 'nordic-espresso': 'copper', sand: 'copper',
  amber: 'amber',
  ocean: 'sky', 'deep-teal': 'teal',
  'midnight-luxury': 'indigo',
  light: DEFAULT_THEME, dark: DEFAULT_THEME,
};

export function themeFrom(value: string | null | undefined): string {
  if (!value) return DEFAULT_THEME;
  if (value === CUSTOM_THEME || themes.some((theme) => theme.id === value)) return value;
  const family = value.replace(/-(light|dark)$/, '');
  return LEGACY_FAMILIES[family] ?? DEFAULT_THEME;
}

export function themeDef(id: string): ThemeDef {
  if (id === CUSTOM_THEME) return { id, name: 'Custom', ...readCustomColours(), group: 'gradient' };
  return themes.find((theme) => theme.id === id) ?? themes[0];
}

export function applyTheme(id: string) {
  const def = themeDef(id);
  const root = document.documentElement;
  root.dataset.theme = id;
  root.style.setProperty('--t1', def.a);
  root.style.setProperty('--t2', def.b);
}

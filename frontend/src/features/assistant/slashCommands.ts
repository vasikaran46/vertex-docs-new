export interface SlashContext {
  activeAttachment: {
    id: string;
    filename: string;
    extension: string;
  } | null;
  lastAssistantMessageText: string | null;
  availableLanguages: [string, string][];
  conversionOptions: Array<{
    format: string;
    label: string;
    available: boolean;
    approximate?: boolean;
    note?: string;
  }>;
}

export interface SlashActionContext extends SlashContext {
  argument: string;
  sendMessage: (customText?: string, action?: string) => Promise<void>;
  handleConvertAttachment: (targetFormat?: string) => Promise<void>;
  clearChat: () => void;
  showNotice: (msg: string) => void;
  setLanguage: (lang: string) => void;
}

export interface SlashSuggestion {
  value: string;
  label: string;
  hint?: string;
}

export interface SlashCommand {
  id: string;
  name: string; // e.g. "/summarize"
  description: string;
  argHint?: string;
  acceptsArg?: boolean;
  getSuggestions?: (query: string, context: SlashContext) => SlashSuggestion[];
  execute: (context: SlashActionContext) => void | Promise<void>;
}

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    id: 'summarize',
    name: '/summarize',
    description: 'Summarize the attached document or the last assistant message',
    argHint: '',
    acceptsArg: false,
    execute: async (ctx) => {
      if (ctx.activeAttachment) {
        await ctx.sendMessage(
          'Summarize this document clearly with key takeaways and action items.',
          'summarize'
        );
      } else if (ctx.lastAssistantMessageText) {
        await ctx.sendMessage(
          'Summarize your previous response concisely with key takeaways and main points.'
        );
      } else {
        ctx.showNotice('Please attach a document or ask a question first to summarize.');
      }
    },
  },
  {
    id: 'translate',
    name: '/translate',
    description: 'Translate attached document or last response into chosen language',
    argHint: '<language>',
    acceptsArg: true,
    getSuggestions: (query, ctx) => {
      const q = query.trim().toLowerCase();
      const list = ctx.availableLanguages.map(([code, label]) => ({
        value: label,
        label,
        hint: code,
      }));
      if (!q) return list;
      return list.filter(
        (item) =>
          item.label.toLowerCase().includes(q) ||
          item.hint.toLowerCase().includes(q)
      );
    },
    execute: async (ctx) => {
      const targetQuery = ctx.argument.trim().toLowerCase();
      let matchedLang = ctx.availableLanguages.find(
        ([code, label]) =>
          code.toLowerCase() === targetQuery ||
          label.toLowerCase() === targetQuery ||
          label.toLowerCase().startsWith(targetQuery)
      );

      const targetLangName = matchedLang ? matchedLang[1] : ctx.argument.trim() || 'English';
      if (matchedLang) {
        ctx.setLanguage(matchedLang[0]);
      }

      if (ctx.activeAttachment) {
        await ctx.sendMessage(
          `Translate the core content of this document into ${targetLangName}.`,
          'translate'
        );
      } else if (ctx.lastAssistantMessageText) {
        await ctx.sendMessage(
          `Translate your previous response into ${targetLangName}.`
        );
      } else {
        ctx.showNotice(`Please attach a document or ask a question to translate into ${targetLangName}.`);
      }
    },
  },
  {
    id: 'convert',
    name: '/convert',
    description: 'Convert attached file to another format (PDF, DOCX, TXT, PPTX, etc.)',
    argHint: '<format>',
    acceptsArg: true,
    getSuggestions: (query, ctx) => {
      const q = query.trim().toLowerCase();
      if (ctx.activeAttachment && ctx.conversionOptions.length > 0) {
        return ctx.conversionOptions
          .filter(
            (opt) =>
              !q ||
              opt.format.toLowerCase().includes(q) ||
              opt.label.toLowerCase().includes(q)
          )
          .map((opt) => ({
            value: opt.format,
            label: opt.label,
            hint: opt.available
              ? opt.approximate
                ? 'Approximate layout'
                : 'Supported'
              : opt.note || 'Unavailable',
          }));
      }

      // Default common options if no options loaded yet
      const fallbackFormats = [
        { value: 'pdf', label: 'Convert to PDF', hint: 'Universal PDF' },
        { value: 'docx', label: 'Convert to DOCX', hint: 'Word Document' },
        { value: 'txt', label: 'Convert to TXT', hint: 'Plain text' },
        { value: 'pptx', label: 'Convert to PPTX', hint: 'PowerPoint Presentation' },
        { value: 'xlsx', label: 'Convert to XLSX', hint: 'Excel Spreadsheet' },
        { value: 'png', label: 'Convert to Images (PNG ZIP)', hint: 'Page images archive' },
      ];
      return fallbackFormats.filter(
        (f) => !q || f.value.includes(q) || f.label.toLowerCase().includes(q)
      );
    },
    execute: async (ctx) => {
      if (!ctx.activeAttachment) {
        ctx.showNotice('Please attach or choose a document first to use /convert.');
        return;
      }
      const fmt = ctx.argument.trim().toLowerCase();
      if (fmt) {
        await ctx.handleConvertAttachment(fmt);
      } else {
        await ctx.handleConvertAttachment();
      }
    },
  },
  {
    id: 'clear',
    name: '/clear',
    description: 'Clear the current conversation history (with 5-second undo)',
    argHint: '',
    acceptsArg: false,
    execute: (ctx) => {
      ctx.clearChat();
    },
  },
];

/**
 * Parses user input to determine if a slash command is active and returns suggestions.
 */
export function parseSlashState(
  input: string,
  context: SlashContext
): {
  isOpen: boolean;
  mode: 'command' | 'argument' | 'none';
  activeCommand: SlashCommand | null;
  query: string;
  suggestions: Array<{ value: string; label: string; hint?: string; command?: SlashCommand }>;
} {
  const trimmed = input.trimStart();
  if (!trimmed.startsWith('/')) {
    return { isOpen: false, mode: 'none', activeCommand: null, query: '', suggestions: [] };
  }

  const spaceIndex = trimmed.indexOf(' ');

  if (spaceIndex === -1) {
    // User is typing command name: e.g. "/sum"
    const query = trimmed.toLowerCase();
    const suggestions = SLASH_COMMANDS.filter((cmd) => {
      if (!query || query === '/') return true;
      const cmdName = cmd.name.toLowerCase();
      return cmdName.startsWith(query) || cmd.id.includes(query.slice(1));
    }).map((cmd) => ({
      value: cmd.name,
      label: cmd.name,
      hint: cmd.argHint ? `${cmd.argHint} — ${cmd.description}` : cmd.description,
      command: cmd,
    }));

    return {
      isOpen: suggestions.length > 0,
      mode: 'command',
      activeCommand: null,
      query,
      suggestions,
    };
  }

  // User has typed command and a space: e.g. "/translate " or "/translate french"
  const cmdName = trimmed.slice(0, spaceIndex).toLowerCase();
  const activeCommand = SLASH_COMMANDS.find(
    (cmd) => cmd.name.toLowerCase() === cmdName || `/${cmd.id.toLowerCase()}` === cmdName
  );

  if (!activeCommand || !activeCommand.acceptsArg || !activeCommand.getSuggestions) {
    return { isOpen: false, mode: 'none', activeCommand: null, query: '', suggestions: [] };
  }

  const argQuery = trimmed.slice(spaceIndex + 1);
  const suggestions = activeCommand.getSuggestions(argQuery, context).map((s) => ({
    ...s,
    command: activeCommand,
  }));

  return {
    isOpen: suggestions.length > 0,
    mode: 'argument',
    activeCommand,
    query: argQuery,
    suggestions,
  };
}

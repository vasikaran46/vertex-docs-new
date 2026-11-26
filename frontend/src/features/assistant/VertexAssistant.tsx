import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, useDragControls, useReducedMotion, type Variants } from 'framer-motion';
import {
  Sparkles,
  FilePlus2,
  X,
  Trash2,
  Edit2,
  Check,
  UploadCloud,
  FileText,
  Volume2,
  Send,
  Mic,
  Copy,
  RotateCcw,
  Square,
  AlertCircle,
  FileQuestion,
  BookOpen,
  ListOrdered,
  Globe,
  ArrowRightLeft,
  RefreshCw,
  History,
  FolderOpen,
  Search,
  ArrowDownToLine,
} from 'lucide-react';
import { MarkdownMessage, DownloadCard, DownloadCardProps } from './MarkdownMessage';
import { MacOSTrafficLights } from './MacOSTrafficLights';
import { LanguagePopover } from './LanguagePopover';
import { SlashCommandMenu } from './SlashCommandMenu';
import {
  SLASH_COMMANDS,
  parseSlashState,
  SlashContext,
  SlashActionContext,
  SlashCommand,
} from './slashCommands';
import './chatbot.css';

// =========================================================================
// CONFIGURATION & TIMING CONSTANTS (Tune in one place)
// =========================================================================
export const REMEMBER_POSITION = false; // false = re-center on every open, true = restore drag offset
export const GENIE_SPRING = { stiffness: 260, damping: 26 };
export const GENIE_OPEN_BEZIER = [0.22, 1, 0.36, 1] as const;
export const GENIE_OPEN_DURATION = 0.42; // 420ms
export const GENIE_CLOSE_DURATION = 0.28; // 280ms ease-in
export const GENIE_USE_SPRING = true; // toggle between spring (stiffness 260, damping 26) or 420ms bezier

const MIN_WIDTH = 380;
const MIN_HEIGHT = 500;
const DRAG_OFFSET_STORAGE_KEY = 'vertex_assistant_drag_offset_v3';

export interface ChatMessage {
  id?: number;
  role: 'user' | 'assistant';
  text: string;
  created_at?: string;
  isStreaming?: boolean;
  artifacts?: DownloadCardProps[];
  downloadCard?: DownloadCardProps;
}

export interface ChatConversation {
  id: number;
  title: string;
  updated_at: string;
}

export interface AttachmentInfo {
  id: string;
  filename: string;
  size: number;
  extension: string;
  is_image?: boolean;
  is_scanned?: boolean;
  text_preview?: string;
}

interface VertexAssistantProps {
  api: string;
  token: string | null;
  companion: { emoji: string; name: string };
  language: string;
  languages: [string, string][];
  onLanguageChange: (lang: string) => void;
  onClose: () => void;
  speakText: (text: string, lang?: string) => void;
  isListening: boolean;
  startVoiceInput: (onResult: (text: string) => void) => void;
  voiceFeedback: string;
  setNotice: (msg: string) => void;
  onNewUnread?: () => void;
}

const getInitialWindowSize = () => {
  const winW = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const winH = typeof window !== 'undefined' ? window.innerHeight : 800;
  return {
    w: Math.min(920, Math.max(MIN_WIDTH, Math.floor(winW * 0.92))),
    h: Math.min(640, Math.max(MIN_HEIGHT, Math.floor(winH * 0.88))),
  };
};

export function VertexAssistant({
  api,
  token,
  companion,
  language,
  languages,
  onLanguageChange,
  onClose,
  speakText,
  isListening,
  startVoiceInput,
  voiceFeedback,
  setNotice,
}: VertexAssistantProps) {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [lastFailedPrompt, setLastFailedPrompt] = useState<string | null>(null);

  // Attachments
  const [activeAttachment, setActiveAttachment] = useState<AttachmentInfo | null>(null);
  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [conversionFormat, setConversionFormat] = useState<string>('pdf');
  const [conversionOptions, setConversionOptions] = useState<Array<{
    format: string;
    label: string;
    available: boolean;
    approximate?: boolean;
    note?: string;
  }>>([]);
  const [conversionBusy, setConversionBusy] = useState(false);

  // Document picker & drag-and-drop state
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [workspaceDocs, setWorkspaceDocs] = useState<Array<{
    id: number;
    original_name: string;
    size: number;
    content_type?: string;
    created_at?: string;
  }>>([]);
  const [docSearch, setDocSearch] = useState('');
  const [docPickerLoading, setDocPickerLoading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  // Language Popover State
  const [isLanguagePopoverOpen, setIsLanguagePopoverOpen] = useState(false);

  // Slash commands state
  const [slashSelectedIndex, setSlashSelectedIndex] = useState(0);
  const [slashMenuForceClosed, setSlashMenuForceClosed] = useState(false);

  // Undo Clear Chat state
  const [undoClearState, setUndoClearState] = useState<{
    messages: ChatMessage[];
    timer: ReturnType<typeof setTimeout> | null;
  } | null>(null);

  // Scroll-to-bottom indicator
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Rename conversation state
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [editTitleText, setEditTitleText] = useState('');

  // Feedback states
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [speakingMsgIndex, setSpeakingMsgIndex] = useState<number | null>(null);

  // Window sizing & maximize state
  const [windowSize, setWindowSize] = useState(getInitialWindowSize);
  const [isMaximized, setIsMaximized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [historyOpenNarrow, setHistoryOpenNarrow] = useState(false);

  // Genie animation state
  const [clipPathFinished, setClipPathFinished] = useState(false);
  const shouldReduceMotion = useReducedMotion();

  // Drag controls & layer ref
  const dragControls = useDragControls();
  const layerRef = useRef<HTMLDivElement | null>(null);

  // AbortController for streaming & element refs
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const windowRef = useRef<HTMLDivElement | null>(null);

  const resizeRef = useRef<{
    isResizing: boolean;
    startX: number;
    startY: number;
    initialW: number;
    initialH: number;
  }>({ isResizing: false, startX: 0, startY: 0, initialW: 0, initialH: 0 });

  // Slash Context
  const lastAssistantMessage = [...messages].reverse().find((m) => m.role === 'assistant');
  const slashContext: SlashContext = {
    activeAttachment,
    lastAssistantMessageText: lastAssistantMessage?.text || null,
    availableLanguages: languages,
    conversionOptions,
  };

  const slashState = parseSlashState(input, slashContext);

  // Reset slash index when suggestions change
  useEffect(() => {
    setSlashSelectedIndex(0);
  }, [slashState.suggestions.length, slashState.mode]);

  // Compute genie fold target metrics relative to floating button
  const computeGenieMetrics = useCallback(() => {
    if (typeof window === 'undefined') {
      return { dx: 0, dy: 0, bx: 90, by: 90 };
    }
    const fab = document.querySelector('.assistant-fab');
    const fabRect = fab?.getBoundingClientRect() || {
      left: window.innerWidth - 88,
      top: window.innerHeight - 88,
      width: 66,
      height: 66,
    };
    const btnCenterX = fabRect.left + fabRect.width / 2;
    const btnCenterY = fabRect.top + fabRect.height / 2;

    const winW = isMaximized ? window.innerWidth - 24 : windowSize.w;
    const winH = isMaximized ? window.innerHeight - 24 : windowSize.h;
    const winLeft = (window.innerWidth - winW) / 2;
    const winTop = (window.innerHeight - winH) / 2;
    const winCenterX = winLeft + winW / 2;
    const winCenterY = winTop + winH / 2;

    const dx = btnCenterX - winCenterX;
    const dy = btnCenterY - winCenterY;

    const bx = Math.min(Math.max(Math.round(((btnCenterX - winLeft) / winW) * 100), 0), 100);
    const by = Math.min(Math.max(Math.round(((btnCenterY - winTop) / winH) * 100), 0), 100);

    return { dx, dy, bx, by };
  }, [isMaximized, windowSize.w, windowSize.h]);

  const [genieMetrics, setGenieMetrics] = useState(computeGenieMetrics);

  useEffect(() => {
    const updateMetrics = () => setGenieMetrics(computeGenieMetrics());
    updateMetrics();
    window.addEventListener('resize', updateMetrics);
    window.addEventListener('scroll', updateMetrics, true);
    return () => {
      window.removeEventListener('resize', updateMetrics);
      window.removeEventListener('scroll', updateMetrics, true);
    };
  }, [computeGenieMetrics]);

  // Autofocus input on open and return focus to floating button on unmount
  useEffect(() => {
    const timer = setTimeout(() => {
      textareaRef.current?.focus();
    }, 80);
    return () => {
      clearTimeout(timer);
      const fab = document.querySelector<HTMLElement>('.assistant-fab');
      fab?.focus();
    };
  }, []);

  // Auto-grow textarea up to 6 lines (~140px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 38), 140)}px`;
    }
  }, [input]);

  // Dynamic conversion options when attachment changes
  useEffect(() => {
    if (!activeAttachment || !token) {
      setConversionOptions([]);
      return;
    }
    let isCurrent = true;
    fetch(`${api}/api/chat/convert/options?attachment_id=${activeAttachment.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        if (isCurrent && Array.isArray(data.options)) {
          setConversionOptions(data.options);
          const available = data.options.filter((o: any) => o.available);
          if (available.length > 0) {
            const hasFormat = available.some((o: any) => o.format === conversionFormat);
            if (!hasFormat) {
              setConversionFormat(available[0].format);
            }
          }
        }
      })
      .catch((err) => {
        console.warn('Could not load conversion options:', err);
      });
    return () => {
      isCurrent = false;
    };
  }, [activeAttachment?.id, token]);

  // Re-clamp window size on window resize
  useEffect(() => {
    const handleResize = () => {
      setWindowSize((prev) => {
        const maxW = Math.max(MIN_WIDTH, window.innerWidth - 24);
        const maxH = Math.max(MIN_HEIGHT, window.innerHeight - 24);
        return {
          w: Math.min(prev.w, maxW),
          h: Math.min(prev.h, maxH),
        };
      });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Keyboard navigation & layered Esc & focus trap
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Escape') {
        // Layer 1: Slash menu open?
        if (slashState.isOpen && !slashMenuForceClosed) {
          e.preventDefault();
          e.stopPropagation();
          setSlashMenuForceClosed(true);
          return;
        }
        // Layer 2: Language popover open?
        if (isLanguagePopoverOpen) {
          e.preventDefault();
          e.stopPropagation();
          setIsLanguagePopoverOpen(false);
          return;
        }
        // Layer 3: Doc picker modal open?
        if (showDocPicker) {
          e.preventDefault();
          e.stopPropagation();
          setShowDocPicker(false);
          return;
        }
        // Layer 4: Close assistant window
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [slashState.isOpen, slashMenuForceClosed, isLanguagePopoverOpen, showDocPicker, onClose]);

  // Focus trap inside the assistant panel
  const handleWindowKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
    if (e.key === 'Tab' && windowRef.current) {
      const focusables = windowRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length > 0) {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  };

  const handleToggleMaximize = () => {
    setIsMaximized((prev) => !prev);
  };

  const resetPosition = () => {
    setWindowSize(getInitialWindowSize());
    setIsMaximized(false);
  };

  const handleResizePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (window.innerWidth <= 640 || isMaximized) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    e.stopPropagation();
    resizeRef.current = {
      isResizing: true,
      startX: e.clientX,
      startY: e.clientY,
      initialW: windowSize.w,
      initialH: windowSize.h,
    };
    setIsResizing(true);
  };

  const handleResizePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeRef.current.isResizing || isMaximized) return;
    const dw = e.clientX - resizeRef.current.startX;
    const dh = e.clientY - resizeRef.current.startY;
    const maxW = window.innerWidth - 24;
    const maxH = window.innerHeight - 24;
    const newW = Math.min(Math.max(resizeRef.current.initialW + dw, MIN_WIDTH), maxW);
    const newH = Math.min(Math.max(resizeRef.current.initialH + dh, MIN_HEIGHT), maxH);
    setWindowSize({ w: newW, h: newH });
  };

  const handleResizePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeRef.current.isResizing) return;
    resizeRef.current.isResizing = false;
    setIsResizing(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}
  };

  useEffect(() => {
    if (token) {
      void loadConversations();
    }
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const handleTranscriptScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
    setShowScrollBottom(!isNearBottom);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollBottom(false);
  };

  const checkServerHealth = async (): Promise<boolean> => {
    try {
      const c = new AbortController();
      const t = setTimeout(() => c.abort(), 2500);
      const res = await fetch(`${api}/api/health`, { method: 'GET', signal: c.signal });
      clearTimeout(t);
      return res.ok;
    } catch {
      return false;
    }
  };

  const getDiagnosticError = async (err: unknown, statusCode?: number): Promise<string> => {
    if (statusCode === 401) return 'AI service key is missing or invalid. Please check backend/.env configuration.';
    if (statusCode === 429) return 'Too many requests, try again in a moment.';
    if (statusCode === 403) return 'Access forbidden: you do not have permission for this file.';
    if (statusCode === 404) return 'The requested file or attachment was not found.';
    if (statusCode === 413) return 'File too large (maximum 50 MB allowed).';
    if (statusCode === 415) return 'Unsupported file format. Supported: PDF, DOCX, TXT, MD, PPTX, XLSX, PNG, JPG, JPEG, WEBP.';
    if (statusCode === 422) return 'Invalid request. Please verify the document format and input.';
    if (statusCode === 502 || statusCode === 503) {
      return 'AI service is temporarily unavailable (LLM key missing or provider error). Non-AI conversions and file tools are still available.';
    }
    if (statusCode === 500) return 'Internal server error. Please try again.';

    const isFetchErr =
      err instanceof TypeError ||
      (err instanceof Error &&
        (err.message.toLowerCase().includes('failed to fetch') ||
          err.message.toLowerCase().includes('network') ||
          err.message.toLowerCase().includes('aborted')));

    if (isFetchErr) {
      const isUp = await checkServerHealth();
      if (isUp) {
        return 'The request was interrupted (connection reset) - retrying...';
      }
      return `Can't reach the server - is the backend running on ${api || 'http://localhost:8000'}?`;
    }
    if (err instanceof Error) {
      return err.message;
    }
    return 'An unexpected error occurred. Please try again.';
  };

  const parseErrorMessage = async (res: Response): Promise<string> => {
    try {
      const data = await res.json();
      if (res.status === 401) {
        return 'AI service key is missing or invalid. Check backend/.env configuration.';
      }
      if (res.status === 429) {
        return 'Too many requests, try again in a moment.';
      }
      if (typeof data === 'string') return data;
      if (data?.detail) {
        if (typeof data.detail === 'string') return data.detail;
        if (data.detail?.message) return data.detail.message;
        if (Array.isArray(data.detail)) {
          return data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        }
      }
      if (data?.error) return data.error;
    } catch {}
    return await getDiagnosticError(null, res.status);
  };

  const loadConversations = async () => {
    if (!token) return;
    setHistoryBusy(true);
    try {
      const res = await fetch(`${api}/api/chat/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const list = (await res.json()) as ChatConversation[];
        setConversations(list);
        if (list.length > 0 && activeChatId === null) {
          void selectConversation(list[0].id);
        }
      }
    } catch (err) {
      console.warn('Could not load chat conversations:', err);
    } finally {
      setHistoryBusy(false);
    }
  };

  const selectConversation = async (convId: number) => {
    if (!token) return;
    setActiveChatId(convId);
    setErrorMsg('');
    setHistoryOpenNarrow(false);
    try {
      const res = await fetch(`${api}/api/chat/conversations/${convId}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = (await res.json()) as Array<{
          id: number;
          role: 'user' | 'assistant';
          content: string;
          created_at: string;
        }>;
        setMessages(
          data.map((m) => {
            let text = m.content;
            let downloadCard: DownloadCardProps | undefined;
            const artifacts: DownloadCardProps[] = [];

            const cardMatch = text.match(/\[DOWNLOAD_CARD:(.*?)\]/);
            if (cardMatch) {
              try {
                downloadCard = JSON.parse(cardMatch[1]) as DownloadCardProps;
                artifacts.push(downloadCard);
                text = text.replace(cardMatch[0], '').trim();
              } catch (e) {
                console.warn('Failed to parse download card:', e);
              }
            }

            return {
              id: m.id,
              role: m.role,
              text,
              created_at: m.created_at,
              downloadCard,
              artifacts: artifacts.length > 0 ? artifacts : undefined,
            };
          })
        );
      }
    } catch (err) {
      console.warn('Could not load messages:', err);
    }
  };

  const createNewChat = async () => {
    if (!token) {
      setActiveChatId(null);
      setMessages([]);
      setErrorMsg('');
      setActiveAttachment(null);
      return;
    }
    setHistoryBusy(true);
    try {
      const res = await fetch(`${api}/api/chat/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: 'New chat' }),
      });
      if (res.ok) {
        const conv = (await res.json()) as ChatConversation;
        setConversations((prev) => [conv, ...prev]);
        setActiveChatId(conv.id);
        setMessages([]);
        setErrorMsg('');
        setActiveAttachment(null);
      }
    } catch (err) {
      console.warn('Failed to create new conversation:', err);
    } finally {
      setHistoryBusy(false);
    }
  };

  const deleteConversation = async (convId: number) => {
    if (!token) return;
    try {
      const res = await fetch(`${api}/api/chat/conversations/${convId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        if (activeChatId === convId) {
          const remaining = conversations.filter((c) => c.id !== convId);
          if (remaining.length > 0) {
            void selectConversation(remaining[0].id);
          } else {
            setActiveChatId(null);
            setMessages([]);
          }
        }
      }
    } catch (err) {
      console.warn('Failed to delete conversation:', err);
    }
  };

  const saveRename = async (convId: number) => {
    if (!token || !editTitleText.trim()) {
      setEditingTitleId(null);
      return;
    }
    try {
      const res = await fetch(`${api}/api/chat/conversations/${convId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: editTitleText.trim() }),
      });
      if (res.ok) {
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, title: editTitleText.trim() } : c))
        );
      }
    } catch (err) {
      console.warn('Failed to rename conversation:', err);
    } finally {
      setEditingTitleId(null);
    }
  };

  const handleClearChat = () => {
    if (messages.length === 0) return;
    const backup = [...messages];
    setMessages([]);
    if (undoClearState?.timer) clearTimeout(undoClearState.timer);
    const timer = setTimeout(() => {
      setUndoClearState(null);
    }, 5000);
    setUndoClearState({ messages: backup, timer });
  };

  const handleUndoClear = () => {
    if (undoClearState) {
      if (undoClearState.timer) clearTimeout(undoClearState.timer);
      setMessages(undoClearState.messages);
      setUndoClearState(null);
    }
  };

  const handleFileSelected = async (file: File) => {
    if (!token) {
      setErrorMsg('Please sign in to upload and attach documents.');
      return;
    }

    if (file.size === 0) {
      setErrorMsg('The selected file is empty (0 bytes). Please select a valid document.');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setErrorMsg('File too large (maximum 50 MB allowed).');
      return;
    }

    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const allowed = ['pdf', 'docx', 'txt', 'md', 'pptx', 'xlsx', 'png', 'jpg', 'jpeg', 'webp'];
    if (!allowed.includes(ext)) {
      setErrorMsg(`Unsupported file type ".${ext}". Supported: ${allowed.join(', ').toUpperCase()}`);
      return;
    }

    setAttachmentUploading(true);
    setErrorMsg('');

    const form = new FormData();
    form.append('file', file);
    if (activeChatId) {
      form.append('conversation_id', String(activeChatId));
    }

    try {
      const res = await fetch(`${api}/api/chat/attachments`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!res.ok) {
        const errorText = await parseErrorMessage(res);
        setErrorMsg(errorText);
        return;
      }

      const att = (await res.json()) as AttachmentInfo;
      setActiveAttachment(att);
      const isImg = att.is_image || ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
      setConversionFormat(isImg ? 'pdf' : ext === 'pdf' ? 'docx' : 'pdf');
      setNotice(`Attached ${file.name}`);
    } catch (err) {
      const msg = await getDiagnosticError(err);
      setErrorMsg(msg);
    } finally {
      setAttachmentUploading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      void handleFileSelected(file);
    }
    e.target.value = '';
  };

  const openDocPicker = async () => {
    if (!token) {
      setErrorMsg('Please sign in to choose from your documents.');
      return;
    }
    setShowDocPicker(true);
    setDocPickerLoading(true);
    setDocSearch('');
    try {
      const res = await fetch(`${api}/api/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const docs = await res.json();
        setWorkspaceDocs(docs);
      } else {
        const err = await parseErrorMessage(res);
        setErrorMsg(err);
      }
    } catch (err) {
      const msg = await getDiagnosticError(err);
      setErrorMsg(msg);
    } finally {
      setDocPickerLoading(false);
    }
  };

  const handleAttachWorkspaceDoc = async (docId: number) => {
    if (!token) return;
    setDocPickerLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch(`${api}/api/chat/attachments/from-document`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          document_id: docId,
          conversation_id: activeChatId,
        }),
      });

      if (!res.ok) {
        const err = await parseErrorMessage(res);
        setErrorMsg(err);
        return;
      }

      const att = (await res.json()) as AttachmentInfo;
      setActiveAttachment(att);
      const ext = att.filename.split('.').pop()?.toLowerCase() || '';
      const isImg = att.is_image || ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
      setConversionFormat(isImg ? 'pdf' : ext === 'pdf' ? 'docx' : 'pdf');
      setShowDocPicker(false);
      setNotice(`Attached ${att.filename} from your workspace.`);
    } catch (err) {
      const msg = await getDiagnosticError(err);
      setErrorMsg(msg);
    } finally {
      setDocPickerLoading(false);
    }
  };

  const handleFocusConversion = (targetFormat?: string) => {
    if (targetFormat) {
      setConversionFormat(targetFormat);
    }
  };

  const handleConvertAttachment = async (targetFmt?: string) => {
    const fmt = targetFmt || conversionFormat;
    if (!token) {
      setErrorMsg('Please sign in to convert documents.');
      return;
    }
    if (!activeAttachment) {
      setErrorMsg('Please attach or select a document first.');
      return;
    }

    const selectedOpt = conversionOptions.find((o) => o.format === fmt);
    if (selectedOpt && !selectedOpt.available) {
      setErrorMsg(selectedOpt.note || `Conversion to ${fmt.toUpperCase()} is currently unavailable.`);
      return;
    }

    setConversionBusy(true);
    setErrorMsg('');

    const form = new FormData();
    form.append('attachment_id', activeAttachment.id);
    form.append('target_format', fmt);
    if (activeChatId) {
      form.append('conversation_id', String(activeChatId));
    }

    try {
      const res = await fetch(`${api}/api/chat/convert`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!res.ok) {
        const errorText = await parseErrorMessage(res);
        setErrorMsg(errorText);
        return;
      }

      const data = await res.json();
      const artifact = data.artifact;
      const approximate = Boolean(data.approximate);

      const noteText = approximate ? '\n*Note: Layout is approximate - review the result.*' : '';
      const newMsg: ChatMessage = {
        role: 'assistant',
        text: `Your ${fmt.toUpperCase()} conversion of **${artifact.filename}** is ready!${noteText}`,
        downloadCard: artifact,
        artifacts: [artifact],
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, newMsg]);
      setNotice(`Converted ${artifact.filename}`);
    } catch (err) {
      const msg = await getDiagnosticError(err);
      setErrorMsg(msg);
    } finally {
      setConversionBusy(false);
    }
  };

  const handleCopyMessage = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch {
      setNotice('Could not copy to clipboard.');
    }
  };

  const handleSpeakMessage = (text: string, index: number) => {
    setSpeakingMsgIndex(index);
    speakText(text, language);
    const approxDuration = Math.min(10000, Math.max(2500, text.length * 60));
    setTimeout(() => {
      setSpeakingMsgIndex((cur) => (cur === index ? null : cur));
    }, approxDuration);
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setBusy(false);
  };

  const handleRegenerate = async () => {
    if (messages.length < 2) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;
    setMessages((prev) => prev.filter((_, idx) => idx !== prev.length - 1));
    await sendMessage(lastUserMsg.text);
  };

  const handleRetryFailed = async () => {
    setErrorMsg('');
    if (lastFailedPrompt) {
      await sendMessage(lastFailedPrompt);
    }
  };

  const sendMessage = async (customPrompt?: string, action?: string) => {
    const textToSend = customPrompt !== undefined ? customPrompt : input;
    if (!textToSend.trim() && !activeAttachment) return;
    if (!token) {
      setErrorMsg('Please sign in to send messages to Vertex Assistant.');
      return;
    }

    const trimmed = textToSend.trim();
    const isDocSpecific = /^(summarize|explain|key\s*points|translate|convert)\b/i.test(trimmed);
    const hasHistory = messages.some((m) => m.role === 'assistant');
    if (!activeAttachment && !hasHistory && isDocSpecific && trimmed.length < 30 && !trimmed.startsWith('/')) {
      setErrorMsg('Please attach a document or ask a question first to summarize.');
      return;
    }

    if (customPrompt === undefined) {
      setInput('');
    }
    setErrorMsg('');
    setLastFailedPrompt(textToSend);

    const userMsg: ChatMessage = {
      role: 'user',
      text: textToSend,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);

    const assistantMsg: ChatMessage = {
      role: 'assistant',
      text: '',
      isStreaming: true,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const payload: any = {
        text: textToSend,
        language,
        conversation_id: activeChatId,
        stream: true,
      };

      if (activeAttachment) {
        payload.attachment_ids = [activeAttachment.id];
      }
      if (action) {
        payload.action = action;
      }

      const res = await fetch(`${api}/api/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
        signal: abortController.signal,
      });

      if (!res.ok) {
        const errorText = await parseErrorMessage(res);
        if (import.meta.env.DEV) {
          console.error('[Vertex Assistant Error]', res.status, errorText);
        }
        setErrorMsg(errorText);
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last && last.role === 'assistant') {
            last.isStreaming = false;
            last.text = `Unable to complete request: ${errorText}`;
          }
          return copy;
        });
        return;
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      let accumulatedText = '';
      let artifacts: DownloadCardProps[] = [];

      if (reader) {
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine.startsWith('data:')) continue;
            const dataStr = trimmedLine.slice(5).trim();
            if (dataStr === '[DONE]') continue;

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.error) {
                accumulatedText = `Unable to complete request: ${parsed.error}`;
                setErrorMsg(parsed.error);
                if (import.meta.env.DEV) {
                  console.error('[Vertex Assistant Stream Error]', parsed.error);
                }
                setMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === 'assistant') {
                    last.isStreaming = false;
                    last.text = accumulatedText;
                  }
                  return copy;
                });
                break;
              }

              const deltaText = parsed.delta || parsed.token || '';
              if (deltaText) {
                accumulatedText += deltaText;
                setMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === 'assistant') {
                    last.text = accumulatedText;
                  }
                  return copy;
                });
              } else if (parsed.artifact) {
                artifacts.push(parsed.artifact);
              } else if (parsed.done && parsed.reply && !accumulatedText) {
                accumulatedText = parsed.reply;
              }
            } catch {}
          }
        }
      }

      // If empty reply returned, show friendly assistant error
      if (!accumulatedText.trim()) {
        accumulatedText = 'Unable to complete request: The AI provider returned an empty reply. Please retry.';
      }

      // Check for download cards in text
      const cardMatch = accumulatedText.match(/\[DOWNLOAD_CARD:(.*?)\]/);
      if (cardMatch) {
        try {
          const parsedCard = JSON.parse(cardMatch[1]) as DownloadCardProps;
          artifacts.push(parsedCard);
          accumulatedText = accumulatedText.replace(cardMatch[0], '').trim();
        } catch {}
      }

      // Finalize assistant message
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last && last.role === 'assistant') {
          last.isStreaming = false;
          last.text = accumulatedText;
          if (artifacts.length > 0) {
            last.artifacts = artifacts;
            last.downloadCard = artifacts[0];
          }
        }
        return copy;
      });

      void loadConversations();
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      const msg = await getDiagnosticError(err);
      if (import.meta.env.DEV) {
        console.error('[Vertex Assistant Exception]', err);
      }
      setErrorMsg(msg);
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last && last.role === 'assistant') {
          last.isStreaming = false;
          last.text = `Unable to complete request: ${msg}`;
        }
        return copy;
      });
    } finally {
      setBusy(false);
      abortControllerRef.current = null;
    }
  };

  const handleSelectSlashItem = (item: {
    value: string;
    label: string;
    hint?: string;
    command?: SlashCommand;
  }) => {
    if (slashState.mode === 'command') {
      const cmd = item.command;
      if (!cmd) return;

      if (cmd.acceptsArg) {
        setInput(`${cmd.name} `);
        setSlashSelectedIndex(0);
        textareaRef.current?.focus();
      } else {
        setInput('');
        setSlashMenuForceClosed(true);
        const actionContext: SlashActionContext = {
          ...slashContext,
          argument: '',
          sendMessage: async (p, a) => {
            await sendMessage(p, a);
          },
          handleConvertAttachment: async (targetFormat) => {
            await handleConvertAttachment(targetFormat);
          },
          clearChat: () => {
            handleClearChat();
          },
          showNotice: (msg) => {
            setNotice(msg);
          },
          setLanguage: (lang) => {
            onLanguageChange(lang);
          },
        };
        void cmd.execute(actionContext);
      }
    } else if (slashState.mode === 'argument') {
      const cmd = slashState.activeCommand;
      if (!cmd) return;
      setInput('');
      setSlashMenuForceClosed(true);
      const actionContext: SlashActionContext = {
        ...slashContext,
        argument: item.value,
        sendMessage: async (p, a) => {
          await sendMessage(p, a);
        },
        handleConvertAttachment: async (targetFormat) => {
          await handleConvertAttachment(targetFormat);
        },
        clearChat: () => {
          handleClearChat();
        },
        showNotice: (msg) => {
          setNotice(msg);
        },
        setLanguage: (lang) => {
          onLanguageChange(lang);
        },
      };
      void cmd.execute(actionContext);
    }
  };

  const handleSendMessageOrSlash = async (customPrompt?: string, action?: string) => {
    const textToSend = customPrompt !== undefined ? customPrompt : input;
    const trimmed = textToSend.trim();

    if (trimmed.startsWith('/') && customPrompt === undefined) {
      const spaceIdx = trimmed.indexOf(' ');
      const cmdName = (spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx)).toLowerCase();
      const arg = spaceIdx === -1 ? '' : trimmed.slice(spaceIdx + 1).trim();

      const matchedCmd = SLASH_COMMANDS.find(
        (c) => c.name.toLowerCase() === cmdName || `/${c.id.toLowerCase()}` === cmdName
      );

      if (matchedCmd) {
        setInput('');
        setSlashMenuForceClosed(true);
        const actionContext: SlashActionContext = {
          ...slashContext,
          argument: arg,
          sendMessage: async (p, a) => {
            await sendMessage(p, a);
          },
          handleConvertAttachment: async (targetFormat) => {
            await handleConvertAttachment(targetFormat);
          },
          clearChat: () => {
            handleClearChat();
          },
          showNotice: (msg) => {
            setNotice(msg);
          },
          setLanguage: (lang) => {
            onLanguageChange(lang);
          },
        };

        await matchedCmd.execute(actionContext);
        return;
      }

      setErrorMsg('Unknown command, type / to see options.');
      return;
    }

    await sendMessage(customPrompt, action);
  };

  const handleComposerKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashState.isOpen && !slashMenuForceClosed && slashState.suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashSelectedIndex((prev) => (prev + 1) % slashState.suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashSelectedIndex((prev) => (prev - 1 + slashState.suggestions.length) % slashState.suggestions.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault();
        const currentItem = slashState.suggestions[slashSelectedIndex];
        if (currentItem) {
          handleSelectSlashItem(currentItem);
          return;
        }
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setSlashMenuForceClosed(true);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSendMessageOrSlash();
    }
  };

  const isNarrow = windowSize.w < 560;
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;

  const activeTitle =
    conversations.find((c) => c.id === activeChatId)?.title ||
    (messages.length ? 'Active chat' : 'New chat');

  // Genie 4-vertex clip-path interpolation
  const bx = genieMetrics.bx;
  const by = genieMetrics.by;
  const skewDirection = genieMetrics.dx > 0 ? -8 : 8;

  const initialClipPolygon = `polygon(${Math.max(0, bx - 4)}% ${Math.max(0, by - 4)}%, ${Math.min(
    100,
    bx + 4
  )}% ${Math.max(0, by - 4)}%, ${Math.min(100, bx + 4)}% ${Math.min(100, by + 4)}%, ${Math.max(
    0,
    bx - 4
  )}% ${Math.min(100, by + 4)}%)`;
  const fullClipPolygon = 'polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)';

  // LAYER 1 Genie-fold Motion Variants
  const genieVariants: Variants = {
    initial: shouldReduceMotion
      ? { opacity: 0, scale: 0.98 }
      : {
          x: genieMetrics.dx,
          y: genieMetrics.dy,
          scale: 0.05,
          opacity: 0,
          skewX: skewDirection,
          skewY: 4,
        },
    animate: shouldReduceMotion
      ? { opacity: 1, scale: 1, transition: { duration: 0.15 } }
      : {
          x: 0,
          y: 0,
          scale: 1,
          opacity: 1,
          skewX: 0,
          skewY: 0,
          transition: {
            x: { type: 'spring' as const, stiffness: GENIE_SPRING.stiffness, damping: GENIE_SPRING.damping },
            y: { type: 'spring' as const, stiffness: GENIE_SPRING.stiffness, damping: GENIE_SPRING.damping },
            scale: { type: 'spring' as const, stiffness: GENIE_SPRING.stiffness, damping: GENIE_SPRING.damping },
            skewX: { duration: GENIE_OPEN_DURATION, ease: GENIE_OPEN_BEZIER },
            skewY: { duration: GENIE_OPEN_DURATION, ease: GENIE_OPEN_BEZIER },
            opacity: { duration: 0.22 },
          },
        },
    exit: shouldReduceMotion
      ? { opacity: 0, scale: 0.98, transition: { duration: 0.15 } }
      : {
          x: genieMetrics.dx,
          y: genieMetrics.dy,
          scale: 0.05,
          opacity: 0,
          skewX: skewDirection,
          skewY: 4,
          transition: {
            duration: GENIE_CLOSE_DURATION,
            ease: 'easeIn' as const,
          },
        },
  };

  const windowStyle: React.CSSProperties = isMobile
    ? {
        width: 'calc(100vw - 16px)',
        height: 'calc(100vh - 16px)',
      }
    : isMaximized
    ? {
        width: 'calc(100vw - 24px)',
        height: 'calc(100vh - 24px)',
      }
    : {
        width: `${windowSize.w}px`,
        height: `${windowSize.h}px`,
      };

  const genieStyle: React.CSSProperties = {
    transformOrigin: `${bx}% ${by}%`,
  };

  if (typeof document === 'undefined') return null;

  return createPortal(
    /* ChatbotLayer: fixed inset:0, flex centered, pointer-events: none, dragConstraint */
    <div
      ref={layerRef}
      className="chatbot-layer-portal"
      aria-hidden="false"
    >
      {/* LAYER 1: Handles ONLY open/close genie fold animation */}
      <motion.div
        className="assistant-genie-layer"
        style={genieStyle}
        initial="initial"
        animate="animate"
        exit="exit"
        variants={genieVariants}
        onAnimationComplete={(definition) => {
          if (definition === 'animate') {
            setClipPathFinished(true);
          }
        }}
      >
        {/* LAYER 2: Handles ONLY dragging and window chrome/resizing */}
        <motion.div
          ref={windowRef}
          className={`assistant-window-container assistant-panel ${
            isMaximized ? 'is-maximized' : ''
          } ${isDragging ? 'assistant-panel-dragging' : ''} ${
            isResizing ? 'assistant-panel-resizing' : ''
          }`}
          style={windowStyle}
          drag={!isMaximized && !isMobile}
          dragControls={dragControls}
          dragListener={false}
          dragMomentum={false}
          dragElastic={0}
          dragConstraints={layerRef}
          onDragStart={() => setIsDragging(true)}
          onDragEnd={() => setIsDragging(false)}
          onKeyDown={handleWindowKeyDown}
          role="dialog"
          aria-label="Vertex Assistant"
        >
          {/* Fades content in during last 40% so it is never squashed */}
          <motion.div
            className="assistant-content-wrapper"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { duration: 0.22, delay: 0.16 } }}
            exit={{ opacity: 0, transition: { duration: 0.08 } }}
          >
            {/* macOS-style Header & Drag Handle */}
            <header
              className="assistant-header"
              tabIndex={0}
              role="region"
              aria-label="Vertex Assistant header, drag to move, double-click to toggle maximize"
              onPointerDown={(e) => {
                const target = e.target as HTMLElement;
                if (target.closest('button, input, select, a, textarea, .macos-traffic-lights')) return;
                dragControls.start(e);
              }}
              onDoubleClick={(e) => {
                const target = e.target as HTMLElement;
                if (!target.closest('button, input, select, a, textarea, .macos-traffic-lights')) {
                  handleToggleMaximize();
                }
              }}
            >
              <MacOSTrafficLights
                onClose={onClose}
                onMinimize={onClose}
                onMaximizeToggle={handleToggleMaximize}
                isMaximized={isMaximized}
              />

              <div className="assistant-header-app-icon" aria-hidden="true">
                <Sparkles size={18} />
              </div>

              <div className="assistant-header-titles">
                <b className="assistant-header-title">Vertex Assistant</b>
                <small
                  className="assistant-header-subtitle"
                  title={`${activeTitle} · ${companion.name}`}
                >
                  {activeTitle} · {companion.name}
                </small>
              </div>

              <div className="assistant-header-spacer" />

              {isNarrow && (
                <button
                  className="icon-button"
                  title={historyOpenNarrow ? 'Back to chat' : 'View chat history'}
                  aria-label="Toggle chat history"
                  onClick={() => setHistoryOpenNarrow((prev) => !prev)}
                >
                  <History size={16} />
                </button>
              )}

              <button
                className="icon-button"
                title="Reset window size"
                aria-label="Reset window size"
                onClick={resetPosition}
              >
                <RotateCcw size={15} />
              </button>

              <button
                className="assistant-new-chat"
                disabled={!token || historyBusy}
                onClick={() => void createNewChat()}
                title="Start fresh conversation"
              >
                <FilePlus2 size={15} /> New chat
              </button>

              <button
                className="icon-button"
                aria-label="Close assistant"
                onClick={onClose}
              >
                <X size={18} />
              </button>
            </header>

            <div
              className={`assistant-workspace ${isNarrow ? 'is-narrow' : ''} ${
                historyOpenNarrow ? 'show-history-narrow' : ''
              }`}
            >
              {/* Chat History Sidebar */}
              <aside className="assistant-history">
                <b>Chat history</b>
                {historyBusy && <small>Loading chats…</small>}
                {!historyBusy && !conversations.length && <small>Your chats will appear here.</small>}
                {conversations.map((c) => (
                  <motion.div
                    layout
                    className={`assistant-history-item ${activeChatId === c.id ? 'active' : ''}`}
                    key={c.id}
                    transition={{ duration: 0.16 }}
                  >
                    {editingTitleId === c.id ? (
                      <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 4 }}>
                        <input
                          value={editTitleText}
                          autoFocus
                          onChange={(e) => setEditTitleText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') void saveRename(c.id);
                            if (e.key === 'Escape') setEditingTitleId(null);
                          }}
                        />
                        <button onClick={() => void saveRename(c.id)} title="Save title">
                          <Check size={12} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          title={c.title}
                          onClick={() => void selectConversation(c.id)}
                          style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis' }}
                        >
                          {c.title}
                        </button>
                        <button
                          title="Rename chat"
                          onClick={() => {
                            setEditingTitleId(c.id);
                            setEditTitleText(c.title);
                          }}
                        >
                          <Edit2 size={12} />
                        </button>
                        <button
                          aria-label={`Delete ${c.title}`}
                          title="Delete chat"
                          onClick={() => void deleteConversation(c.id)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </>
                    )}
                  </motion.div>
                ))}
                {!token && <small>Sign in to keep private chat history.</small>}
              </aside>

              {/* Main Chat Area */}
              <div
                className="assistant-chat-main"
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                    setIsDragOver(false);
                  }
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) {
                    void handleFileSelected(file);
                  }
                }}
              >
                {isDragOver && (
                  <div className="chat-drag-overlay" role="status">
                    <UploadCloud size={36} style={{ color: 'var(--primary, #ec4899)' }} />
                    <b>Drop your document here</b>
                    <small>PDF, Word, Excel, PowerPoint, Text, or Image</small>
                  </div>
                )}

                <div
                  className="assistant-chat-transcript"
                  ref={transcriptRef}
                  onScroll={handleTranscriptScroll}
                  tabIndex={0}
                  aria-label="Conversation messages"
                >
                  {!messages.length && (
                    <div className="assistant-welcome">
                      <b>
                        {companion.emoji} Hi, I'm {companion.name}
                      </b>
                      <p>
                        Ask a question, type <code style={{ color: 'var(--accent, #ec4899)' }}>/</code> for commands, attach a document, or click a quick suggestion below:
                      </p>

                      {/* Suggestion Chips */}
                      <div className="assistant-suggestion-chips" role="group" aria-label="Quick suggestions">
                        <button
                          type="button"
                          className="assistant-suggestion-chip"
                          onClick={() => {
                            if (activeAttachment) {
                              void sendMessage('Summarize this document clearly with key takeaways.', 'summarize');
                            } else {
                              setInput('/summarize');
                              textareaRef.current?.focus();
                            }
                          }}
                        >
                          <Sparkles size={13} />
                          <span>Summarize document</span>
                        </button>

                        <button
                          type="button"
                          className="assistant-suggestion-chip"
                          onClick={() => {
                            setInput('/convert pdf');
                            textareaRef.current?.focus();
                          }}
                        >
                          <ArrowRightLeft size={13} />
                          <span>Convert file to PDF</span>
                        </button>

                        <button
                          type="button"
                          className="assistant-suggestion-chip"
                          onClick={() => {
                            setInput('/translate Tamil');
                            textareaRef.current?.focus();
                          }}
                        >
                          <Globe size={13} />
                          <span>Translate to Tamil</span>
                        </button>

                        <button
                          type="button"
                          className="assistant-suggestion-chip"
                          onClick={() => {
                            void sendMessage('Extract the key points, dates, and conclusions from this document.', 'key_points');
                          }}
                        >
                          <ListOrdered size={13} />
                          <span>Key points & dates</span>
                        </button>
                      </div>

                      <button
                        className="chat-speak-button"
                        style={{ marginTop: 14 }}
                        onClick={() =>
                          speakText(
                            'Hello! I am your Vertex assistant. Ask a question, type slash for commands, or attach a document.'
                          )
                        }
                      >
                        <Volume2 size={14} /> Listen
                      </button>
                      {!token && (
                        <small style={{ display: 'block', marginTop: 8 }}>
                          Sign in to chat and keep your private chat history.
                        </small>
                      )}
                    </div>
                  )}

                  {messages.map((message, index) => {
                    const isUser = message.role === 'user';
                    return (
                      <motion.div
                        className={`chat-message-row ${message.role}`}
                        key={`${message.role}-${index}-${message.id || index}`}
                        initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, x: isUser ? 20 : -20, y: 6 }}
                        animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, x: 0, y: 0 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                      >
                        <div className={`chat-message ${message.role}`}>
                          <MarkdownMessage
                            content={message.text}
                            onConvertAnother={handleFocusConversion}
                          />
                          {message.isStreaming && <span className="streaming-cursor" />}

                          {/* Render artifacts (download cards) */}
                          {message.artifacts &&
                            message.artifacts.map((card, cIdx) => (
                              <DownloadCard
                                key={`art-${cIdx}`}
                                card={card}
                                onConvertAnother={handleFocusConversion}
                              />
                            ))}
                          {!message.artifacts && message.downloadCard && (
                            <DownloadCard
                              card={message.downloadCard}
                              onConvertAnother={handleFocusConversion}
                            />
                          )}
                        </div>

                        {message.role === 'assistant' && !message.isStreaming && (
                          <div className="chat-message-actions">
                            <button
                              className="chat-action-btn"
                              onClick={() => handleCopyMessage(message.text, index)}
                              title="Copy response"
                            >
                              {copiedIndex === index ? <Check size={13} /> : <Copy size={13} />}
                              {copiedIndex === index ? 'Copied' : 'Copy'}
                            </button>
                            <button
                              className={`chat-action-btn ${speakingMsgIndex === index ? 'speaking-active' : ''}`}
                              onClick={() => handleSpeakMessage(message.text, index)}
                              title="Listen aloud"
                            >
                              {speakingMsgIndex === index ? (
                                <span className="speaking-wave" aria-hidden="true">
                                  <span /><span /><span />
                                </span>
                              ) : (
                                <Volume2 size={13} />
                              )}
                              {speakingMsgIndex === index ? 'Playing' : 'Listen'}
                            </button>
                            {index === messages.length - 1 && !busy && (
                              <button
                                className="chat-action-btn"
                                onClick={handleRegenerate}
                                title="Regenerate response"
                              >
                                <RotateCcw size={13} /> Regenerate
                              </button>
                            )}
                            {message.text.includes('Unable to complete request') && (
                              <button
                                className="chat-action-btn"
                                onClick={handleRetryFailed}
                                title="Retry request"
                              >
                                <RefreshCw size={13} /> Retry
                              </button>
                            )}
                          </div>
                        )}
                      </motion.div>
                    );
                  })}

                  {/* Animated Typing Dots Indicator */}
                  {busy && (
                    <div className="chat-typing-row">
                      <div className="chat-typing-bubble" aria-label="Finn is typing">
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                      </div>
                      <button
                        className="chat-stop-btn"
                        onClick={handleStopGeneration}
                        title="Stop generating"
                      >
                        <Square size={12} /> Stop generating
                      </button>
                    </div>
                  )}

                  {/* Clear Chat Undo Toast */}
                  {undoClearState && (
                    <div className="chat-undo-toast" role="status">
                      <span>Chat cleared</span>
                      <button onClick={handleUndoClear} className="chat-undo-btn">
                        <RotateCcw size={12} /> Undo
                      </button>
                    </div>
                  )}

                  {/* Floating Scroll to Latest button */}
                  {showScrollBottom && (
                    <button
                      type="button"
                      className="chat-scroll-bottom-btn"
                      onClick={scrollToBottom}
                      aria-label="Scroll to latest messages"
                      title="Scroll to latest messages"
                    >
                      <ArrowDownToLine size={13} />
                      <span>Latest</span>
                    </button>
                  )}

                  {errorMsg && (
                    <div className="chat-error-banner" role="alert">
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <AlertCircle size={16} /> {errorMsg}
                      </span>
                      <div className="chat-error-actions">
                        <button className="chat-retry-btn" onClick={handleRetryFailed}>
                          <RefreshCw size={12} style={{ display: 'inline', marginRight: 4 }} /> Retry
                        </button>
                        <button
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
                          onClick={() => setErrorMsg('')}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                  )}

                  {voiceFeedback && <small className="voice-feedback">{voiceFeedback}</small>}
                  <div ref={messagesEndRef} />
                </div>

                {/* Quick-action chips when file is attached */}
                {activeAttachment && (
                  <div className="assistant-quick-actions" aria-label="Document quick actions">
                    <button
                      className="assistant-chip-btn"
                      disabled={busy}
                      onClick={() =>
                        void sendMessage('Summarize this document clearly with key takeaways and action items.', 'summarize')
                      }
                    >
                      <BookOpen size={13} /> Summarize
                    </button>
                    <button
                      className="assistant-chip-btn"
                      disabled={busy}
                      onClick={() =>
                        void sendMessage('Explain the main points of this document simply and concisely.', 'explain_simply')
                      }
                    >
                      <FileQuestion size={13} /> Explain simply
                    </button>
                    <button
                      className="assistant-chip-btn"
                      disabled={busy}
                      onClick={() =>
                        void sendMessage('Extract the key points, dates, and conclusions from this document.', 'key_points')
                      }
                    >
                      <ListOrdered size={13} /> Key points
                    </button>
                    <button
                      className="assistant-chip-btn"
                      disabled={busy}
                      onClick={() =>
                        void sendMessage(`Translate the core content of this document into the selected language (${language}).`, 'translate')
                      }
                    >
                      <Globe size={13} /> Translate
                    </button>
                    <button
                      className="assistant-chip-btn"
                      disabled={conversionBusy || (conversionOptions.length > 0 && conversionOptions.find((o) => o.format === conversionFormat)?.available === false)}
                      onClick={() => void handleConvertAttachment()}
                    >
                      <ArrowRightLeft size={13} /> Convert ({conversionFormat.toUpperCase()})
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Attachment & Conversion Toolbar */}
            <div className="assistant-attachment-row">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={attachmentUploading}
                title="Upload PDF, DOCX, TXT, MD, PPTX, XLSX, PNG, JPG, JPEG or WEBP"
              >
                <UploadCloud size={14} />
                {attachmentUploading ? 'Uploading…' : 'Attach file or image'}
              </button>
              <button
                onClick={() => void openDocPicker()}
                disabled={attachmentUploading}
                title="Choose from my stored workspace documents"
              >
                <FolderOpen size={14} />
                Choose from my documents
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.png,.jpg,.jpeg,.webp"
                hidden
                onChange={handleFileUpload}
              />

              {activeAttachment && (
                <span className="assistant-attachment-chip" title={activeAttachment.filename}>
                  <FileText size={13} />
                  <span className="attachment-badge">
                    {activeAttachment.extension.replace('.', '')}
                  </span>
                  <span>{activeAttachment.filename}</span>
                  <small>({(activeAttachment.size / 1024).toFixed(0)} KB)</small>
                  <button
                    aria-label="Remove attachment"
                    onClick={() => setActiveAttachment(null)}
                    title="Remove from chat"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              <select
                aria-label="Convert attached file to"
                value={conversionFormat}
                onChange={(e) => setConversionFormat(e.target.value)}
                disabled={!activeAttachment || conversionBusy}
              >
                {conversionOptions.length > 0 ? (
                  conversionOptions.map((opt) => (
                    <option key={opt.format} value={opt.format} disabled={!opt.available}>
                      {opt.available ? opt.label : `${opt.label} (${opt.note || 'Unavailable'})`}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="pdf">Convert to PDF</option>
                    <option value="docx">Convert to DOCX</option>
                    <option value="txt">Convert to TXT</option>
                    <option value="pptx">Convert to PPTX</option>
                    <option value="xlsx">Convert to XLSX</option>
                  </>
                )}
              </select>

              <button
                disabled={!activeAttachment || conversionBusy || !token}
                onClick={() => void handleConvertAttachment()}
              >
                {conversionBusy ? 'Converting…' : 'Convert'}
              </button>
            </div>

            {/* Choose from my documents picker dialog */}
            {showDocPicker && (
              <div className="chat-doc-picker-modal" role="dialog" aria-label="Choose from my documents">
                <div className="chat-doc-picker-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FolderOpen size={15} style={{ color: 'var(--primary, #ec4899)' }} />
                    <b>Choose from my documents</b>
                  </div>
                  <button
                    onClick={() => setShowDocPicker(false)}
                    className="chat-close-btn"
                    aria-label="Close document picker"
                  >
                    <X size={14} />
                  </button>
                </div>
                <div className="chat-doc-picker-search">
                  <Search size={14} style={{ color: 'var(--text-muted, #666)' }} />
                  <input
                    type="text"
                    placeholder="Search documents by name…"
                    value={docSearch}
                    onChange={(e) => setDocSearch(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="chat-doc-picker-list">
                  {docPickerLoading ? (
                    <div className="chat-doc-picker-empty">Loading your documents…</div>
                  ) : workspaceDocs.filter((d) => !docSearch || d.original_name.toLowerCase().includes(docSearch.toLowerCase())).length === 0 ? (
                    <div className="chat-doc-picker-empty">
                      {docSearch ? 'No matching documents found.' : 'No documents in your workspace yet.'}
                    </div>
                  ) : (
                    workspaceDocs
                      .filter((d) => !docSearch || d.original_name.toLowerCase().includes(docSearch.toLowerCase()))
                      .map((doc) => (
                        <button
                          key={doc.id}
                          className="chat-doc-picker-item"
                          onClick={() => void handleAttachWorkspaceDoc(doc.id)}
                          title={`Select ${doc.original_name}`}
                        >
                          <FileText size={15} style={{ color: 'var(--primary, #ec4899)', flexShrink: 0 }} />
                          <div className="chat-doc-picker-item-info">
                            <span className="chat-doc-picker-item-name">{doc.original_name}</span>
                            <span className="chat-doc-picker-item-meta">
                              {(doc.size / 1024).toFixed(0)} KB {doc.created_at ? `· ${new Date(doc.created_at).toLocaleDateString()}` : ''}
                            </span>
                          </div>
                        </button>
                      ))
                  )}
                </div>
              </div>
            )}

            {/* Composer with Autocomplete Menu and Upward Language Popover */}
            <div className="assistant-compose">
              {/* Slash Command Autocomplete Menu */}
              {slashState.isOpen && !slashMenuForceClosed && (
                <SlashCommandMenu
                  isOpen={slashState.isOpen && !slashMenuForceClosed}
                  mode={slashState.mode as 'command' | 'argument'}
                  selectedIndex={slashSelectedIndex}
                  suggestions={slashState.suggestions}
                  onSelect={handleSelectSlashItem}
                  onClose={() => setSlashMenuForceClosed(true)}
                />
              )}

              {/* Custom Language Popover replacing native select */}
              <LanguagePopover
                currentLanguage={language}
                languages={languages}
                onSelectLanguage={onLanguageChange}
                isOpen={isLanguagePopoverOpen}
                onToggle={() => setIsLanguagePopoverOpen((prev) => !prev)}
                onClose={() => setIsLanguagePopoverOpen(false)}
              />

              {/* Small slash button for mouse & touch users */}
              <button
                type="button"
                className="slash-trigger-btn"
                aria-label="Open slash commands menu"
                title="Slash commands (/)"
                onClick={() => {
                  setInput('/');
                  setSlashMenuForceClosed(false);
                  textareaRef.current?.focus();
                }}
              >
                /
              </button>

              <textarea
                ref={textareaRef}
                value={input}
                role="combobox"
                aria-expanded={slashState.isOpen && !slashMenuForceClosed}
                aria-controls="assistant-slash-menu"
                aria-activedescendant={
                  slashState.isOpen && !slashMenuForceClosed && slashState.suggestions[slashSelectedIndex]
                    ? `slash-option-${slashSelectedIndex}`
                    : undefined
                }
                onChange={(e) => {
                  setInput(e.target.value);
                  setSlashMenuForceClosed(false);
                }}
                onPaste={(e) => {
                  const file = e.clipboardData.files?.[0];
                  if (file) {
                    e.preventDefault();
                    void handleFileSelected(file);
                  }
                }}
                onKeyDown={handleComposerKeyDown}
                placeholder={
                  activeAttachment
                    ? `Ask about ${activeAttachment.filename} or type / for commands…`
                    : 'Message Vertex Assistant or type / for commands…'
                }
                aria-label="Message Vertex Assistant"
              />

              <button
                className={`voice-button ${isListening ? 'voice-active' : ''}`}
                aria-label={isListening ? 'Stop voice input' : 'Speak your message'}
                aria-pressed={isListening}
                onClick={() =>
                  startVoiceInput((text) =>
                    setInput((current) => [current, text].filter(Boolean).join(' '))
                  )
                }
              >
                {isListening ? (
                  <div className="voice-waveform" aria-hidden="true">
                    <span className="wave-bar" />
                    <span className="wave-bar" />
                    <span className="wave-bar" />
                    <span className="wave-bar" />
                  </div>
                ) : (
                  <Mic size={16} />
                )}
              </button>

              <button
                className="send-button"
                aria-label="Send message"
                disabled={busy || (!input.trim() && !activeAttachment) || !token}
                onClick={() => void handleSendMessageOrSlash()}
              >
                <Send size={17} />
              </button>
            </div>

            {/* Resize Handle in bottom right corner */}
            {!isMobile && !isMaximized && (
              <div
                className="assistant-resize-handle assistant-resize-grip"
                title="Resize panel"
                aria-label="Resize panel"
                onPointerDown={handleResizePointerDown}
                onPointerMove={handleResizePointerMove}
                onPointerUp={handleResizePointerUp}
              >
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M9 1L1 9M9 5L5 9M9 9H9.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
            )}
          </motion.div>
        </motion.div>
      </motion.div>
    </div>,
    document.body
  );
}

import React, { useState, useEffect, useRef } from 'react';
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
  Languages,
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
} from 'lucide-react';
import { MarkdownMessage, DownloadCard, DownloadCardProps } from './MarkdownMessage';
import './chatbot.css';

const STORAGE_KEY = 'vertex_assistant_pos_size_v1';

export interface PanelPosSize {
  x: number;
  y: number;
  w: number;
  h: number;
}

const clampPos = (x: number, y: number, w: number, h: number): { x: number; y: number } => {
  const winW = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const winH = typeof window !== 'undefined' ? window.innerHeight : 800;
  // Keep at least 80px of header visible horizontally and at least 40px vertically
  const minX = -(w - 80);
  const maxX = winW - 80;
  const minY = 0;
  const maxY = winH - 50;
  let clampedX = Math.min(Math.max(x, minX), maxX);
  let clampedY = Math.min(Math.max(y, minY), maxY);

  // Subtle edge snap within 16px of screen edges
  if (Math.abs(clampedX - 16) < 16) clampedX = 16;
  if (Math.abs(winW - w - 16 - clampedX) < 16) clampedX = winW - w - 16;
  if (Math.abs(clampedY - 16) < 16) clampedY = 16;
  if (Math.abs(winH - h - 16 - clampedY) < 16) clampedY = winH - h - 16;

  return { x: clampedX, y: clampedY };
};

const getDefaultPosSize = (): PanelPosSize => {
  const winW = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const winH = typeof window !== 'undefined' ? window.innerHeight : 800;
  const w = Math.min(760, winW - 32);
  const h = Math.min(620, winH - 110);
  const x = Math.max(16, winW - w - 24);
  const y = Math.max(16, winH - h - 96);
  return { x, y, w, h };
};

const loadPosSize = (): PanelPosSize => {
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
    if (raw) {
      const parsed = JSON.parse(raw);
      if (
        typeof parsed.x === 'number' &&
        typeof parsed.y === 'number' &&
        typeof parsed.w === 'number' &&
        typeof parsed.h === 'number'
      ) {
        const winW = typeof window !== 'undefined' ? window.innerWidth : 1200;
        const winH = typeof window !== 'undefined' ? window.innerHeight : 800;
        const maxW = Math.max(360, winW - 16);
        const maxH = Math.max(420, winH - 16);
        const w = Math.min(Math.max(parsed.w, 360), maxW);
        const h = Math.min(Math.max(parsed.h, 420), maxH);
        const clamped = clampPos(parsed.x, parsed.y, w, h);
        return { x: clamped.x, y: clamped.y, w, h };
      }
    }
  } catch {}
  return getDefaultPosSize();
};

const savePosSize = (ps: PanelPosSize) => {
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ps));
    }
  } catch {}
};

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
  const [conversionFormat, setConversionFormat] = useState<'pdf' | 'docx' | 'txt'>('pdf');
  const [conversionBusy, setConversionBusy] = useState(false);

  // Rename conversation state
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [editTitleText, setEditTitleText] = useState('');

  // Copy feedback
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Draggable and Resizable state
  const [posSize, setPosSize] = useState<PanelPosSize>(loadPosSize);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [historyOpenNarrow, setHistoryOpenNarrow] = useState(false);

  // AbortController for streaming & element refs
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const convertSelectRef = useRef<HTMLSelectElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const dragRef = useRef<{
    isDragging: boolean;
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
  }>({ isDragging: false, startX: 0, startY: 0, initialX: 0, initialY: 0 });

  const resizeRef = useRef<{
    isResizing: boolean;
    startX: number;
    startY: number;
    initialW: number;
    initialH: number;
  }>({ isResizing: false, startX: 0, startY: 0, initialW: 0, initialH: 0 });

  const rafId = useRef<number | null>(null);

  // Auto-grow textarea up to 6 lines (~140px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 38), 140)}px`;
    }
  }, [input]);

  // Re-clamp position and size on window resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 640) return;
      setPosSize((prev) => {
        const maxW = Math.max(360, window.innerWidth - 16);
        const maxH = Math.max(420, window.innerHeight - 16);
        const w = Math.min(prev.w, maxW);
        const h = Math.min(prev.h, maxH);
        const clamped = clampPos(prev.x, prev.y, w, h);
        return { x: clamped.x, y: clamped.y, w, h };
      });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const resetPosition = () => {
    const def = getDefaultPosSize();
    setPosSize(def);
    savePosSize(def);
  };

  const handleHeaderPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (window.innerWidth <= 640) return;
    const target = e.target as HTMLElement;
    if (target.closest('button, input, select, a, textarea')) return;

    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    dragRef.current = {
      isDragging: true,
      startX: e.clientX,
      startY: e.clientY,
      initialX: posSize.x,
      initialY: posSize.y,
    };
    setIsDragging(true);
  };

  const handleHeaderPointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!dragRef.current.isDragging) return;
    const clientX = e.clientX;
    const clientY = e.clientY;

    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      const dx = clientX - dragRef.current.startX;
      const dy = clientY - dragRef.current.startY;
      const newX = dragRef.current.initialX + dx;
      const newY = dragRef.current.initialY + dy;
      const clamped = clampPos(newX, newY, posSize.w, posSize.h);
      setPosSize((prev) => ({ ...prev, x: clamped.x, y: clamped.y }));
    });
  };

  const handleHeaderPointerUp = (e: React.PointerEvent<HTMLElement>) => {
    if (!dragRef.current.isDragging) return;
    dragRef.current.isDragging = false;
    setIsDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}
    savePosSize(posSize);
  };

  const handleHeaderKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
      e.preventDefault();
      const step = e.shiftKey ? 40 : 10;
      let nextX = posSize.x;
      let nextY = posSize.y;
      if (e.key === 'ArrowLeft') nextX -= step;
      if (e.key === 'ArrowRight') nextX += step;
      if (e.key === 'ArrowUp') nextY -= step;
      if (e.key === 'ArrowDown') nextY += step;
      const clamped = clampPos(nextX, nextY, posSize.w, posSize.h);
      const updated = { ...posSize, x: clamped.x, y: clamped.y };
      setPosSize(updated);
      savePosSize(updated);
    }
  };

  const handleResizePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (window.innerWidth <= 640) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    e.stopPropagation();
    resizeRef.current = {
      isResizing: true,
      startX: e.clientX,
      startY: e.clientY,
      initialW: posSize.w,
      initialH: posSize.h,
    };
    setIsResizing(true);
  };

  const handleResizePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeRef.current.isResizing) return;
    const clientX = e.clientX;
    const clientY = e.clientY;

    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      const dw = clientX - resizeRef.current.startX;
      const dh = clientY - resizeRef.current.startY;
      const maxW = window.innerWidth - 16;
      const maxH = window.innerHeight - 16;
      const newW = Math.min(Math.max(resizeRef.current.initialW + dw, 360), maxW);
      const newH = Math.min(Math.max(resizeRef.current.initialH + dh, 420), maxH);
      const clamped = clampPos(posSize.x, posSize.y, newW, newH);
      setPosSize({ x: clamped.x, y: clamped.y, w: newW, h: newH });
    });
  };

  const handleResizePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeRef.current.isResizing) return;
    resizeRef.current.isResizing = false;
    setIsResizing(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}
    savePosSize(posSize);
  };

  useEffect(() => {
    if (token) {
      void loadConversations();
    }
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

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

  const tryRecoverConvertedDocument = async (
    targetExt: string,
    sourceFilename?: string
  ): Promise<DownloadCardProps | null> => {
    if (!token) return null;
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const c = new AbortController();
      const t = setTimeout(() => c.abort(), 4000);
      const res = await fetch(`${api}/api/documents`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: c.signal,
      });
      clearTimeout(t);
      if (!res.ok) return null;
      const docs = (await res.json()) as Array<{ id: number; name: string; size: number }>;
      if (!Array.isArray(docs) || docs.length === 0) return null;

      const normExt = targetExt.startsWith('.') ? targetExt.toLowerCase() : `.${targetExt.toLowerCase()}`;
      let baseStem = '';
      if (sourceFilename) {
        const lastDot = sourceFilename.lastIndexOf('.');
        baseStem = (lastDot > 0 ? sourceFilename.substring(0, lastDot) : sourceFilename).toLowerCase();
      }

      for (let i = docs.length - 1; i >= 0; i--) {
        const d = docs[i];
        const nameLower = d.name.toLowerCase();
        if (nameLower.endsWith(normExt)) {
          if (!baseStem || nameLower.startsWith(baseStem)) {
            return {
              id: d.id,
              document_id: d.id,
              filename: d.name,
              size: d.size,
              url: `/api/documents/${d.id}/download`,
              download_url: `/api/documents/${d.id}/download`,
            };
          }
        }
      }
      return null;
    } catch (err) {
      console.warn('Document recovery check failed:', err);
      return null;
    }
  };

  const getDiagnosticError = async (err: unknown, statusCode?: number): Promise<string> => {
    if (statusCode === 401) return 'Session expired. Please sign in again.';
    if (statusCode === 413) return 'File too large (maximum 50 MB allowed).';
    if (statusCode === 415) return 'Unsupported file format for this operation.';
    if (statusCode === 503) return 'AI Provider not configured (add LLM_API_KEY to backend/.env).';

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
    return 'An unexpected error occurred.';
  };

  const parseErrorMessage = (err: unknown, statusCode?: number): string => {
    if (statusCode === 401) return 'Session expired. Please sign in again.';
    if (statusCode === 413) return 'File too large (maximum 50 MB allowed).';
    if (statusCode === 415) return 'Unsupported file format for this operation.';
    if (statusCode === 503) return 'AI Provider not configured (add LLM_API_KEY to backend/.env).';

    if (err instanceof TypeError || (err instanceof Error && err.message.toLowerCase().includes('failed to fetch'))) {
      return "Can't reach the server - is the backend running on http://localhost:8000?";
    }
    if (err instanceof Error) {
      return err.message;
    }
    return 'An unexpected error occurred.';
  };

  const loadConversations = async () => {
    if (!token) return;
    setHistoryBusy(true);
    try {
      const res = await fetch(`${api}/api/chat/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Could not load chats (${res.status})`);
      const data = (await res.json()) as ChatConversation[];
      setConversations(data);
      if (data.length > 0 && !activeChatId) {
        void selectConversation(data[0].id);
      }
    } catch (e) {
      console.error('Error loading conversations:', e);
    } finally {
      setHistoryBusy(false);
    }
  };

  const selectConversation = async (id: number) => {
    if (!token) return;
    try {
      const res = await fetch(`${api}/api/chat/conversations/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Could not open conversation (${res.status})`);
      const data = (await res.json()) as {
        id: number;
        title: string;
        messages: ChatMessage[];
        attachments?: AttachmentInfo[];
      };
      setActiveChatId(data.id);
      setMessages(data.messages);
      if (data.attachments && data.attachments.length > 0) {
        setActiveAttachment(data.attachments[0]);
      } else {
        setActiveAttachment(null);
      }
      setErrorMsg('');
      setLastFailedPrompt(null);
    } catch (e) {
      setErrorMsg(parseErrorMessage(e));
    }
  };

  const createNewChat = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${api}/api/chat/conversations`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Could not start new chat');
      const created = (await res.json()) as ChatConversation;
      setConversations((prev) => [created, ...prev]);
      setActiveChatId(created.id);
      setMessages([]);
      setActiveAttachment(null);
      setErrorMsg('');
      setLastFailedPrompt(null);
    } catch (e) {
      setErrorMsg(parseErrorMessage(e));
    }
  };

  const deleteConversation = async (id: number) => {
    if (!token) return;
    try {
      const res = await fetch(`${api}/api/chat/conversations/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Could not delete chat');
      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);
      if (activeChatId === id) {
        if (remaining.length > 0) {
          void selectConversation(remaining[0].id);
        } else {
          setActiveChatId(null);
          setMessages([]);
          setActiveAttachment(null);
        }
      }
    } catch (e) {
      setErrorMsg(parseErrorMessage(e));
    }
  };

  const saveRename = async (id: number) => {
    if (!token || !editTitleText.trim()) {
      setEditingTitleId(null);
      return;
    }
    try {
      const res = await fetch(`${api}/api/chat/conversations/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: editTitleText.trim() }),
      });
      if (res.ok) {
        const updated = (await res.json()) as { id: number; title: string };
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: updated.title } : c))
        );
      }
    } catch (e) {
      console.error(e);
    } finally {
      setEditingTitleId(null);
    }
  };

  // Attachment upload
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !token) return;
    event.target.value = '';

    if (file.size > 50 * 1024 * 1024) {
      setErrorMsg('File exceeds 50 MB limit.');
      return;
    }

    setAttachmentUploading(true);
    setErrorMsg('');

    try {
      let convId = activeChatId;
      if (!convId) {
        const newChat = await fetch(`${api}/api/chat/conversations`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
        const created = (await newChat.json()) as ChatConversation;
        convId = created.id;
        setActiveChatId(created.id);
        setConversations((prev) => [created, ...prev]);
      }

      const form = new FormData();
      form.append('file', file);
      if (convId) form.append('conversation_id', String(convId));

      const res = await fetch(`${api}/api/chat/attachments`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed (${res.status})`);
      }

      const attInfo = (await res.json()) as AttachmentInfo;
      setActiveAttachment(attInfo);

      // Set smart default conversion target
      const ext = attInfo.extension.toLowerCase();
      if (ext === '.docx' || ext === '.txt' || ext === '.md' || attInfo.is_image) {
        setConversionFormat('pdf');
      } else if (ext === '.pdf') {
        setConversionFormat('docx');
      }

      if (attInfo.is_scanned) {
        setNotice('Notice: This PDF contains scanned images or no selectable text (OCR not available).');
      }
    } catch (e) {
      setErrorMsg(parseErrorMessage(e));
    } finally {
      setAttachmentUploading(false);
    }
  };

  // Direct server-side conversion (Convert button / dropdown)
  const handleConvertAttachment = async () => {
    if (!token || !activeAttachment || conversionBusy) return;
    setConversionBusy(true);
    setErrorMsg('');
    const sourceFilename = activeAttachment.filename;
    const targetFormat = conversionFormat;

    try {
      const form = new FormData();
      form.append('attachment_id', activeAttachment.id);
      form.append('target_format', targetFormat);
      if (activeChatId) form.append('conversation_id', String(activeChatId));

      const res = await fetch(`${api}/api/chat/convert`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Conversion failed (${res.status})`);
      }

      const data = (await res.json()) as { artifact: DownloadCardProps; message?: string };

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Your ${targetFormat.toUpperCase()} conversion of **${sourceFilename}** is ready!`,
          artifacts: [data.artifact],
          downloadCard: data.artifact,
        },
      ]);
    } catch (e) {
      // Step 3 Resilience: Try to recover converted document from /api/documents before reporting an error
      const recovered = await tryRecoverConvertedDocument(targetFormat, sourceFilename);
      if (recovered) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `Your ${targetFormat.toUpperCase()} conversion of **${sourceFilename}** is ready!`,
            artifacts: [recovered],
            downloadCard: recovered,
          },
        ]);
        setErrorMsg('');
      } else {
        const errText = await getDiagnosticError(e);
        setErrorMsg(errText);
        setLastFailedPrompt(`convert to ${targetFormat}`);
      }
    } finally {
      setConversionBusy(false);
    }
  };

  // Chat message sending with server-side tools & streaming
  const sendMessage = async (overridePrompt?: string, action?: string) => {
    const textToSend = (overridePrompt || input).trim();
    if (!textToSend && !activeAttachment && !action) return;
    if (!token) {
      setNotice('Sign in to chat with Vertex Assistant.');
      return;
    }

    let convId = activeChatId;
    if (!convId) {
      try {
        const newChat = await fetch(`${api}/api/chat/conversations`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
        const created = (await newChat.json()) as ChatConversation;
        convId = created.id;
        setActiveChatId(created.id);
        setConversations((prev) => [created, ...prev]);
      } catch (err) {
        setErrorMsg(parseErrorMessage(err));
        return;
      }
    }

    const prompt = textToSend || (activeAttachment ? `Please examine ${activeAttachment.filename}.` : '');
    setInput('');
    setErrorMsg('');
    setLastFailedPrompt(null);
    setBusy(true);

    const userMsgText = activeAttachment ? `${prompt}\n\n[Attached: ${activeAttachment.filename}]` : prompt;
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: userMsgText },
      { role: 'assistant', text: '', isStreaming: true },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Timeout safety (35s)
    const timeoutId = window.setTimeout(() => {
      controller.abort();
    }, 35000);

    try {
      const response = await fetch(`${api}/api/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          text: prompt,
          attachment_ids: activeAttachment ? [activeAttachment.id] : [],
          language,
          conversation_id: convId,
          action,
          target_format: conversionFormat,
          stream: true,
        }),
        signal: controller.signal,
      });

      window.clearTimeout(timeoutId);

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server error (${response.status})`);
      }

      if (!response.body) throw new Error('No streaming response body available');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let streamedReply = '';
      let collectedArtifacts: DownloadCardProps[] = [];

      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                throw new Error(data.error);
              }
              if (data.token) {
                streamedReply += data.token;
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      text: streamedReply,
                      isStreaming: true,
                    };
                  }
                  return updated;
                });
              }
              if (data.artifacts && Array.isArray(data.artifacts)) {
                collectedArtifacts = data.artifacts;
              }
              if (data.done) {
                if (data.title && convId) {
                  setConversations((prev) =>
                    prev.map((c) => (c.id === convId ? { ...c, title: data.title } : c))
                  );
                }
              }
            } catch (err) {
              if (err instanceof Error && err.name !== 'SyntaxError') {
                throw err;
              }
            }
          }
        }
      }

      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            text: streamedReply || 'Done.',
            isStreaming: false,
            artifacts: collectedArtifacts,
            downloadCard: collectedArtifacts[0],
          };
        }
        return updated;
      });
    } catch (e: any) {
      window.clearTimeout(timeoutId);
      if (e.name === 'AbortError') {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              text: updated[lastIdx].text + '\n\n*(Generation stopped)*',
              isStreaming: false,
            };
          }
          return updated;
        });
      } else {
        // Step 3 Resilience: If prompt was a conversion intent or action was 'convert', check if the document was generated
        const isConvertIntent = action === 'convert' || /convert|pdf|docx|export/i.test(prompt);
        let recoveredCard: DownloadCardProps | null = null;
        if (isConvertIntent && activeAttachment) {
          const targetExt = conversionFormat || 'pdf';
          recoveredCard = await tryRecoverConvertedDocument(targetExt, activeAttachment.filename);
        }

        if (recoveredCard) {
          setMessages((prev) => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
              updated[lastIdx] = {
                ...updated[lastIdx],
                text: `Your conversion of **${activeAttachment?.filename || 'the document'}** is ready!`,
                isStreaming: false,
                artifacts: [recoveredCard!],
                downloadCard: recoveredCard!,
              };
            }
            return updated;
          });
          setErrorMsg('');
        } else {
          const errorText = await getDiagnosticError(e);
          setErrorMsg(errorText);
          setLastFailedPrompt(prompt);
          setMessages((prev) => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
              updated[lastIdx] = {
                ...updated[lastIdx],
                text: `⚠️ **Unable to complete request:** ${errorText}`,
                isStreaming: false,
              };
            }
            return updated;
          });
        }
      }
    } finally {
      setBusy(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleRegenerate = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg) {
      const cleanPrompt = lastUserMsg.text.replace(/\[Attached: .*?\]/, '').trim();
      void sendMessage(cleanPrompt);
    }
  };

  const handleRetryFailed = () => {
    if (lastFailedPrompt) {
      const p = lastFailedPrompt;
      setLastFailedPrompt(null);
      if (/^convert to /i.test(p) && activeAttachment) {
        void handleConvertAttachment();
      } else {
        void sendMessage(p);
      }
    } else {
      handleRegenerate();
    }
  };

  const handleCopyMessage = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleFocusConversion = () => {
    convertSelectRef.current?.focus();
  };

  const activeTitle = conversations.find((c) => c.id === activeChatId)?.title || 'Private chat';

  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;
  const isNarrow = posSize.w < 560;

  const panelStyle: React.CSSProperties = isMobile
    ? {}
    : {
        left: `${posSize.x}px`,
        top: `${posSize.y}px`,
        width: `${posSize.w}px`,
        height: `${posSize.h}px`,
        right: 'auto',
        bottom: 'auto',
      };

  return (
    <section
      className={`assistant-panel ${isDragging ? 'assistant-panel-dragging' : ''} ${
        isResizing ? 'assistant-panel-resizing' : ''
      }`}
      style={panelStyle}
      aria-label="Vertex Assistant"
    >
      <header
        className="assistant-header"
        tabIndex={0}
        role="region"
        aria-label="Vertex Assistant header, double click to reset position, use arrow keys to move"
        onPointerDown={handleHeaderPointerDown}
        onPointerMove={handleHeaderPointerMove}
        onPointerUp={handleHeaderPointerUp}
        onDoubleClick={(e) => {
          if (!(e.target as HTMLElement).closest('button, input, select, a')) {
            resetPosition();
          }
        }}
        onKeyDown={handleHeaderKeyDown}
      >
        <span className="assistant-star">
          <Sparkles size={17} />
        </span>
        <span>
          <b>Vertex Assistant</b>
          <small>
            {activeTitle} · {companion.name}
          </small>
        </span>
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
          title="Reset position and size (double-click header also resets)"
          aria-label="Reset position"
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
        <button className="icon-button" aria-label="Close assistant" onClick={onClose}>
          <X size={18} />
        </button>
      </header>

      <div className={`assistant-workspace ${isNarrow ? 'is-narrow' : ''} ${historyOpenNarrow ? 'show-history-narrow' : ''}`}>
        {/* Chat History Sidebar */}
        <aside className="assistant-history">
          <b>Chat history</b>
          {historyBusy && <small>Loading chats…</small>}
          {!historyBusy && !conversations.length && <small>Your chats will appear here.</small>}
          {conversations.map((c) => (
            <div
              className={`assistant-history-item ${activeChatId === c.id ? 'active' : ''}`}
              key={c.id}
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
            </div>
          ))}
          {!token && <small>Sign in to keep private chat history.</small>}
        </aside>

        {/* Main Chat Area */}
        <div className="assistant-chat-main">
          <div className="assistant-messages">
            {!messages.length && (
              <div className="assistant-welcome">
                <b>
                  {companion.emoji} {companion.name}
                </b>
                <p>Hello! Ask a question, attach a document or image, or convert a file with real server-side engines.</p>
                <button
                  className="chat-speak-button"
                  onClick={() =>
                    speakText(
                      'Hello! I am your Vertex assistant. Ask a question, attach a document or image, or convert a supported file.'
                    )
                  }
                >
                  <Volume2 size={14} /> Listen
                </button>
                {!token && (
                  <small style={{ display: 'block', marginTop: 8 }}>
                    Sign in to chat. Add an LLM_API_KEY to backend/.env to enable AI replies.
                  </small>
                )}
              </div>
            )}

            {messages.map((message, index) => (
              <div
                className={`chat-message-row ${message.role}`}
                key={`${message.role}-${index}`}
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
                      className="chat-action-btn"
                      onClick={() => speakText(message.text)}
                      title="Listen aloud"
                    >
                      <Volume2 size={13} /> Listen
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
              </div>
            ))}

            {busy && (
              <div style={{ textAlign: 'center', margin: '6px 0' }}>
                <button className="chat-stop-btn" onClick={handleStopGeneration}>
                  <Square size={13} /> Stop generating
                </button>
              </div>
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
                disabled={conversionBusy}
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
          title="Upload PDF, DOCX, TXT, MD or image"
        >
          <UploadCloud size={14} />
          {attachmentUploading ? 'Uploading…' : 'Attach file or image'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,image/png,image/jpeg,image/webp"
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
          ref={convertSelectRef}
          aria-label="Convert attached file to"
          value={conversionFormat}
          onChange={(e) => setConversionFormat(e.target.value as any)}
        >
          <option value="pdf">Convert to PDF</option>
          <option value="docx">Convert to DOCX</option>
          <option value="txt">Convert to TXT</option>
          <option value="pptx" disabled>
            Convert to PPTX (Coming soon)
          </option>
          <option value="xlsx" disabled>
            Convert to XLSX (Coming soon)
          </option>
        </select>

        <button
          disabled={!activeAttachment || conversionBusy || !token}
          onClick={() => void handleConvertAttachment()}
        >
          {conversionBusy ? 'Converting…' : 'Convert'}
        </button>
      </div>

      {/* Composer */}
      <div className="assistant-compose">
        <label className="language-select">
          <Languages size={15} />
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            aria-label="Assistant language"
          >
            {languages.map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void sendMessage();
            }
          }}
          placeholder={
            activeAttachment
              ? `Ask about ${activeAttachment.filename} or type "convert to ${conversionFormat}"…`
              : 'Message Vertex Assistant…'
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
          <Mic size={16} />
        </button>
        <button
          className="send-button"
          aria-label="Send message"
          disabled={busy || (!input.trim() && !activeAttachment) || !token}
          onClick={() => void sendMessage()}
        >
          <Send size={17} />
        </button>
      </div>

      {/* Resize Handle in bottom right corner */}
      {!isMobile && (
        <div
          className="assistant-resize-handle"
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
    </section>
  );
}

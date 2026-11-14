import React, { useState } from 'react';
import { MessageCircle, Volume2, Mic, Send, Copy, Check } from 'lucide-react';
import { MarkdownMessage } from '../assistant/MarkdownMessage';
import '../assistant/chatbot.css';

export interface AiDocMessage {
  role: 'user' | 'assistant';
  text: string;
}

interface AiDocChatProps {
  selectedLabel: string;
  companion: { emoji: string; name: string };
  messages: AiDocMessage[];
  busy: boolean;
  input: string;
  onInputChange: (val: string) => void;
  onSend: (overrideText?: string) => void;
  isListening: boolean;
  startVoiceInput: (onResult: (text: string) => void) => void;
  speakText: (text: string) => void;
}

export function AiDocChat({
  selectedLabel,
  companion,
  messages,
  busy,
  input,
  onInputChange,
  onSend,
  isListening,
  startVoiceInput,
  speakText,
}: AiDocChatProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const handleCopy = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div>
      <div className="ai-feature-intro">
        <span className="ai-feature-icon">
          <MessageCircle size={20} />
        </span>
        <div>
          <h2>Ask questions about your file</h2>
          <p>
            Your answers are grounded in <b>{selectedLabel}</b> and reply in the selected assistant language.
          </p>
        </div>
      </div>

      <div className="ai-chat-transcript" role="log" aria-live="polite">
        {!messages.length && (
          <div className="ai-chat-welcome">
            <span>{companion.emoji}</span>
            <div>
              <b>Hi, I’m {companion.name}!</b>
              <p>Ask me to explain a section, find a date, or clarify an idea from this document.</p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
                <button
                  className="assistant-chip-btn"
                  onClick={() => onSend('Summarize the key takeaways and decisions in this file.')}
                >
                  Key takeaways
                </button>
                <button
                  className="assistant-chip-btn"
                  onClick={() => onSend('List all dates, deadlines, and action items mentioned.')}
                >
                  Action items
                </button>
                <button
                  className="assistant-chip-btn"
                  onClick={() => onSend('Explain the main topic in simple terms.')}
                >
                  Explain simply
                </button>
              </div>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div className={`ai-chat-line ${message.role}`} key={`${message.role}-${index}`}>
            <span className="ai-chat-avatar">
              {message.role === 'assistant' ? companion.emoji : 'You'}
            </span>
            <div className="ai-chat-bubble">
              <MarkdownMessage content={message.text} />
              {message.role === 'assistant' && (
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  <button
                    aria-label="Read assistant reply aloud"
                    className="chat-action-btn"
                    onClick={() => speakText(message.text)}
                  >
                    <Volume2 size={13} /> Listen
                  </button>
                  <button
                    aria-label="Copy assistant reply"
                    className="chat-action-btn"
                    onClick={() => handleCopy(message.text, index)}
                  >
                    {copiedIdx === index ? <Check size={13} /> : <Copy size={13} />}
                    {copiedIdx === index ? 'Copied' : 'Copy'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="ai-chat-line assistant">
            <span className="ai-chat-avatar">{companion.emoji}</span>
            <div className="ai-chat-bubble typing-indicator">Thinking it through…</div>
          </div>
        )}
      </div>

      <div className="ai-chat-compose">
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder={`Ask ${selectedLabel} a question…`}
          aria-label="Message about the selected document"
        />
        <button
          className={`voice-button ${isListening ? 'voice-active' : ''}`}
          aria-label={isListening ? 'Stop voice input' : 'Speak your question'}
          aria-pressed={isListening}
          onClick={() =>
            startVoiceInput((text) =>
              onInputChange([input, text].filter(Boolean).join(' '))
            )
          }
        >
          <Mic size={16} />
        </button>
        <button
          className="primary-button"
          disabled={busy || !input.trim()}
          onClick={() => onSend()}
        >
          <Send size={15} /> Ask
        </button>
      </div>
    </div>
  );
}

import React, { useEffect, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Terminal, Sparkles, Languages, ArrowRightLeft, Trash2, ArrowRight } from 'lucide-react';
import { SlashCommand } from './slashCommands';

interface SlashCommandMenuProps {
  isOpen: boolean;
  mode: 'command' | 'argument';
  selectedIndex: number;
  suggestions: Array<{
    value: string;
    label: string;
    hint?: string;
    command?: SlashCommand;
  }>;
  onSelect: (item: { value: string; label: string; hint?: string; command?: SlashCommand }) => void;
  onClose: () => void;
}

export const SlashCommandMenu: React.FC<SlashCommandMenuProps> = ({
  isOpen,
  mode,
  selectedIndex,
  suggestions,
  onSelect,
}) => {
  const listRef = useRef<HTMLDivElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current) {
      const activeEl = listRef.current.querySelector<HTMLElement>('.slash-menu-item.active');
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  if (!isOpen || suggestions.length === 0) {
    return null;
  }

  const getIcon = (cmdId?: string) => {
    switch (cmdId) {
      case 'summarize':
        return <Sparkles size={14} className="slash-icon summarize" />;
      case 'translate':
        return <Languages size={14} className="slash-icon translate" />;
      case 'convert':
        return <ArrowRightLeft size={14} className="slash-icon convert" />;
      case 'clear':
        return <Trash2 size={14} className="slash-icon clear" />;
      default:
        return <Terminal size={14} className="slash-icon default" />;
    }
  };

  return (
    <motion.div
      id="assistant-slash-menu"
      role="listbox"
      aria-label="Slash commands"
      ref={listRef}
      className="assistant-slash-menu"
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 6 }}
      animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 6 }}
      transition={{ duration: 0.14, ease: 'easeOut' }}
    >
      <div className="slash-menu-header">
        <span>{mode === 'command' ? 'Slash Commands' : 'Argument Options'}</span>
        <small>↑↓ navigate · Enter / Tab select · Esc close</small>
      </div>

      <div className="slash-menu-list">
        {suggestions.map((item, idx) => {
          const isSelected = idx === selectedIndex;
          const cmd = item.command;

          return (
            <div
              key={`${item.value}-${idx}`}
              id={`slash-option-${idx}`}
              role="option"
              aria-selected={isSelected}
              className={`slash-menu-item ${isSelected ? 'active' : ''}`}
              onMouseDown={(e) => {
                // Prevent input blur before click registers
                e.preventDefault();
                onSelect(item);
              }}
            >
              <div className="slash-item-left">
                {getIcon(cmd?.id)}
                <span className="slash-item-name">{item.label}</span>
                {cmd?.argHint && mode === 'command' && (
                  <span className="slash-item-arg">{cmd.argHint}</span>
                )}
              </div>

              {item.hint && (
                <div className="slash-item-right">
                  <span className="slash-item-hint">{item.hint}</span>
                  <ArrowRight size={12} className="slash-item-arrow" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
};

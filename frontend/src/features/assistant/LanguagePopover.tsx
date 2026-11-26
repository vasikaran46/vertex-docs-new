import React, { useState, useRef, useEffect } from 'react';
import { Languages, Check, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

interface LanguagePopoverProps {
  currentLanguage: string;
  languages: [string, string][];
  onSelectLanguage: (code: string) => void;
  isOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
}

export const LanguagePopover: React.FC<LanguagePopoverProps> = ({
  currentLanguage,
  languages,
  onSelectLanguage,
  isOpen,
  onToggle,
  onClose,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  const currentLabel =
    languages.find(([code]) => code === currentLanguage)?.[1] || currentLanguage.toUpperCase();

  return (
    <div className="language-popover-container" ref={containerRef}>
      <button
        type="button"
        className={`language-popover-trigger ${isOpen ? 'active' : ''}`}
        onClick={onToggle}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title="Select assistant reply language"
      >
        <Languages size={15} />
        <span className="language-current-label">{currentLabel}</span>
        <ChevronUp size={12} className={`language-chevron ${isOpen ? 'open' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="language-popover-menu"
            role="listbox"
            aria-label="Reply languages"
            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.96 }}
            animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
            exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
          >
            <div className="language-popover-header">
              <span>Reply in Language</span>
            </div>
            <div className="language-popover-list">
              {languages.map(([code, label]) => {
                const isSelected = code === currentLanguage;
                return (
                  <button
                    key={code}
                    role="option"
                    aria-selected={isSelected}
                    type="button"
                    className={`language-popover-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      onSelectLanguage(code);
                      onClose();
                    }}
                  >
                    <span className="language-item-name">{label}</span>
                    <span className="language-item-code">{code}</span>
                    {isSelected && <Check size={14} className="language-check-icon" />}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

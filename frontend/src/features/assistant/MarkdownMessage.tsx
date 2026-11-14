import React, { useState } from 'react';
import { Copy, Check, FileText, Download, RefreshCw } from 'lucide-react';

export interface DownloadCardProps {
  id?: number;
  document_id?: number;
  filename: string;
  size: number;
  url?: string;
  download_url?: string;
  content_type?: string;
}

export function DownloadCard({
  card,
  onConvertAnother,
}: {
  card: DownloadCardProps;
  onConvertAnother?: () => void;
}) {
  const formatSize = (bytes: number) => {
    if (!bytes) return 'Unknown size';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const targetUrl = card.url || card.download_url || '#';

  return (
    <div className="chat-download-card">
      <div className="chat-download-card-info">
        <FileText size={30} style={{ color: 'var(--primary, #059669)', flexShrink: 0 }} />
        <div>
          <b>{card.filename}</b>
          <small>{formatSize(card.size)} · Ready to download</small>
        </div>
      </div>
      <div className="chat-download-card-actions">
        <a href={targetUrl} download={card.filename} className="chat-download-btn">
          <Download size={15} /> Download
        </a>
        {onConvertAnother && (
          <button className="chat-convert-another-btn" onClick={onConvertAnother} title="Choose another format to convert">
            <RefreshCw size={13} /> Convert another format
          </button>
        )}
      </div>
    </div>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="chat-code-block">
      <button className="chat-code-copy-btn" onClick={handleCopy} title="Copy code">
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function MarkdownMessage({
  content,
  onConvertAnother,
}: {
  content: string;
  onConvertAnother?: () => void;
}) {
  // Check for download card tag: [DOWNLOAD_CARD:{...}]
  const downloadCardMatch = content.match(/\[DOWNLOAD_CARD:(\{.*?\})\]/);
  let cardData: DownloadCardProps | null = null;
  let cleanContent = content;

  if (downloadCardMatch) {
    try {
      cardData = JSON.parse(downloadCardMatch[1]);
      cleanContent = content.replace(downloadCardMatch[0], '').trim();
    } catch {
      // Ignore parse failure
    }
  }

  // Parse markdown into blocks
  const lines = cleanContent.split('\n');
  const blocks: React.ReactNode[] = [];
  let currentList: string[] = [];
  let isNumberedList = false;
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLang = '';
  let inTable = false;
  let tableRows: string[][] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      if (isNumberedList) {
        blocks.push(
          <ol key={`ol-${blocks.length}`}>
            {currentList.map((item, idx) => (
              <li key={idx}>{renderInline(item)}</li>
            ))}
          </ol>
        );
      } else {
        blocks.push(
          <ul key={`ul-${blocks.length}`}>
            {currentList.map((item, idx) => (
              <li key={idx}>{renderInline(item)}</li>
            ))}
          </ul>
        );
      }
      currentList = [];
    }
  };

  const flushTable = () => {
    if (tableRows.length > 0) {
      const [headerRow, ...bodyRows] = tableRows;
      blocks.push(
        <div key={`table-${blocks.length}`} style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                {headerRow.map((cell, idx) => (
                  <th key={idx}>{renderInline(cell.trim())}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{renderInline(cell.trim())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.trim().startsWith('```')) {
      if (!inCodeBlock) {
        flushList();
        flushTable();
        inCodeBlock = true;
        codeLang = line.trim().slice(3).trim();
        codeBuffer = [];
      } else {
        inCodeBlock = false;
        blocks.push(
          <CodeBlock
            key={`code-${blocks.length}`}
            code={codeBuffer.join('\n')}
            language={codeLang}
          />
        );
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Table row
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      flushList();
      if (/^\|[\s\-:|]+\|$/.test(line.trim())) {
        continue;
      }
      const cells = line
        .trim()
        .slice(1, -1)
        .split('|');
      tableRows.push(cells);
      inTable = true;
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Headings
    if (line.startsWith('### ')) {
      flushList();
      blocks.push(<h3 key={`h3-${blocks.length}`}>{renderInline(line.slice(4))}</h3>);
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      blocks.push(<h2 key={`h2-${blocks.length}`}>{renderInline(line.slice(3))}</h2>);
      continue;
    }
    if (line.startsWith('# ')) {
      flushList();
      blocks.push(<h1 key={`h1-${blocks.length}`}>{renderInline(line.slice(2))}</h1>);
      continue;
    }

    // Bullet list
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      if (isNumberedList) flushList();
      isNumberedList = false;
      currentList.push(line.trim().slice(2));
      continue;
    }

    // Numbered list
    const numMatch = line.trim().match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      if (!isNumberedList) flushList();
      isNumberedList = true;
      currentList.push(numMatch[2]);
      continue;
    }

    flushList();

    // Blockquote
    if (line.startsWith('> ')) {
      blocks.push(<blockquote key={`quote-${blocks.length}`}>{renderInline(line.slice(2))}</blockquote>);
      continue;
    }

    // Paragraph
    if (line.trim().length > 0) {
      blocks.push(<p key={`p-${blocks.length}`}>{renderInline(line)}</p>);
    }
  }

  flushList();
  flushTable();

  return (
    <div className="chat-markdown">
      {blocks}
      {cardData && <DownloadCard card={cardData} onConvertAnother={onConvertAnother} />}
    </div>
  );
}

function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let keyIdx = 0;

  const inlineRegex = /(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/;

  while (remaining) {
    const match = remaining.match(inlineRegex);
    if (!match || match.index === undefined) {
      parts.push(remaining);
      break;
    }

    if (match.index > 0) {
      parts.push(remaining.slice(0, match.index));
    }

    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={keyIdx++}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={keyIdx++}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(<code key={keyIdx++}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('[') && token.includes('](') && token.endsWith(')')) {
      const linkMatch = token.match(/\[(.*?)\]\((.*?)\)/);
      if (linkMatch) {
        parts.push(
          <a key={keyIdx++} href={linkMatch[2]} target="_blank" rel="noreferrer">
            {linkMatch[1]}
          </a>
        );
      } else {
        parts.push(token);
      }
    }

    remaining = remaining.slice(match.index + token.length);
  }

  return <>{parts}</>;
}

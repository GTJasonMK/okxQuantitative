const HTML_ESCAPE_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

const safeUrlPattern = /^(https?:\/\/|mailto:)/i;

const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (char) => HTML_ESCAPE_MAP[char] || char);

const normalizeMarkdownText = (value) => (
  String(value || '')
    .replace(/\r\n/g, '\n')
    .replace(/\t/g, '  ')
);

const resolveSafeUrl = (value) => {
  const normalized = String(value || '').trim();
  if (!normalized || !safeUrlPattern.test(normalized)) {
    return '';
  }
  return normalized;
};

const createPlaceholderStore = () => {
  const values = [];
  return {
    stash(html) {
      const token = `\u0000assistant-md-${values.length}\u0000`;
      values.push(html);
      return token;
    },
    restore(text) {
      return values.reduce(
        (current, html, index) => current.replaceAll(`\u0000assistant-md-${index}\u0000`, html),
        text,
      );
    },
  };
};

const countIndent = (line) => {
  const match = String(line || '').match(/^ */);
  return match ? match[0].length : 0;
};

const stripIndent = (line, size) => {
  if (!line) {
    return '';
  }
  let index = 0;
  let remaining = size;
  while (index < line.length && remaining > 0 && line[index] === ' ') {
    index += 1;
    remaining -= 1;
  }
  return line.slice(index);
};

const splitTableRow = (line) => {
  const normalized = String(line || '').trim();
  if (!normalized.includes('|')) {
    return [];
  }
  const trimmed = normalized.replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
};

const isHorizontalRule = (line) => /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line);
const isFenceStart = (line) => /^```/.test(String(line || '').trim());
const isHeading = (line) => /^ {0,3}#{1,6}\s+/.test(line);
const isBlockquote = (line) => /^ {0,3}>\s?/.test(line);

const getListMatch = (line) => {
  const match = String(line || '').match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
  if (!match) {
    return null;
  }
  return {
    indent: match[1].length,
    ordered: /\d+\./.test(match[2]),
    marker: match[2],
    content: match[3] || '',
  };
};

const isTableSeparatorRow = (line) => {
  const cells = splitTableRow(line);
  if (cells.length === 0) {
    return false;
  }
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
};

const renderInlineMarkdown = (value, options = {}) => {
  const { disableLinks = false } = options;
  const store = createPlaceholderStore();
  let text = escapeHtml(value);

  text = text.replace(/`([^`\n]+)`/g, (_, code) => store.stash(`<code>${code}</code>`));

  if (!disableLinks) {
    text = text.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
      const safeUrl = resolveSafeUrl(url);
      if (!safeUrl) {
        return match;
      }
      const renderedLabel = renderInlineMarkdown(label, { disableLinks: true });
      return store.stash(
        `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer noopener">${renderedLabel}</a>`,
      );
    });

    text = text.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, (match, prefix, url) => {
      const safeUrl = resolveSafeUrl(url);
      if (!safeUrl) {
        return match;
      }
      return `${prefix}${store.stash(
        `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer noopener">${escapeHtml(safeUrl)}</a>`,
      )}`;
    });
  }

  text = text.replace(/\*\*([^*\n][\s\S]*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_\n][\s\S]*?)__/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*\n][\s\S]*?)\*/g, '<em>$1</em>');
  text = text.replace(/_([^_\n][\s\S]*?)_/g, '<em>$1</em>');
  text = text.replace(/~~([^~\n][\s\S]*?)~~/g, '<del>$1</del>');

  return store.restore(text);
};

const renderParagraph = (lines) => {
  const content = lines
    .map((line) => renderInlineMarkdown(line.trimEnd()))
    .join('<br />');
  return `<p>${content}</p>`;
};

const renderHeading = (line) => {
  const match = String(line || '').match(/^ {0,3}(#{1,6})\s+(.*)$/);
  if (!match) {
    return '';
  }
  const level = Math.min(match[1].length, 6);
  const content = match[2].replace(/\s+#+\s*$/, '');
  return `<h${level}>${renderInlineMarkdown(content)}</h${level}>`;
};

const renderCodeFence = (lines, startIndex) => {
  const openingLine = String(lines[startIndex] || '').trim();
  const language = openingLine.slice(3).trim();
  const codeLines = [];
  let cursor = startIndex + 1;

  while (cursor < lines.length && !/^```/.test(String(lines[cursor] || '').trim())) {
    codeLines.push(lines[cursor]);
    cursor += 1;
  }

  const escapedCode = escapeHtml(codeLines.join('\n'));
  const languageAttr = language ? ` data-language="${escapeHtml(language)}"` : '';

  return {
    html: `<pre class="assistant-md-pre"${languageAttr}><code>${escapedCode}</code></pre>`,
    nextIndex: cursor < lines.length ? cursor + 1 : cursor,
  };
};

const renderTable = (lines, startIndex) => {
  const headerCells = splitTableRow(lines[startIndex]);
  const separatorCells = splitTableRow(lines[startIndex + 1]);
  if (headerCells.length === 0 || headerCells.length !== separatorCells.length) {
    return null;
  }

  const alignments = separatorCells.map((cell) => {
    if (/^:-{3,}:$/.test(cell)) {
      return 'center';
    }
    if (/^-{3,}:$/.test(cell)) {
      return 'right';
    }
    if (/^:-{3,}$/.test(cell)) {
      return 'left';
    }
    return 'left';
  });

  let cursor = startIndex + 2;
  const bodyRows = [];

  while (cursor < lines.length) {
    const currentLine = String(lines[cursor] || '');
    if (!currentLine.trim()) {
      break;
    }
    const cells = splitTableRow(currentLine);
    if (cells.length !== headerCells.length) {
      break;
    }
    bodyRows.push(cells);
    cursor += 1;
  }

  const renderCell = (tag, content, align) => (
    `<${tag} style="text-align:${align};">${renderInlineMarkdown(content)}</${tag}>`
  );

  const headHtml = `<thead><tr>${
    headerCells.map((cell, index) => renderCell('th', cell, alignments[index])).join('')
  }</tr></thead>`;

  const bodyHtml = bodyRows.length > 0
    ? `<tbody>${
        bodyRows.map((row) => `<tr>${
          row.map((cell, index) => renderCell('td', cell, alignments[index])).join('')
        }</tr>`).join('')
      }</tbody>`
    : '';

  return {
    html: `<table>${headHtml}${bodyHtml}</table>`,
    nextIndex: cursor,
  };
};

const renderBlockquote = (lines, startIndex, renderMarkdown) => {
  const quoteLines = [];
  let cursor = startIndex;

  while (cursor < lines.length && isBlockquote(lines[cursor])) {
    quoteLines.push(String(lines[cursor] || '').replace(/^ {0,3}>\s?/, ''));
    cursor += 1;
  }

  return {
    html: `<blockquote>${renderMarkdown(quoteLines.join('\n'))}</blockquote>`,
    nextIndex: cursor,
  };
};

const renderList = (lines, startIndex, renderMarkdown) => {
  const firstItem = getListMatch(lines[startIndex]);
  if (!firstItem) {
    return null;
  }

  const tag = firstItem.ordered ? 'ol' : 'ul';
  const baseIndent = firstItem.indent;
  const items = [];
  let cursor = startIndex;

  while (cursor < lines.length) {
    const currentMatch = getListMatch(lines[cursor]);
    if (!currentMatch || currentMatch.indent !== baseIndent || currentMatch.ordered !== firstItem.ordered) {
      break;
    }

    const itemLines = [currentMatch.content];
    cursor += 1;

    while (cursor < lines.length) {
      const currentLine = String(lines[cursor] || '');
      if (!currentLine.trim()) {
        itemLines.push('');
        cursor += 1;
        continue;
      }

      const nextMatch = getListMatch(currentLine);
      const currentIndent = countIndent(currentLine);

      if (nextMatch && nextMatch.indent === baseIndent && nextMatch.ordered === firstItem.ordered) {
        break;
      }

      if (currentIndent <= baseIndent && !(nextMatch && nextMatch.indent > baseIndent)) {
        break;
      }

      itemLines.push(stripIndent(currentLine, Math.min(currentIndent, baseIndent + 2)));
      cursor += 1;
    }

    const itemHtml = renderMarkdown(itemLines.join('\n')).trim() || '<p></p>';
    items.push(`<li>${itemHtml}</li>`);
  }

  return {
    html: `<${tag}>${items.join('')}</${tag}>`,
    nextIndex: cursor,
  };
};

const createMarkdownRenderer = () => {
  const startsBlock = (lines, index) => {
    const line = String(lines[index] || '');
    if (!line.trim()) {
      return false;
    }
    if (
      isFenceStart(line)
      || isHorizontalRule(line)
      || isHeading(line)
      || isBlockquote(line)
      || getListMatch(line)
    ) {
      return true;
    }
    return index + 1 < lines.length && splitTableRow(line).length > 0 && isTableSeparatorRow(lines[index + 1]);
  };

  const renderMarkdown = (value) => {
    const normalized = normalizeMarkdownText(value).trim();
    if (!normalized) {
      return '<p></p>';
    }

    const lines = normalized.split('\n');
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
      const line = String(lines[index] || '');

      if (!line.trim()) {
        index += 1;
        continue;
      }

      if (isFenceStart(line)) {
        const result = renderCodeFence(lines, index);
        blocks.push(result.html);
        index = result.nextIndex;
        continue;
      }

      if (isHorizontalRule(line)) {
        blocks.push('<hr />');
        index += 1;
        continue;
      }

      if (isHeading(line)) {
        blocks.push(renderHeading(line));
        index += 1;
        continue;
      }

      if (isBlockquote(line)) {
        const result = renderBlockquote(lines, index, renderMarkdown);
        blocks.push(result.html);
        index = result.nextIndex;
        continue;
      }

      const tableCandidate = index + 1 < lines.length
        && splitTableRow(line).length > 0
        && isTableSeparatorRow(lines[index + 1])
        ? renderTable(lines, index)
        : null;
      if (tableCandidate) {
        blocks.push(tableCandidate.html);
        index = tableCandidate.nextIndex;
        continue;
      }

      const listCandidate = getListMatch(line) ? renderList(lines, index, renderMarkdown) : null;
      if (listCandidate) {
        blocks.push(listCandidate.html);
        index = listCandidate.nextIndex;
        continue;
      }

      const paragraphLines = [];
      while (index < lines.length) {
        const currentLine = String(lines[index] || '');
        if (!currentLine.trim()) {
          break;
        }
        if (startsBlock(lines, index)) {
          if (paragraphLines.length === 0) {
            paragraphLines.push(currentLine);
            index += 1;
          }
          break;
        }
        paragraphLines.push(currentLine);
        index += 1;
      }

      if (paragraphLines.length > 0) {
        const headingOnly = paragraphLines.length === 1 && isHeading(paragraphLines[0]);
        if (headingOnly) {
          blocks.push(renderHeading(paragraphLines[0]));
        } else {
          blocks.push(renderParagraph(paragraphLines));
        }
      } else {
        index += 1;
      }
    }

    return blocks.join('') || '<p></p>';
  };

  return renderMarkdown;
};

const renderMarkdown = createMarkdownRenderer();

const renderPlainAssistantText = (value) => {
  const normalized = normalizeMarkdownText(value);
  if (!normalized.trim()) {
    return '<p></p>';
  }
  return `<p>${escapeHtml(normalized).replace(/\n/g, '<br />')}</p>`;
};

export const renderAssistantMessageHtml = (content, role = 'assistant') => (
  role === 'assistant'
    ? renderMarkdown(content)
    : renderPlainAssistantText(content)
);

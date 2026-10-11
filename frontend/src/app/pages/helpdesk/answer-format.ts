/**
 * Formatting for AI Helpdesk answers.
 *
 * The backend returns plain text that often contains light Markdown
 * (bold runs, bullet/numbered lines, tables, `<br>` line breaks). This module
 * turns that text into plain data structures that the template renders as
 * text nodes, so an answer can never become markup and no HTML is ever
 * injected. Anything that is not recognised is kept exactly as sent.
 */

/** One piece of inline text; `bold` marks **strong** runs, `italic` *emphasis*. */
export interface AnswerSegment {
  text: string;
  bold: boolean;
  italic?: boolean;
}

/** One line of inline text. */
export type AnswerLine = AnswerSegment[];

/** A table cell: the lines the backend separated with `<br>`. */
export type AnswerCell = AnswerLine[];

/** A table row: its cells in order. */
export type AnswerRow = AnswerCell[];

/** A renderable answer block. */
export type AnswerBlock =
  | { kind: 'paragraph'; segments: AnswerSegment[] }
  | { kind: 'list'; ordered: boolean; items: { segments: AnswerSegment[] }[] }
  | { kind: 'table'; header: AnswerRow; rows: AnswerRow[] };

/**
 * Inline HTML the model sometimes emits. Only line/emphasis tags are removed
 * — deliberately narrow, so text like "income < 1 lakh" is never damaged.
 */
const LINE_BREAK_TAGS = /<br\s*\/?>/gi;
const EMPHASIS_TAGS = /<\/?(?:b|strong|i|em|u|p|ul|ol|li|span|div)\s*\/?>/gi;

const TABLE_ROW = /^\|.*\|$/;
/** A Markdown horizontal rule — decorative, so it is not rendered as text. */
const RULE_LINE = /^(?:-{3,}|\*{3,}|_{3,})$/;
const SEPARATOR_CELL = /^:?-{2,}:?$/;
const BULLET_LINE = /^[-*•]\s+(.*)$/;
const NUMBERED_LINE = /^\d+[.)]\s+(.*)$/;

/** Split inline text on `**bold**` and `*italic*` runs. */
export function parseInline(text: string): AnswerSegment[] {
  const trimmed = text.replace(EMPHASIS_TAGS, '');
  const pattern = /\*\*(.+?)\*\*/g;
  const segments: AnswerSegment[] = [];
  let lastIndex = 0;
  let match = pattern.exec(trimmed);

  const pushPlain = (plain: string): void => {
    segments.push(...parseItalic(plain));
  };

  while (match !== null) {
    if (match.index > lastIndex) {
      pushPlain(trimmed.slice(lastIndex, match.index));
    }
    segments.push({ text: match[1], bold: true });
    lastIndex = match.index + match[0].length;
    match = pattern.exec(trimmed);
  }

  if (lastIndex < trimmed.length) {
    pushPlain(trimmed.slice(lastIndex));
  }

  return segments.filter((segment) => segment.text.length > 0);
}

/** Split a plain run on `*italic*` markers, keeping anything else as text. */
function parseItalic(text: string): AnswerSegment[] {
  const pattern = /\*([^*]+)\*/g;
  const segments: AnswerSegment[] = [];
  let lastIndex = 0;
  let match = pattern.exec(text);

  while (match !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: text.slice(lastIndex, match.index), bold: false });
    }
    segments.push({ text: match[1], bold: false, italic: true });
    lastIndex = match.index + match[0].length;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), bold: false });
  }

  return segments;
}

/** A table cell as the lines the backend separated with `<br>`. */
function parseCell(text: string): AnswerCell {
  return text
    .split(LINE_BREAK_TAGS)
    .map((part) => parseInline(part.trim()))
    .filter((line) => line.length > 0);
}

/**
 * Drop columns that are empty in every row. Models sometimes add a spacer
 * column (usually just a tab or a couple of spaces), which would otherwise
 * show up as a blank column in the table.
 */
function dropEmptyColumns(rows: AnswerRow[]): AnswerRow[] {
  const width = rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (width <= 1) {
    return rows;
  }

  const keep: number[] = [];
  for (let index = 0; index < width; index++) {
    if (rows.some((row) => (row[index]?.length ?? 0) > 0)) {
      keep.push(index);
    }
  }

  if (keep.length === width) {
    return rows;
  }
  return rows.map((row) => keep.map((index) => row[index] ?? []));
}

function splitTableRow(line: string): string[] {
  return line
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

/** Turn the plain-text answer into paragraphs, lists and tables. */
export function parseAnswer(answer: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = [];
  let paragraph = '';
  let items: { segments: AnswerSegment[] }[] = [];
  let ordered = false;
  let tableRows: AnswerRow[] = [];

  const flushParagraph = (): void => {
    const text = paragraph.trim();
    if (text.length > 0) {
      blocks.push({ kind: 'paragraph', segments: parseInline(text) });
    }
    paragraph = '';
  };

  const flushList = (): void => {
    if (items.length > 0) {
      blocks.push({ kind: 'list', ordered, items });
    }
    items = [];
  };

  const flushTable = (): void => {
    if (tableRows.length > 0) {
      const rows = dropEmptyColumns(tableRows);
      if (rows.some((row) => row.length > 0)) {
        blocks.push({ kind: 'table', header: rows[0], rows: rows.slice(1) });
      }
    }
    tableRows = [];
  };

  const handleTextLine = (line: string): void => {
    const bullet = line.match(BULLET_LINE);
    if (bullet) {
      flushParagraph();
      if (items.length > 0 && ordered) {
        flushList();
      }
      ordered = false;
      items.push({ segments: parseInline(bullet[1]) });
      return;
    }

    const numbered = line.match(NUMBERED_LINE);
    if (numbered) {
      flushParagraph();
      if (items.length > 0 && !ordered) {
        flushList();
      }
      ordered = true;
      items.push({ segments: parseInline(numbered[1]) });
      return;
    }

    flushList();
    const heading = line.replace(/^#{1,6}\s*/, '');
    paragraph = paragraph.length > 0 ? `${paragraph} ${heading}` : heading;
  };

  for (const rawLine of answer.split(/\r?\n/)) {
    const line = rawLine.trim();

    if (line.length === 0) {
      flushParagraph();
      flushList();
      flushTable();
      continue;
    }

    if (RULE_LINE.test(line)) {
      flushParagraph();
      flushList();
      flushTable();
      continue;
    }

    if (TABLE_ROW.test(line)) {
      flushParagraph();
      flushList();
      const cells = splitTableRow(line);
      if (!cells.every((cell) => SEPARATOR_CELL.test(cell))) {
        tableRows.push(cells.map(parseCell));
      }
      continue;
    }

    flushTable();

    // `<br>` inside a line starts a new logical line.
    for (const part of line.split(LINE_BREAK_TAGS)) {
      const text = part.trim();
      if (text.length > 0) {
        handleTextLine(text);
      }
    }
  }

  flushParagraph();
  flushList();
  flushTable();
  return blocks;
}

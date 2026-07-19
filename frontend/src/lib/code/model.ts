// The code-viewer model (D-129).
//
// Everything the viewer needs to describe WHAT is being shown and WHAT is
// marked, with no opinion about how it is laid out. The rendering layer
// (CodeBlock) is the only place that knows about rows, columns, wrapping or
// CSS. That split is the whole point of the refactor: a new exercise type adds
// a decoration kind or a document role here, and does not touch rendering.

/** A caret position. `line` is 1-based (it is what the user sees in the
 * gutter); `col` is 0-based, counted in characters from the start of the line,
 * so col 0 is before the first character. */
export interface Position {
  line: number;
  col: number;
}

/** A selection or a decorated span. End is exclusive at the character level. */
export interface CodeRange {
  start: Position;
  end: Position;
}

/** What a document is FOR, which is how a caller picks the one it wants out of
 * the payload's list. `primary` is the code under study and always exists;
 * predict_the_fix adds `failing_test` and one `choice` per candidate fix. */
export type DocumentRole = 'primary' | 'failing_test' | 'choice';

export interface CodeDocument {
  /** Stable within a payload. For a choice this is the choice id, so a caller
   * can line documents up with the answer options it is rendering. */
  id: string;
  role: DocumentRole;
  code: string;
  language: string;
  /** Nullable, not just optional: the wire sends an explicit null for a
   * document that has no label (Pydantic serializes the default that way). */
  label?: string | null;
}

/** Decision 4: a payload is a LIST of documents even when it has one element.
 * The single-document case is not a special case anywhere above this line. */
export interface CodePayload {
  documents: CodeDocument[];
}

/** Decision 3: decorations are data, applied at render time. Today's reveal
 * marks are three of these kinds; a future diff or coverage overlay adds a kind
 * rather than a new prop on CodeBlock. */
export type DecorationKind = 'selected' | 'correct' | 'incorrect' | 'note';

export interface Decoration {
  range: CodeRange;
  kind: DecorationKind;
}

// --- ranges -----------------------------------------------------------------

/** The range covering one whole line. Decision 1: a whole-line selection is
 * not a different kind of thing from a sub-expression selection, it is just a
 * range whose ends happen to sit on the same line. `END_OF_LINE` stands in for
 * "however long this line is" so callers do not need the source text to build
 * one. */
export const END_OF_LINE = Number.MAX_SAFE_INTEGER;

export function lineRange(line: number): CodeRange {
  return { start: { line, col: 0 }, end: { line, col: END_OF_LINE } };
}

export function rangeSpansLines(range: CodeRange): number {
  return range.end.line - range.start.line + 1;
}

/** Does this range touch the given line at all? This is what maps a range onto
 * rows at render time, and it is the only place multi-line ranges need
 * thinking about: a range from line 3 to line 7 covers 3, 4, 5, 6 and 7. */
export function rangeCoversLine(range: CodeRange, line: number): boolean {
  return line >= range.start.line && line <= range.end.line;
}

/** True when the range covers the whole of that line rather than a slice of
 * it. A middle line of a multi-line range is always fully covered. */
export function rangeCoversWholeLine(range: CodeRange, line: number): boolean {
  if (!rangeCoversLine(range, line)) return false;
  const startsBefore = range.start.line < line || range.start.col === 0;
  const endsAfter = range.end.line > line || range.end.col >= END_OF_LINE;
  return startsBefore && endsAfter;
}

export function rangesEqual(a: CodeRange | null | undefined, b: CodeRange | null | undefined): boolean {
  if (!a || !b) return a === b;
  return (
    a.start.line === b.start.line &&
    a.start.col === b.start.col &&
    a.end.line === b.end.line &&
    a.end.col === b.end.col
  );
}

// --- decorations ------------------------------------------------------------

/** Every decoration kind that applies to a line, in the order given. Callers
 * render them; this function does not rank them. */
export function decorationKindsForLine(decorations: Decoration[], line: number): DecorationKind[] {
  return decorations.filter((d) => rangeCoversLine(d.range, line)).map((d) => d.kind);
}

/**
 * Which single kind wins, when several decorations cover one line and the
 * target can only show one.
 *
 * The gutter and the code row have DIFFERENT ladders, and that asymmetry is
 * not an oversight -- it is what the viewer does today and must keep doing. A
 * selected line shows in the gutter (the number goes blue) and leaves the code
 * row untinted; only correct/incorrect marks tint the row. Collapsing these
 * into one ladder would tint the row on selection, which is a visible change.
 *
 * `note` is in neither ladder: it renders as a dot beside the number, not as a
 * background, so it never competes for the tint.
 */
const GUTTER_PRECEDENCE: DecorationKind[] = ['selected', 'correct', 'incorrect'];
const ROW_PRECEDENCE: DecorationKind[] = ['incorrect', 'correct'];

function winner(decorations: Decoration[], line: number, ladder: DecorationKind[]): DecorationKind | null {
  const kinds = new Set(decorationKindsForLine(decorations, line));
  return ladder.find((k) => kinds.has(k)) ?? null;
}

/** The kind that tints the code row. Marks only, never the selection. */
export function rowDecorationForLine(decorations: Decoration[], line: number): DecorationKind | null {
  return winner(decorations, line, ROW_PRECEDENCE);
}

/** The kind that styles the gutter entry. Selection outranks marks. */
export function gutterDecorationForLine(decorations: Decoration[], line: number): DecorationKind | null {
  return winner(decorations, line, GUTTER_PRECEDENCE);
}

export function lineHasNote(decorations: Decoration[], line: number): boolean {
  return decorationKindsForLine(decorations, line).includes('note');
}

// --- building decorations from reveal data ---------------------------------

/** Convenience for the common case: whole-line marks from a list of line
 * numbers. This is what turns the reveal payloads (which speak in line
 * numbers) into decorations without every caller writing range literals. */
export function lineDecorations(lines: Iterable<number>, kind: DecorationKind): Decoration[] {
  return Array.from(lines, (line) => ({ range: lineRange(line), kind }));
}

// --- documents --------------------------------------------------------------

export function documentsFromCode(code: string, language = 'python'): CodeDocument[] {
  return [{ id: 'primary', role: 'primary', code, language }];
}

export function primaryDocument(payload: CodePayload): CodeDocument | undefined {
  return payload.documents.find((d) => d.role === 'primary') ?? payload.documents[0];
}

/**
 * The primary document as a one-element list, ready to hand to CodeBlock.
 *
 * This exists because "render the payload" and "render the code under study"
 * are different things and conflating them is a real bug: a predict_the_fix
 * payload's document list also holds the failing test and every candidate fix,
 * and a column that renders the whole list would show all of them stacked. The
 * code column wants the primary document; the answer component places the rest.
 */
export function primaryDocuments(
  payload: { documents?: CodeDocument[] | null; code?: string | null; language?: string | null } | null | undefined,
): CodeDocument[] {
  const doc = primaryDocument(normalizeCodePayload(payload));
  return doc ? [doc] : [];
}

export function documentsByRole(payload: CodePayload, role: DocumentRole): CodeDocument[] {
  return payload.documents.filter((d) => d.role === role);
}

export function documentById(payload: CodePayload, id: string): CodeDocument | undefined {
  return payload.documents.find((d) => d.id === id);
}

/**
 * The deserialization half of the D-129 boundary.
 *
 * Invariant 3 says exercises are immutable per (id, version) and the 109
 * stored payloads are not migrated, so the client must render both shapes: a
 * payload that arrives with `documents` (the backend normalizes today) and a
 * bare `code` string (anything that predates it, including a cached response).
 * Normalizing here means exactly one place in the client knows two shapes
 * exist, and every component above it sees a document list.
 */
export function normalizeCodePayload(
  payload: { documents?: CodeDocument[] | null; code?: string | null; language?: string | null } | null | undefined,
  fallbackLanguage = 'python',
): CodePayload {
  if (payload?.documents && payload.documents.length > 0) {
    return { documents: payload.documents };
  }
  if (typeof payload?.code === 'string') {
    return { documents: documentsFromCode(payload.code, payload.language ?? fallbackLanguage) };
  }
  return { documents: [] };
}

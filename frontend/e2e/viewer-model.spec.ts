import { expect, test } from '@playwright/test';

import {
  END_OF_LINE,
  decorationKindsForLine,
  documentById,
  documentsByRole,
  gutterDecorationForLine,
  lineDecorations,
  lineRange,
  normalizeCodePayload,
  primaryDocument,
  rangeCoversLine,
  rangeCoversWholeLine,
  rangeSpansLines,
  rowDecorationForLine,
  type Decoration,
} from '../src/lib/code/model';

// D-129 model tests. These run in Node, not a browser -- the model is
// deliberately free of DOM, which is the property that lets interaction logic
// be tested without rendering anything.
//
// Every test here fails against the pre-refactor viewer, and mostly for the
// strongest possible reason: the concepts did not exist. There was no range
// (selection was `selectedLine: number`), no decoration (marks were a
// `Record<number, 'correct' | 'incorrect'>` baked into spans at construction),
// and no document list (a payload was `code: string`).

test.describe('decision 1: selection is a range, not a row', () => {
  test('a range spans multiple lines and covers every line between its ends', () => {
    // The case the old model could not express at all: one selection, five
    // lines. `selectedLine: number` had no way to say this.
    const range = { start: { line: 3, col: 4 }, end: { line: 7, col: 12 } };

    expect(rangeSpansLines(range)).toBe(5);

    expect(rangeCoversLine(range, 2)).toBe(false);
    for (const line of [3, 4, 5, 6, 7]) {
      expect(rangeCoversLine(range, line)).toBe(true);
    }
    expect(rangeCoversLine(range, 8)).toBe(false);

    // The interior lines are covered end to end; the first and last are only
    // partly covered, because the range starts and stops mid-line. This is the
    // distinction that makes sub-expression selection possible later.
    expect(rangeCoversWholeLine(range, 3)).toBe(false);
    expect(rangeCoversWholeLine(range, 5)).toBe(true);
    expect(rangeCoversWholeLine(range, 7)).toBe(false);
  });

  test('a whole-line selection is just a range spanning that line', () => {
    const range = lineRange(4);

    expect(range.start).toEqual({ line: 4, col: 0 });
    expect(range.end).toEqual({ line: 4, col: END_OF_LINE });
    expect(rangeSpansLines(range)).toBe(1);
    expect(rangeCoversWholeLine(range, 4)).toBe(true);
    expect(rangeCoversLine(range, 3)).toBe(false);
    expect(rangeCoversLine(range, 5)).toBe(false);
  });
});

test.describe('decision 3: decorations are data', () => {
  test('decorations are applied from a list, and multi-line ones decorate every line they cover', () => {
    const decorations: Decoration[] = [
      { range: { start: { line: 2, col: 0 }, end: { line: 4, col: END_OF_LINE } }, kind: 'correct' },
      { range: lineRange(6), kind: 'incorrect' },
      { range: lineRange(2), kind: 'note' },
    ];

    // A single decoration marks a three-line span. The old markLines record
    // could only ever hold one line per entry.
    expect(rowDecorationForLine(decorations, 2)).toBe('correct');
    expect(rowDecorationForLine(decorations, 3)).toBe('correct');
    expect(rowDecorationForLine(decorations, 4)).toBe('correct');
    expect(rowDecorationForLine(decorations, 5)).toBe(null);
    expect(rowDecorationForLine(decorations, 6)).toBe('incorrect');

    // Two kinds can sit on one line; the note does not displace the mark.
    expect(decorationKindsForLine(decorations, 2).sort()).toEqual(['correct', 'note']);
  });

  test('the gutter and the row resolve overlapping decorations differently', () => {
    // This asymmetry is behaviour the refactor had to PRESERVE: a selected line
    // colours the gutter and leaves the code row untinted. Collapsing the two
    // ladders into one would tint the row on selection, which is visible.
    const decorations: Decoration[] = [
      { range: lineRange(5), kind: 'correct' },
      { range: lineRange(5), kind: 'selected' },
    ];

    expect(gutterDecorationForLine(decorations, 5)).toBe('selected');
    expect(rowDecorationForLine(decorations, 5)).toBe('correct');
  });

  test('reveal line numbers convert into whole-line decorations', () => {
    const decorations = lineDecorations([2, 9], 'correct');

    expect(decorations).toHaveLength(2);
    expect(decorations[0]).toEqual({ range: lineRange(2), kind: 'correct' });
    expect(rowDecorationForLine(decorations, 9)).toBe('correct');
    expect(rowDecorationForLine(decorations, 3)).toBe(null);
  });
});

test.describe('decision 4: a payload is a list of documents', () => {
  test('a multi-document payload keeps every document, addressable by role and id', () => {
    const payload = {
      code: 'def f():\n    pass',
      documents: [
        { id: 'primary', role: 'primary' as const, code: 'def f():\n    pass', language: 'python' },
        { id: 'failing_test', role: 'failing_test' as const, code: 'assert f() == 1', language: 'python' },
        { id: 'fix-a', role: 'choice' as const, code: 'return 1', language: 'python' },
        { id: 'fix-b', role: 'choice' as const, code: 'return 2', language: 'python' },
      ],
    };

    const normalized = normalizeCodePayload(payload);

    expect(normalized.documents).toHaveLength(4);
    expect(primaryDocument(normalized)?.id).toBe('primary');
    expect(documentsByRole(normalized, 'choice').map((d) => d.id)).toEqual(['fix-a', 'fix-b']);
    expect(documentById(normalized, 'failing_test')?.code).toBe('assert f() == 1');
  });

  test('a legacy payload with only `code` normalizes to a one-element list', () => {
    // Invariant 3: the 109 stored payloads are not migrated, so this shape has
    // to keep rendering. The single-document case is not special-cased anywhere
    // above this function -- it is a list of length one.
    const normalized = normalizeCodePayload({ code: 'x = 1' });

    expect(normalized.documents).toHaveLength(1);
    expect(normalized.documents[0]).toEqual({
      id: 'primary',
      role: 'primary',
      code: 'x = 1',
      language: 'python',
    });
    expect(primaryDocument(normalized)?.code).toBe('x = 1');
  });

  test('documents win over code when both are present, and neither means an empty list', () => {
    const both = normalizeCodePayload({
      code: 'stale',
      documents: [{ id: 'primary', role: 'primary', code: 'fresh', language: 'python' }],
    });
    expect(primaryDocument(both)?.code).toBe('fresh');

    expect(normalizeCodePayload(null).documents).toEqual([]);
    expect(normalizeCodePayload({}).documents).toEqual([]);
  });
});

import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { Highlight } from 'prism-react-renderer';

import { GutterLineButton, GutterSlots, type GutterCellState, type GutterSlot } from './Gutter';
import { readingSyntaxTheme } from './syntaxTheme';
import {
  documentsFromCode,
  gutterDecorationForLine,
  lineHasNote,
  lineRange,
  rangeCoversLine,
  rowDecorationForLine,
  type CodeDocument,
  type CodeRange,
  type Decoration,
} from '../../lib/code/model';
import { enclosingSignature } from '../../lib/code/signature';
import { useIsNarrow, useWrapPreference, type WrapMode } from '../../lib/code/viewerPreferences';

// The rendering half of D-129, plus the narrow arrangement from D-130.
// Everything above this component speaks in ranges, decorations and documents;
// this is the only place that knows they become rows, columns and CSS.
//
// D-130's rule for this file: every narrow-only behaviour is gated on `narrow`
// so the wide branch emits the markup it emitted before, byte for byte. That
// is a testable claim, and viewer-dom.spec.ts tests it.

export interface CodeBlockProps {
  /** Decision 4: always a list, even with one element. */
  documents: CodeDocument[];
  /** Decision 1: the selection is a RANGE. A tapped line number is the range
   * spanning that line; nothing here assumes ranges are line-sized. */
  selection?: CodeRange | null;
  onSelectRange?: (range: CodeRange) => void;
  /** Decision 3: marks arrive as data and are applied here. */
  decorations?: Decoration[];
  /** Overrides the resolved user preference. Tests and callers that need a
   * specific mode set it; normal rendering leaves it undefined. */
  wrapMode?: WrapMode;
  /**
   * Narrow-only (D-130): let the block own the vertical space it is given and
   * scroll internally, with the enclosing signature pinned at the top. Off by
   * default so nothing about the wide layout changes.
   */
  fillsViewport?: boolean;
  /**
   * D-132: give every code row the touch-target height (44px) instead of the
   * reading line-height. Opt-in per render, because it costs roughly half the
   * visible lines: only spot_the_bug WHILE ANSWERING needs tappable lines --
   * every other type answers in the sheet, and every reveal is for reading.
   */
  tapSizedRows?: boolean;
  /** D-132: trim the pane to whole rows so the bottom row is never a fragment. */
  snapRows?: boolean;
}

const trimmedCode = (code: string) => code.replace(/\n+$/, '');

/** How far past its own indentation a wrapped continuation sits. Two
 * characters is enough to read as "continued" without pushing long wrapped
 * lines off the right edge on a narrow screen. */
const HANG_CH = 2;

/** Leading-whitespace width of each line, in characters. Tabs count as 4,
 * matching the width the browser renders them at in this monospace face. */
function lineIndents(code: string): number[] {
  return trimmedCode(code)
    .split('\n')
    .map((line) => {
      const match = /^[ \t]*/.exec(line);
      return match ? match[0].replace(/\t/g, '    ').length : 0;
    });
}

/** Decoration kind -> the gutter state that renders it. The gutter has its own
 * vocabulary (GutterCellState) that predates decorations and is shared with
 * non-code gutters, so the two are mapped rather than merged. */
const GUTTER_STATE: Record<string, GutterCellState> = {
  selected: 'selected',
  correct: 'correct',
  incorrect: 'incorrect',
};

const ROW_TINT: Record<string, string> = {
  correct: 'bg-correct-tint',
  incorrect: 'bg-incorrect-tint',
};

/** Tracks which logical line is at the top of a scrolling code area, by
 * measuring the rows rather than dividing by a line height -- wrapped rows
 * have different heights, so arithmetic on a single line-height is wrong the
 * moment wrapping is on. */
function useFirstVisibleLine(enabled: boolean): {
  scrollerRef: React.RefObject<HTMLDivElement>;
  firstVisibleLine: number;
} {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [firstVisibleLine, setFirstVisibleLine] = useState(1);

  const measure = useCallback(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const rows = scroller.querySelectorAll<HTMLElement>('[data-line]');
    const top = scroller.scrollTop;
    for (const row of rows) {
      if (row.offsetTop + row.offsetHeight > top + 1) {
        setFirstVisibleLine(Number(row.dataset.line));
        return;
      }
    }
  }, []);

  useLayoutEffect(() => {
    if (!enabled) return;
    const scroller = scrollerRef.current;
    if (!scroller) return;
    measure();
    scroller.addEventListener('scroll', measure, { passive: true });
    return () => scroller.removeEventListener('scroll', measure);
  }, [enabled, measure]);

  return { scrollerRef, firstVisibleLine };
}

/**
 * Trim a scrolling code pane to a whole number of rows (D-132).
 *
 * The pane is `flex-1`, so its height is whatever is left over -- essentially
 * never a multiple of the row height, which is why the bottom row always
 * rendered as a fragment (measured leftovers: 7.8px at 375x667, 8.6px at
 * 400x844, 25.5px at 667x375). A sliced row is not just untidy: half a line of
 * code reads as a different line of code.
 *
 * Snapping on the LINE-HEIGHT works even when lines wrap, because a wrapped
 * line is always a whole number of line-heights tall. So this needs no
 * knowledge of wrapping.
 */
function useSnappedHeight(
  ref: React.RefObject<HTMLElement>,
  enabled: boolean,
): number | null {
  const [height, setHeight] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!enabled || !el) {
      setHeight(null);
      return;
    }
    const measure = () => {
      // Snap on REAL GEOMETRY, not arithmetic.
      //
      // Computing floor(available / lineHeight) kept missing contributors:
      // first the pinned signature header (which sits inside the scroller and
      // takes flow space), then the code container's own vertical padding.
      // Each fix removed one source of a sliced bottom row and left another.
      //
      // Measuring where the rows actually END removes the whole class of
      // error: it accounts for the header, the padding, and wrapped rows of
      // differing heights, without knowing any of them exist.
      const parent = el.parentElement;
      if (!parent) return;
      const available = parent.clientHeight;
      // THE LATCH (D-133): if the parent is momentarily zero-height -- which
      // happens for real during a phase or exercise swap -- an earlier
      // version fell through to `snapped = available` and wrote a 0px
      // max-height. That collapsed the scroller, which collapsed the pane,
      // which made the next measurement 0 as well: absorbing, and the code
      // pane never came back. Measured: one zero-height moment took the pane
      // from 672px to 0px permanently.
      //
      // A degenerate measurement must CLEAR the constraint, never write one.
      if (available <= 0) {
        setHeight(null);
        return;
      }
      const top = el.getBoundingClientRect().top;
      const rows = Array.from(el.querySelectorAll<HTMLElement>('[data-line]'));
      if (rows.length === 0) return;
      let snapped = 0;
      for (const row of rows) {
        const bottom = row.getBoundingClientRect().bottom - top + el.scrollTop;
        if (bottom > available + 0.5) break;
        snapped = bottom;
      }
      // Every row is taller than the pane (one very long wrapped line): keep
      // the full height rather than collapsing the pane to nothing.
      if (snapped <= 0) {
        // No row fits (a single very long wrapped line taller than the
        // pane). Leave the pane UNCONSTRAINED and let it scroll rather than
        // pinning it to a computed value -- a tall row shown partially and
        // scrollably beats a pane pinned to a number we do not trust.
        setHeight(null);
        return;
      }
      setHeight((current) => (current !== null && Math.abs(current - snapped) < 0.5 ? current : snapped));
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (el.parentElement) observer.observe(el.parentElement);
    return () => observer.disconnect();
  }, [ref, enabled]);

  return height;
}

function SingleDocument({
  document: doc,
  selection,
  onSelectRange,
  decorations,
  wrap,
  narrow,
  fillsViewport,
  tapSizedRows,
  snapRows,
}: {
  document: CodeDocument;
  selection?: CodeRange | null;
  onSelectRange?: (range: CodeRange) => void;
  decorations: Decoration[];
  wrap: boolean;
  narrow: boolean;
  fillsViewport: boolean;
  tapSizedRows: boolean;
  snapRows: boolean;
}) {
  // The selection is just another decoration by the time it reaches rendering.
  const all: Decoration[] = selection ? [...decorations, { range: selection, kind: 'selected' as const }] : decorations;

  const pinsSignature = narrow && fillsViewport;
  const { scrollerRef, firstVisibleLine } = useFirstVisibleLine(pinsSignature);
  const signature = pinsSignature ? enclosingSignature(doc.code, doc.language, firstVisibleLine) : null;

  // Per-line indentation, for the hanging indent below. Computed from the
  // source rather than from tokens: prism can split leading whitespace across
  // token spans, and this only needs the character count.
  const indents = lineIndents(doc.code);
  const indentOf = (lineNumber: number) => indents[lineNumber - 1] ?? 0;

  const snappedHeight = useSnappedHeight(scrollerRef, snapRows && pinsSignature);
  // 'snap' shrinks the PANE so its bottom border sits directly under the last
  // whole row. 'clip' leaves the pane at its full height and constrains only
  // the scrolling area, so the leftover shows as background inside the border.
  const snapStyle = snappedHeight !== null ? { maxHeight: `${snappedHeight}px` } : undefined;

  return (
    <Highlight theme={readingSyntaxTheme} code={trimmedCode(doc.code)} language={doc.language}>
      {({ className, tokens, getLineProps, getTokenProps }) => {
        const gutterStateFor = (line: number): GutterCellState => {
          const kind = gutterDecorationForLine(all, line);
          return kind ? (GUTTER_STATE[kind] ?? 'default') : 'default';
        };
        const rowClassFor = (line: number): string => {
          const kind = rowDecorationForLine(all, line);
          return kind ? (ROW_TINT[kind] ?? '') : '';
        };
        const selectLine = onSelectRange ? (line: number) => onSelectRange(lineRange(line)) : undefined;

        const renderTokens = (line: (typeof tokens)[number]) =>
          line.map((token, key) => {
            const { className: tokenClassName, ...tokenProps } = getTokenProps({ token });
            return <span key={key} className={tokenClassName} {...tokenProps} />;
          });

        // --- wrap mode ------------------------------------------------------
        //
        // Two rendering paths, because scroll and wrap genuinely differ in
        // structure. Scroll needs ONE horizontally scrolling code area, so the
        // gutter is a sibling column outside it. Wrap needs each logical line
        // to be a row that grows vertically with its gutter cell pinned to its
        // first visual row. A grid cannot give the code area one shared
        // scrollbar, and a sibling column cannot follow a wrapped line down.
        //
        // Decision 5 falls out of decision 1 here: the wrapped group is ONE
        // element and therefore one tap target, so a tap on a continuation row
        // cannot resolve to a different line.
        if (wrap) {
          const rows = (
            <>
              {tokens.map((line, i) => {
                const lineNumber = i + 1;
                const rowClass = rowClassFor(lineNumber);
                // prism's getLineProps returns BOTH className and style. It used
                // to be spread after our own `style`, which silently replaced the
                // hanging indent with prism's value (usually undefined) -- the
                // indent was never applied at all. Pull both out and merge.
                const { className: lineClassName, style: lineStyle, ...lineProps } = getLineProps({ line });
                const state = gutterStateFor(lineNumber);
                const noted = lineHasNote(all, lineNumber);
                const Row = selectLine ? 'button' : 'div';
                return (
                  <Row
                    key={lineNumber}
                    data-line={lineNumber}
                    {...(selectLine
                      ? {
                          type: 'button' as const,
                          onClick: () => selectLine(lineNumber),
                          'aria-label': `Select line ${lineNumber}`,
                          'aria-pressed': state === 'selected',
                        }
                      : {})}
                    className={`flex w-full items-start text-left ${selectLine ? 'cursor-pointer' : ''}`}
                    style={{ touchAction: 'manipulation' }}
                  >
                    {/*
                      D-130: on narrow screens the hit area reaches the screen
                      edge by eating the page padding, via a negative margin
                      restored as padding. That widens the target WITHOUT
                      touching line-height -- growing it vertically would make
                      adjacent lines overlap, and a mistap that selects the
                      wrong line is exactly the failure this interaction cannot
                      have.
                    */}
                    <span
                      aria-hidden="true"
                      className={`shrink-0 select-none self-stretch pr-3 text-right tabular-nums w-gutter md:w-gutter-desktop ${
                        narrow && fillsViewport ? 'pl-page box-content' : ''
                      } ${
                        state === 'selected'
                          ? 'text-action bg-action-tint'
                          : state === 'correct'
                            ? 'text-correct bg-correct-tint'
                            : state === 'incorrect'
                              ? 'text-incorrect bg-incorrect-tint'
                              : 'text-ink-muted'
                      }`}
                    >
                      {lineNumber}
                      {noted ? <span className="ml-1 text-action">•</span> : null}
                    </span>
                    {/*
                      Hanging indent, measured from THIS LINE'S OWN
                      indentation (D-132).
                      The previous version used a fixed `text-indent: -2ch` with
                      `padding-left: calc(1rem + 2ch)`, which is relative to the
                      CONTAINER and ignores the line's leading whitespace. On a
                      12-space-indented line the continuation landed ~12
                      characters LEFT of the code it continues, so a wrapped
                      statement read as if it sat at a shallower nesting level.
                      In a code-comprehension app that is worse than horizontal
                      scroll: scrolling hides structure, this MISREPRESENTS it.

                      The fix: pad by (own indent + hang) and pull the first row
                      back by the same amount. Row 1 therefore starts where it
                      always did (its leading spaces still render), and every
                      continuation row starts at own-indent + hang -- strictly
                      right of the code it continues, which is the invariant.
                    */}
                    <span
                      className={`${lineClassName} ${rowClass} min-w-0 flex-1 whitespace-pre-wrap break-words px-4`}
                      {...lineProps}
                      style={{
                        ...lineStyle,
                        textIndent: `calc(-1 * (${indentOf(lineNumber)}ch + ${HANG_CH}ch))`,
                        paddingLeft: `calc(1rem + ${indentOf(lineNumber)}ch + ${HANG_CH}ch)`,
                      }}
                    >
                      {renderTokens(line)}
                    </span>
                  </Row>
                );
              })}
            </>
          );

          if (!pinsSignature) {
            return (
              <div className="overflow-hidden rounded-soft border border-border bg-surface-reading">
                <div className={`${className} m-0 flex flex-col py-3 font-code text-code leading-code`}>{rows}</div>
              </div>
            );
          }

          return (
            // FULL BLEED on narrow (D-130). The block gives up its side borders
            // and radius and runs to both screen edges, which is what lets a
            // line's hit area reach the edge: a bordered, overflow-hidden box
            // clips any child trying to escape it, so the escape has to be the
            // box's own. The dead page margin becomes gutter, and a thumb
            // reaching for a line number no longer has to land inside a 48px
            // strip inset 16px from the edge it is travelling from.
            <div
              className="-mx-page flex min-h-0 flex-1 flex-col overflow-hidden border-y border-border bg-surface-reading"
              // D-132: the row height for this pane, and the snapping unit.
              // A wrapped line is always a whole number of rows, so snapping
              // the pane to a multiple of the row height guarantees no
              // partial VISUAL row, wrapped or not.
              style={tapSizedRows ? ({ ["--code-line-height" as string]: "var(--tap-min)" } as React.CSSProperties) : undefined}
            >
              <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto" style={snapStyle}>
                {/*
                  The enclosing signature, pinned (D-130). Scrolling into the
                  middle of a long function otherwise costs you the one piece of
                  context that makes the body legible: what you are inside. It
                  renders only when there IS an enclosing scope above the fold,
                  so short snippets never grow a header they do not need.
                */}
                {signature ? (
                  <div data-sticky-signature className="sticky top-0 z-10 flex items-baseline gap-2 border-b border-border bg-surface-raised/95 px-4 py-1 font-code text-2xs text-ink-muted backdrop-blur-sm">
                    <span className="tabular-nums text-ink-muted/70">{signature.line}</span>
                    <span className="truncate">{signature.text}</span>
                  </div>
                ) : null}
                <div className={`${className} m-0 flex flex-col py-3 font-code text-code leading-code`}>{rows}</div>
              </div>
            </div>
          );
        }

        // --- scroll mode (the default above the breakpoint, and the exact
        // markup this component emitted before D-130) ------------------------
        return (
          <div className="flex overflow-hidden rounded-soft border border-border bg-surface-reading">
            <div className="shrink-0 select-none border-r border-border bg-surface-raised py-3 w-gutter md:w-gutter-desktop">
              <GutterSlots
                slots={tokens.map((_, i): GutterSlot => {
                  const line = i + 1;
                  return {
                    kind: 'lineNumber',
                    key: String(line),
                    line,
                    state: gutterStateFor(line),
                    hasNote: lineHasNote(all, line),
                    onClick: selectLine ? () => selectLine(line) : undefined,
                  };
                })}
              />
            </div>
            <pre className={`${className} m-0 flex-1 overflow-x-auto py-3 px-4 font-code text-code leading-code`}>
              {tokens.map((line, i) => {
                const lineNumber = i + 1;
                const rowClass = rowClassFor(lineNumber);
                const { className: lineClassName, ...lineProps } = getLineProps({ line });
                return (
                  <div key={lineNumber} className={`${lineClassName} ${rowClass} -mx-4 px-4`} {...lineProps}>
                    {renderTokens(line)}
                  </div>
                );
              })}
            </pre>
          </div>
        );
      }}
    </Highlight>
  );
}

export function CodeBlock({
  documents,
  selection,
  onSelectRange,
  decorations = [],
  wrapMode,
  fillsViewport = false,
  tapSizedRows = false,
  snapRows = true,
}: CodeBlockProps) {
  const narrow = useIsNarrow();
  const { mode } = useWrapPreference();
  const wrap = (wrapMode ?? mode) === 'wrap';

  // A one-document payload renders with no extra wrapper, so the markup is
  // exactly what it was before the refactor. Only a genuinely multi-document
  // block gets a container, and no live type takes that path today.
  if (documents.length === 1) {
    return (
      <SingleDocument
        document={documents[0]}
        selection={selection}
        onSelectRange={onSelectRange}
        decorations={decorations}
        wrap={wrap}
        narrow={narrow}
        fillsViewport={fillsViewport}
        tapSizedRows={tapSizedRows}
        snapRows={snapRows}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2" data-multi-document={documents.length}>
      {documents.map((doc) => (
        <div key={doc.id} data-document-id={doc.id}>
          {doc.label ? <p className="mb-1 text-sm font-medium text-ink-muted">{doc.label}</p> : null}
          <SingleDocument
            document={doc}
            selection={selection}
            onSelectRange={onSelectRange}
            decorations={decorations}
            wrap={wrap}
            narrow={narrow}
            fillsViewport={false}
            tapSizedRows={tapSizedRows}
            snapRows={snapRows}
          />
        </div>
      ))}
    </div>
  );
}

/** Back-compat helper for callers that still hold a bare code string. */
export { documentsFromCode };

// Re-exported so call sites import the gutter primitive from one place.
export { GutterLineButton };
export type { CodeRange, Decoration, CodeDocument };
export { rangeCoversLine };

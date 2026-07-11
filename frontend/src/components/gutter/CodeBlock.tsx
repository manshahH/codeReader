import { Highlight } from 'prism-react-renderer';

import { GutterLineButton, type GutterCellState } from './Gutter';
import { readingSyntaxTheme } from './syntaxTheme';

export interface CodeBlockProps {
  code: string;
  language?: string;
  selectedLine?: number | null;
  onSelectLine?: (line: number) => void;
  markLines?: Record<number, 'correct' | 'incorrect'>;
  notedLines?: Set<number>;
}

const trimmedCode = (code: string) => code.replace(/\n+$/, '');

export function CodeBlock({ code, language = 'python', selectedLine, onSelectLine, markLines, notedLines }: CodeBlockProps) {
  return (
    <Highlight theme={readingSyntaxTheme} code={trimmedCode(code)} language={language}>
      {({ className, tokens, getLineProps, getTokenProps }) => (
        <div className="flex overflow-hidden rounded-soft border border-border bg-surface-reading">
          <div className="shrink-0 select-none border-r border-border bg-surface-raised py-3 w-gutter md:w-gutter-desktop">
            {tokens.map((_, i) => {
              const line = i + 1;
              const state: GutterCellState = selectedLine === line
                ? 'selected'
                : markLines?.[line] === 'correct'
                  ? 'correct'
                  : markLines?.[line] === 'incorrect'
                    ? 'incorrect'
                    : 'default';
              return (
                <GutterLineButton
                  key={line}
                  line={line}
                  state={state}
                  hasNote={notedLines?.has(line)}
                  onClick={onSelectLine ? () => onSelectLine(line) : undefined}
                />
              );
            })}
          </div>
          <pre className={`${className} m-0 flex-1 overflow-x-auto py-3 px-4 font-code text-code leading-relaxed`}>
            {tokens.map((line, i) => {
              const lineNumber = i + 1;
              const rowState = markLines?.[lineNumber];
              const rowClass = rowState === 'correct' ? 'bg-correct-tint' : rowState === 'incorrect' ? 'bg-incorrect-tint' : '';
              const { className: lineClassName, ...lineProps } = getLineProps({ line });
              return (
                <div key={lineNumber} className={`${lineClassName} ${rowClass} -mx-4 px-4`} {...lineProps}>
                  {line.map((token, key) => {
                    const { className: tokenClassName, ...tokenProps } = getTokenProps({ token });
                    return <span key={key} className={tokenClassName} {...tokenProps} />;
                  })}
                </div>
              );
            })}
          </pre>
        </div>
      )}
    </Highlight>
  );
}

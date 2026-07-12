import type { PrismTheme } from 'prism-react-renderer';

// One muted theme, tuned for the single dark reading surface (D-98): every
// color is a CSS variable, defined once in tokens.css.
export const readingSyntaxTheme: PrismTheme = {
  plain: { color: 'var(--syntax-plain)' },
  styles: [
    { types: ['comment', 'prolog', 'doctype', 'cdata'], style: { color: 'var(--syntax-comment)', fontStyle: 'italic' } },
    { types: ['keyword', 'builtin'], style: { color: 'var(--syntax-keyword)' } },
    { types: ['string', 'char', 'attr-value'], style: { color: 'var(--syntax-string)' } },
    { types: ['function', 'class-name'], style: { color: 'var(--syntax-function)' } },
    { types: ['number', 'boolean', 'constant'], style: { color: 'var(--syntax-number)' } },
    { types: ['operator', 'punctuation'], style: { color: 'var(--syntax-punctuation)' } },
  ],
};

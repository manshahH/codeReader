/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    // Overrides (not extend): the default indigo/red/green ramp and the
    // sprawling default spacing scale are exactly the reach-for-a-default
    // failure mode this app is built to avoid. Only the semantic tokens
    // exist as utility classes.
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      'surface-reading': 'var(--surface-reading)',
      'surface-raised': 'var(--surface-raised)',
      ink: 'var(--color-ink)',
      'ink-muted': 'var(--color-ink-muted)',
      border: 'var(--color-border)',
      scrim: 'var(--color-scrim)',
      correct: 'var(--color-correct)',
      incorrect: 'var(--color-incorrect)',
      action: 'var(--color-action)',
      'action-hover': 'var(--color-action-hover)',
      'action-tint': 'var(--color-action-tint)',
      'correct-tint': 'var(--color-correct-tint)',
      'incorrect-tint': 'var(--color-incorrect-tint)',
      'syntax-plain': 'var(--syntax-plain)',
      'syntax-comment': 'var(--syntax-comment)',
      'syntax-keyword': 'var(--syntax-keyword)',
      'syntax-string': 'var(--syntax-string)',
      'syntax-function': 'var(--syntax-function)',
      'syntax-number': 'var(--syntax-number)',
      'syntax-punctuation': 'var(--syntax-punctuation)',
    },
    spacing: {
      0: '0px',
      px: '1px',
      1: 'var(--space-1)',
      2: 'var(--space-2)',
      3: 'var(--space-3)',
      4: 'var(--space-4)',
      5: 'var(--space-5)',
      6: 'var(--space-6)',
      7: 'var(--space-7)',
      8: 'var(--space-8)',
      9: 'var(--space-9)',
      10: 'var(--space-10)',
      gutter: 'var(--gutter-width)',
      'gutter-desktop': 'var(--gutter-width-desktop)',
      // D-130: the narrow page padding, named so the gutter can reclaim it as
      // hit area (-ml-page / pl-page) instead of hard-coding 16px.
      page: 'var(--page-pad-narrow)',
      tap: 'var(--tap-min)',
      'safe-bottom': 'var(--safe-bottom)',
      'safe-top': 'var(--safe-top)',
    },
    borderRadius: {
      none: '0px',
      tight: 'var(--radius-tight)',
      soft: 'var(--radius-soft)',
      loose: 'var(--radius-loose)',
      tick: 'var(--radius-tick)',
    },
    fontSize: {
      '2xs': 'var(--text-2xs)',
      xs: 'var(--text-xs)',
      sm: 'var(--text-sm)',
      base: 'var(--text-base)',
      lg: 'var(--text-lg)',
      xl: 'var(--text-xl)',
      '2xl': 'var(--text-2xl)',
      '3xl': 'var(--text-3xl)',
      '4xl': 'var(--text-4xl)',
      code: 'var(--text-code)',
    },
    fontFamily: {
      code: ['var(--font-code)'],
      explanation: ['var(--font-explanation)'],
      ui: ['var(--font-ui)'],
    },
    extend: {
      transitionDuration: {
        fast: 'var(--motion-fast)',
        DEFAULT: 'var(--motion-base)',
        max: 'var(--motion-max)',
      },
      transitionTimingFunction: {
        DEFAULT: 'var(--motion-ease)',
      },
      maxWidth: {
        measure: '65ch',
      },
      // D-130: minHeight has its own scale in Tailwind, so the touch floor has
      // to be declared here to exist as `min-h-tap`.
      // D-131: the code line-height token, so a line's tap-target height is
      // set in one place (tokens.css) rather than per component.
      lineHeight: {
        code: 'var(--code-line-height)',
      },
      minHeight: {
        tap: 'var(--tap-min)',
      },
      minWidth: {
        tap: 'var(--tap-min)',
      },
    },
  },
  plugins: [],
};

# 08b : Approved Frontend Tokens (M6)

These tokens were produced during the M6 design phase and APPROVED. They are
binding for the frontend build. Do not re-derive or substitute.

## Palette
- Reading surface (light, default): #FAFAF7
- Reading surface (dark, offered, NOT default): #0F1419
- --color-correct: #059669   (green — RESERVED for correctness/diff only)
- --color-incorrect: #DC2626 (red — RESERVED for correctness/diff only)
- --color-action: #1E40AF    (annotation-ink blue; never purple/indigo)

## Typefaces (self-hosted, no runtime CDN)
- Code: Iosevka (characterful, real italics). JetBrains Mono only as last-resort
  fallback, never the identity.
- Explanations: Source Serif 4 (OFL) — the explanation is the product.
- UI chrome: IBM Plex Sans (not Inter/Poppins/Space Grotesk).

## Scales & rules
- 9-level responsive type scale; 4px-based spacing scale (10 levels).
- Intentional radius variation (no identical-16px-everywhere).
- One custom muted syntax theme, both modes, tuned for reading.
- Dark mode: explicit user toggle, default LIGHT. No system-preference auto-switch.
- Gutter width on mobile: 48px.
- Reveal animation: subtle, <300ms, transform/opacity only, respect
  prefers-reduced-motion.

## Gutter signature (layout spine, not a code decoration)
- Session progress = gutter marks.
- Streak history = column of gutter ticks (not a flame emoji).
- spot_the_bug line selection = tap the line number IN the gutter.
- Reveal annotations connect explanation notes to gutter line numbers.

## Slop audit
Self-audited 0/16 catalogue patterns at design time. Re-audit per screen at build.

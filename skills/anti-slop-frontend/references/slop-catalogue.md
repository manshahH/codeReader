# Slop catalogue (deep reference)

Load this when auditing existing frontend code, when you want the deterministic checks, or when you need the specific font/color names so you don't accidentally default into them. The SKILL.md covers the patterns and fixes; this is the checklist-grade inventory plus sources.

Everything here is a *correlation*, not a verdict. A deterministic audit of these patterns still runs ~5–10% false positives, and human-built pages trip them too (the pre-LLM equivalent was everyone using Bootstrap). Use this to audit your own output, not to accuse others.

## Contents
1. The 16-pattern deterministic checklist (with frequencies)
2. Fonts: the overused set
3. Color: the exact tells and the fixes
4. Layout and component signatures
5. Motion rules
6. Code-level fingerprints
7. Tool-specific notes
8. What the clean pages do
9. Not-a-tell / do-not-overcorrect
10. Sources

---

## 1. The 16-pattern deterministic checklist

From Adrian Krebs' audit of 1,590 Show HN landing pages, scored with Playwright against computed styles (no LLM judge, to avoid measuring the bias with the bias). Buckets: 0–1 patterns = clean, 2–3 = mild, 4+ = heavy slop. Score your own page the same way.

**Fonts**
1. Inter used for everything, especially a centered hero headline.
2. The same combos on rotation: Space Grotesk, Instrument Serif, Geist.
3. Serif italic as the accent for one hero word on an otherwise-Inter page.

**Color**
4. "VibeCode purple" — a specific lavender-indigo that leaks from image-gen and text-to-page prompts.
5. Permanent dark mode with medium-grey body text and all-caps section labels.
6. Barely-passing (or failing) body-text contrast in dark themes.
7. Gradients everywhere.
8. Large colored glows and colored box-shadows.

**Layout**
9. Centered hero set in a generic sans.
10. Badge/pill positioned right above the hero H1.
11. Colored borders on cards, usually top or left edge. *(The single most specific tell — "almost as reliable as em-dashes for text.")*
12. Identical feature cards with an icon on top.
13. Numbered "1, 2, 3" step sequences.
14. Stat-banner rows.
15. Sidebar or nav with emoji icons.
16. All-caps headings and section labels.

**CSS (the two dominant fingerprints)**
- Untouched shadcn/ui defaults (the library is explicitly designed to be copy-pasted by agents, so unstyled output converges on its look).
- Glassmorphism (frosted-glass cards, backdrop-blur) as the reflated 2022 default.

Most common single tells by frequency: permanent dark theme 34%, gradient backgrounds 27%, icon-card grids 22%.

## 2. Fonts: the overused set

Defaulting into any of these is the tell; choosing one on purpose is fine. Overused right now: **Inter** (the "Helvetica of the LLM era"), Poppins, Geist, Space Grotesk, Instrument Sans, Instrument Serif, General Sans, Inter Display, Cal Sans. The serif-italic-accent-word-in-an-Inter-hero move is its own specific tell.

Deliberate alternatives cited by designers (examples, not a new default list): Geist paired with a non-Inter body, Haas Grotesk, Untitled Sans, Söhne, Inktrap, Migra; for serifs, Tiempos, GT Sectra, Freight Text, Playfair Display, Bricolage Grotesque, JetBrains Mono for dev-tool products. The rule is a display face with personality + a *distinct* body face + an intentional scale. Custom or commissioned type is the strongest signal of intent (Vercel's Geist, Stripe's bespoke serif, Linear's modified type).

## 3. Color: the exact tells and the fixes

**Tells:** the lavender/indigo accent band; `bg-indigo-500/600` + `hover:bg-indigo-700` straight from Tailwind's default (its creator, Adam Wathan, publicly apologized for picking `bg-indigo-500` as the Tailwind UI default); purple→blue and cyan→pink gradients; aurora ambient glow backgrounds; gradient-filled headline text; colored glows / colored box-shadows; pure `#000` and `#fff`; untinted greys; shadcn default gray ramp; dark mode selected by default with grey body text under AA contrast.

**Fixes:**
- Semantic tokens with meaning-based names (`--color-action-primary`, `--color-feedback-success`), never decorative names.
- No pure black or white; tint neutrals toward the brand hue so the UI feels cohesive.
- Consider OKLCH for controlled light/dark palettes.
- Hold WCAG AA: 4.5:1 body text, 3:1 large headings. Avoid washed-out grey text and oversaturated dark-mode colors.
- Restrained color inside product UI; stronger committed color reserved for brand/marketing surfaces.
- Gradients only where they carry meaning, not as ambient "future tech" vibe on a plumber's site.

## 4. Layout and component signatures

- **Centered-hero stack:** pill badge → oversized vague H1 → subhead → two CTAs. The default composition.
- **Icon-card grid:** three identical cards, icon on top, uniform height. If you have seven features with seven icon treatments, that's slop; one repeated primitive is design.
- **Colored-edge cards:** a 3–4px colored stripe on the left or top of cards/blockquotes. The most reliable single tell.
- **Numbered step sequences** used where nothing is actually sequential.
- **Stat banners** ("99.9% uptime," "500M requests," "10x faster") — performing authority, usually unearned.
- **Floating social-proof pills** ("Trusted by 10,000+ teams," "AI Powered") with blur/glow, signaling credibility before the product is even explained.
- **Sticky transparent navbar; middle pricing plan elevated; FAQ accordion at the bottom** — the recurring section furniture.
- **Fake dashboard mockup** in the hero (charts up-and-to-the-right) that shows off "looking like software" instead of explaining it. A real screenshot beats it.
- **Uniformity:** identical padding, identical 16px border-radius on everything, shadows at exactly 0.1 opacity. Real hierarchy comes from intentional variation.
- **Unmotivated bento grids** and **glassmorphism stacks** (glass-on-glass until text is unreadable).

Fix pattern throughout: a structural device (number, eyebrow, divider, border, stat) is allowed only when it encodes something true about the content. Otherwise it's decoration that happens to be the model's default.

## 5. Motion rules

Tells: uniform fade-in on every element on scroll; the bouncing scroll-indicator mouse; hover-glow and Y-transform on everything; or no motion at all.

Purposeful-motion rules (Emil Kowalski-style, widely cited):
- Animate **`transform` and `opacity` only** where possible (cheap, smooth).
- Keep motion **under ~300ms**.
- Use **custom easing**, not the same default curve everywhere.
- Motion must do a job: communicate a state change, direct attention, or express brand character — matched to the product (precise/mathematical vs. playful/bouncy).
- Always respect **`prefers-reduced-motion`**.
- Start with micro-interactions on primary CTAs and inputs; add scroll animation only where it serves navigation or storytelling; delete purely decorative motion.

## 6. Code-level fingerprints

- Tailwind indigo defaults (`bg-indigo-600`, `hover:bg-indigo-700`).
- Raw hex codes scattered per component instead of tokens → the model invents new values → **visual drift**, where late sections stop matching the early color/spacing system (worsens on long single-agent builds that lose earlier context).
- div-soup, missing semantic HTML and landmarks.
- Inline styles, no central token file, no `DESIGN.md`.
- Leftover placeholder lorem, stray "as an AI" comments, or generated TODO stubs.
- Accessibility gaps that ship by default: no visible keyboard focus, missing labels, broken mobile states.

Architecture fix: define all tokens in one file at the first commit; keep components from hard-coding color/font/spacing; keep a `DESIGN.md` at project root so every prompt snaps to the same system. This also makes it cheap to generate several variants and pick one, instead of being stuck with the first (statistically slop) output.

## 7. Tool-specific notes

- **shadcn/ui:** excellent, but built to be copy-pasted by agents, so untouched output converges everywhere. Customize color tokens, radius, shadow depth, and component variants before shipping.
- **v0, Lovable, Bolt, Cursor, Claude Code, Gemini CLI, Codex:** all pull from the same React/Tailwind training distribution, so all default to the same fingerprint without direction. Single-agent chat builders also drift over long projects as early design context falls out of the window.
- **Framer/Webflow AI and website builders:** aurora backgrounds, Instrument Sans, floating stat bars, glass cards as house defaults.
- Prompting: total openness ("build me a fitness landing page") returns the statistical mean. Over-specifying every default ("64px Inter Bold, purple gradient #6366f1→#8b5cf6, 8px radius") is a recipe for slop — you handed the model every default it would have picked. The sweet spot is principle-based direction: name the dimensions to think about, reference inspirations without copying, and explicitly list the defaults to avoid.

## 8. What the clean pages do

Three consistent moves separated the clean 46% in the audit:
1. A palette with a point of view, explicitly not the default lavender (earth tones; high-contrast black + one bright; cream-and-pink; disciplined grey-and-blue).
2. A type system that is not Inter, with a display face + a distinct body face.
3. **One strong layout primitive, repeated** until it becomes the signature — the single highest-leverage discipline.

Plus: real photography and product screenshots over stock and fake dashboards; copy in a specific human voice ("would our founder actually say this?"); purposeful motion; and a codified token system so distinctiveness survives to the next page.

## 9. Not-a-tell / do-not-overcorrect

- **Polish and clean code are not tells.** Don't add ugliness or bugs to seem human.
- **Using AI is not the problem.** It's great for structure, scaffolding, and boilerplate; the problem is shipping the first draft unrefined.
- **A pattern chosen on purpose is fine.** Inter, shadcn, a purple accent, a dark theme — all legitimate when the brief asks for them. The brief's explicit request always wins.
- **Slop isn't morally bad or non-converting.** The cost is differentiation, not function. This is taste calibration in an era of mass-produced defaults, not gatekeeping.
- **Restraint beats maximalism as the escape.** Over-designing (parallax everywhere, custom cursors, layered gradients) is a different slop, not a cure.

## 10. Sources

- Adrian Krebs, "Scoring Show HN submissions for AI design patterns" (2026) — the 1,590-page Playwright audit, 16-pattern rubric, frequencies, and the "slop is uninspired, not bad" framing.
- Developers Digest, "AI Design Slop: 16 Patterns That Out Your App as Vibe-Coded" (2026).
- 925studios, "AI Slop Web Design: Complete Guide" (2026) — spotting, fixing, and the overcorrection mistakes.
- NewWebsite.ai, "10 Signs a Website Was Designed by AI" (2026).
- The Fountain Institute, "7 Signs a UI Has Been Vibe Coded" (2026) — emoji-as-UI, purple-as-Times-New-Roman.
- Thomas Wiegold, "Claude Code frontend-design plugin" (2026) — the fingerprint, Adam Wathan's indigo apology, token/`DESIGN.md` architecture, principle-based prompting.
- DEV.to (alanwest), "How to fix the AI-generated look in your frontend" (2026).
- Monet, "Escape AI Slop landing page design" (2026) — token-aware config and prompting.
- Mohamed Elkholy, "Beyond Make it Beautiful: The Anti-Slop Framework" (2026) — Emil Kowalski motion rules, OKLCH color rules.
- Taste Skill (tasteskill.dev) and Muzli/8080.ai, "Why every AI-built app looks the same" (2026) — brief-inference and context-drift.
- Anthropic `frontend-design` skill (bundled) — the generative counterpart.

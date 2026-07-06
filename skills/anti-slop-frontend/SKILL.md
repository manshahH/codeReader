---
name: anti-slop-frontend
description: Build and review web UI that does not read as AI-generated. Use this whenever you are designing, coding, or critiquing a website, landing page, web app, dashboard, or UI component — HTML/CSS, React, Vue, Tailwind, shadcn, or any frontend stack — and especially when the user wants a site that looks intentional, distinctive, custom, or "not AI-generated / not vibe-coded / not slop." Apply it silently on any substantial frontend build too, because the default failure mode is a polished, generic, purple-gradient landing page that could belong to any company. This is the detection-and-avoidance field guide; pair it with the frontend-design skill, which covers generating a distinctive direction. Not for backend, data, or non-visual code.
---

# Anti-slop frontend

The goal is simple: never ship a page that makes a viewer think "a chatbot made this." This skill is the field guide to the specific visual and code patterns that give away AI-generated frontends, why they happen, and what to do instead. It pairs with the `frontend-design` skill (which drives the positive, generative side); this one is the inverse — the tells to avoid and the audit to run before shipping.

Read the root cause first. Every tell below is a symptom of it.

## The root cause: regression to the mean

An LLM generates UI by predicting the most probable next token given billions of public code samples. Those samples are overwhelmingly tutorials, starter templates, and component-library docs, which all lean on the same defaults. The probability mass sits squarely on the design conventions that dominated developer Twitter and Dribbble around 2020–2022: Tailwind UI, Linear's "Magic Blue," early Stripe and Vercel, shadcn, Bootstrap-era templates. So the default output is the statistical median of every landing page ever scraped. It is not bad. It is *average design at scale*, and average is invisible.

The fix is not a banned-list of fonts and colors. It is intent: make each visual decision deliberately, grounded in this specific subject, and refuse to accept the default just because it is what came out. You can still choose Inter, or a purple accent, or shadcn — but choose it because it serves the brief, not because the model reached for it. A useful gut check for any screen: *could this exact layout, palette, and copy belong to a completely different product?* If yes, it is slop, however polished.

## The AI fingerprint at a glance

An audit of 1,590 Show HN landing pages (Krebs, 2026) scored each against 16 deterministic patterns and found 22% were heavy slop (4+ patterns), 32% mild, 46% clean. The most common single tells were a permanent dark theme (34%), gradient backgrounds (27%), and icon-card grids (22%). The composite "you've seen it a thousand times" page is:

> Centered hero, a pill badge above a big vague headline, purple-to-blue gradient somewhere, two CTA buttons, three identical feature cards with an icon on top, a stat banner, Inter throughout, uniform border-radius, shadows at exactly 0.1 opacity, everything fading in on scroll.

If what you're about to build matches that description, stop and make real choices.

## What clean pages do instead (the positive targets)

Aim at these directly. They are what separated the clean 46% in the audit, and what distinctive products (Linear, Stripe, Notion, Vercel, Basecamp) actually do.

- **A palette with a point of view.** Warm earth tones, high-contrast black plus one bright accent, a cream-and-pink, a disciplined grey-and-blue — anything that is a choice. Tint neutrals toward the brand hue; avoid pure `#000` and `#fff`. Hold WCAG AA contrast (4.5:1 body, 3:1 large text), which generated dark themes routinely fail.
- **A type system that is not the default.** Pick a display face with personality and pair it with a *distinct* body face. Set an intentional scale with real hierarchy. (See the reference file for the overused set to avoid defaulting into.)
- **One strong layout primitive, repeated.** This is the single highest-leverage discipline. Choose one structural idea and let it become the page's signature, instead of stacking seven different section types (cards, then stats, then steps, then a sidebar of emojis). Repetition of one good idea reads as design; variety of stock blocks reads as slop.
- **Ground everything in the subject.** The product's own world — its materials, vocabulary, data, artifacts — is where non-generic choices come from. Use the real content, not lorem and fake dashboards.
- **Semantic design tokens, defined once.** Put color, type, spacing, radius, and shadow in one token file (CSS variables / Tailwind config / a `DESIGN.md`) with meaning-based names (`--color-action-primary`, not `--purple-500`). This stops the model from inventing a new value per component, which is what produces visual drift where the end of the page no longer matches the start.
- **Purposeful motion only.** Animate to communicate a state change or direct attention, not to decorate. Follow the tight rules: animate `transform` and `opacity` only, keep it under ~300ms, use custom easing, and respect `prefers-reduced-motion`.

## The tells, by cluster

Each cluster names the fix inline. The exhaustive, checklist-grade version with CSS-level signatures and specific font/color names is in `references/slop-catalogue.md` — read it when auditing existing code or when you want the deterministic checks.

### Color and light
Purple/lavender-indigo accent (the "Times New Roman of AI design"); purple-to-blue gradients in hero, CTA, and backgrounds; aurora/ambient blurry glow backgrounds; gradient-filled headline text; large colored glows and colored box-shadows; permanent dark mode chosen by default with medium-grey low-contrast body text. **Fix:** pick a semantic palette for this brand; if dark mode, earn it and pass contrast; reserve gradients for where they carry meaning, not vibe.

### Typography
Inter (or Poppins) everywhere; the same "trying to escape" combos on rotation (Geist, Space Grotesk, Instrument Serif/Sans, General Sans, Inter Display); a single serif-italic accent word dropped into an otherwise-Inter hero; all-caps section labels; flat hierarchy with per-component font sizes. **Fix:** deliberate display+body pairing, one consistent scale, hierarchy through weight and size chosen on purpose.

### Layout and structure
Centered hero with a badge/pill directly above the H1; three (or N) identical feature cards with an icon on top; **colored left or top border on cards** — described as "almost as reliable a sign of AI design as em-dashes are for text," the most specific single tell; numbered 1-2-3 step sequences when the content is not actually a sequence; stat/metric banner rows; floating social-proof pills ("Trusted by 10,000+"); sticky transparent navbar; pricing with the middle plan elevated; FAQ accordion tacked to the bottom; fake dashboard mockup in the hero; uniform padding, identical 16px radius on everything, and shadows at exactly 0.1 opacity. **Fix:** structure should encode something true about the content. A number marker only if order matters; a stat only if it is real and earned; a card border only if it means something. Vary spacing and radius intentionally to build hierarchy.

### Components and iconography
Untouched shadcn defaults (the library is literally built to be copy-pasted by agents, so it converges everywhere); glassmorphism as a reflex (frosted cards, backdrop blur, one CSS rule to look "premium," stacked until unreadable); the default Lucide/Heroicons set because every tutorial uses them; **emoji used as UI** — nav icons, section headers, bullet replacements — which signals the interface never made a real iconography decision. **Fix:** customize shadcn tokens (radius, shadow, color, variants) if you use it; use glass sparingly and only where legibility survives; pick one coherent icon set and size it to context; keep emoji to genuine communication microcopy, never structural UI.

### Motion
Everything fading in with identical timing/easing on scroll; the bouncing scroll-indicator mouse in the hero; glow-on-hover and Y-transform on every element; or, the opposite, no motion at all. **Fix:** the purposeful-motion rules above. Cut any animation that exists only for polish.

### Copy
Vague aspirational headlines that fit any company ("Build the future," "Reimagine productivity," "Your all-in-one platform," "Scale without limits"); generic superlatives and hedging; unearned stats. **Fix:** specificity. "We help dentists fill cancellation slots in 4 hours" beats "Reimagine your practice." For prose beyond headlines, apply the `humanize` skill.

### Code-level fingerprints
`bg-indigo-500/600` with `hover:bg-indigo-700` (Tailwind's own creator publicly regrets making indigo the default); raw hex codes scattered instead of tokens; div-soup with no semantic HTML; inline styles and no token file; leftover placeholder lorem or stray AI comments; drift across a long build where later sections abandon the early color and spacing system. **Fix:** tokens first, semantic elements, one system referenced throughout.

## Workflow: pre-flight, build, audit

Two passes, mirroring how a studio actually works.

**Pre-flight (before writing code).** State the brief in one line: subject, audience, the page's single job. Then decide the token system — palette, type pairing, spacing/radius/shadow scale, and the one signature layout primitive — and write it down. Explicitly name the defaults you are *not* using for this brief. If any part of the plan is the generic answer you'd give for any similar page, change it and say why. Only then build, deriving every value from the tokens.

**Audit (before shipping).** Run the page against the checklist in `references/slop-catalogue.md`. Count the patterns it triggers. Four or more means heavy slop — go back. This works as a self-check on your own output and as a review of code you've been handed. Where you can, make the checks concrete (inspect computed styles: is the accent in the lavender-indigo band? are card borders colored on one edge? is body-text contrast below AA? is every radius identical?).

## The overcorrection trap — read before "fixing" slop

De-slopping is not "add chaos and call it human." The most common ways teams overcorrect, from the same sources that catalogued the tells:

- **Over-designing to compensate.** Layering gradients, parallax on every section, custom cursors, animated backgrounds. That is noise, not distinction. The products that escape slop (Linear, Notion, Stripe) do it through *restraint* — fewer choices, each intentional and consistent. Spend boldness in one place; keep the rest quiet.
- **Refusing AI entirely.** Hand-coding everything as a point of pride wastes what AI is genuinely good at: structure, responsive scaffolding, boilerplate. The problem is shipping the first output unrefined, not using the tool.
- **Changing visuals without changing content.** A custom font over "Empowering teams to build better products" is still slop, just more expensive. Fix design and copy together.
- **Skipping the system.** One-off tweaks let defaults creep back on the next page. Codify tokens so every new page starts from your foundation, not the model's.
- **Shipping ugly-random and calling it brave.** Ugly *on purpose* with a clear point of view is memorable; ugly by accident is not. Distinctiveness is a deliberate opinion, not the absence of polish.

Two calibration notes so this stays honest, not a witch-hunt. First, slop is not morally wrong or non-converting — the research is explicit that these pages often convert fine; the cost is *differentiation*, standing out in a sea of identical pages. Second, none of these patterns is banned. Inter, shadcn, a purple accent, and a dark theme are all legitimate when the brief calls for them. **The brief's explicit request always wins.** The tell is not the pattern itself; it is reaching for the pattern by default instead of by choice.

## Final principle

The entire skill reduces to one move: replace defaults with decisions. When you catch yourself about to emit the statistically likely thing — the indigo gradient, the three icon cards, Inter, the fade-in — pause and ask what *this* subject actually calls for. That question does more than any checklist.

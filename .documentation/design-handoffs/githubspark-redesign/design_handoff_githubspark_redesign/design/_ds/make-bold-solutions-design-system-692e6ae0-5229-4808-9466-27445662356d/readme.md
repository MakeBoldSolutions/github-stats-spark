# Make Bold Solutions — Design System

> Big firm expertise. Small firm heart. The brand system for Make Bold
> Solutions: tokens, components, UI kits and brand guidance derived from the
> official Brand Guidelines and the live site (makeboldsolutions.com).

---

## 1. About the company

**Make Bold Solutions** provides **fractional CFO services and strategic financial
leadership** to small and midsize businesses, sole proprietors, and nonprofits —
based in **Wichita, Kansas** and serving the surrounding region. It is led by
**Lesley Hazleton, CPA** — *Wichita Business Journal CFO of the Year, 2023*, a PwC
alumna with 30+ years of experience. The positioning line is **“Big Firm
Expertise. Small Firm Heart.”**: Fortune-500-grade financial discipline delivered
with hands-on, personal partnership, at the scope and pace each client needs.

The firm exists specifically to serve the businesses most accounting firms
overlook — small operators, sole proprietors, and mission-driven nonprofits — with
direct senior-level access (no junior hand-offs) and a focus on outcomes over
billable hours.

**Make Bold Spark** (makeboldspark.com) is the firm's technical arm — open-source
software and rapid-build tools that solve financial-services problems when
off-the-shelf software isn't enough.

The brand pairs two ideas — **bold** and **clear**. Decisions are decisive (“make
bold”); the value delivered is clarity. The identity reflects this: a sharp,
geometric peak mark and a confident rust-red, on calm cream surfaces with highly
readable type.

**Core values**
- **Clarity over complexity** — simplify the financial picture so leaders can act
  with confidence and focus on what matters most.
- **Bold, decisive leadership** — backed by disciplined analysis, deep experience,
  and accountability.
- **Rooted in experience & accountability** — financial foundations built for
  durable, long-term success.

**Services** (from the live site): Fractional CFO · Business Optimization ·
Nonprofit Governance · Fractional Corporate Controller · Strategic Tax Planning ·
Tax Preparation. Plus low-commitment starter engagements: Cash Flow Snapshot,
Books Cleanup Plan, Budget & Forecast Build, Nonprofit Kickstart.

**Primary surfaces.** A professional-services firm, not a software product:
1. **Marketing website** (makeboldsolutions.com) — the primary digital presence.
2. **Presentations / decks** — client proposals, board/treasurer reporting.
3. **Stationery** — business cards, letterhead (defined in the guide).

**Key contacts:**
- Lesley Hazleton, CPA — Principal — lesley.hazleton@makeboldsolutions.com — linkedin.com/in/lesleyhazleton
- Mark W. Hazleton — Chief Technology Officer (Make Bold Spark) — mark.hazleton@makeboldsolutions.com — +1 972 322 1066
- Wichita, Kansas · makeboldsolutions.com · makeboldspark.com

---

## 2. Sources

This system was built from the official brand asset package **`MakeBoldSolutions/`**
(mounted locally, read-only). Notable contents:

- `BrandGuide/MakeBoldSolutions.pdf` — 19-page Brand Guidelines (logo, color,
  type, stationery, contact). Full text extracted; key pages summarized here.
- `Fonts/Be_Vietnam_Pro.zip` — Be Vietnam Pro static TTFs (display face).
- `Fonts/InterTight/` — Inter Tight variable TTFs (body face).
- `SVG and AI/Logo.svg` — vector logo lockup (mark + wordmark).
- `RGB Files for Screens/` — PNG logo exports (vertical full-color, B&W,
  single-color; horizontal wordmarks; social profile).
- `Business Card/`, stationery `.ai` files — print collateral (not imported).
- **Print logo exports** (CMYK PRINTFILES) — full-color vertical lockup, mark,
  watermark, horizontal wordmark (cleaner than the RGB partial exports; imported).

The **live website** (https://makeboldsolutions.com) was also reviewed and is the
source of truth for product copy, services, and the website UI kit.

Copies of the imported originals live in `_src/` (working scratch); the cleaned,
shipped assets live in `assets/`.

> ⚠️ **No production codebase or Figma file was provided.** The website UI kit is
> a recreation built from the **live site's content** (copy, services, structure)
> on the brand tokens — it matches the real site's substance but is an independent
> rebuild, not the site's own code. Imagery uses the same Unsplash photography the
> live site references. A sample deck is offered but not yet built (no template was
> provided).

---

## 3. Content fundamentals — how Make Bold writes

The brand voice is **warm, senior, and accessible** — expert without being
stuffy. "Big firm expertise, small firm heart." Match it.

- **Tone:** assured and experienced, but approachable and human. It sounds like a
  seasoned CPA who genuinely partners with you — *"we bring the expertise and do
  the work alongside you."* Confident, never a hype-deck; warm, never corporate-cold.
- **Person:** speaks as **"we"** (the firm) to **"you"** (small-business owners,
  sole proprietors, nonprofit leaders). Partnership and reassurance framing —
  *"No obligation, no pressure"*, *"do the work alongside you."*
- **Casing:** sentence case for body and most headlines. The signature typographic
  move is the **spaced, uppercase "S O L U T I O N S"** under the wordmark —
  letter-spaced caps are a brand device for eyebrows and labels, never paragraphs.
- **Sentence shape:** short, declarative, parallel. Plain-spoken outcomes over
  jargon: *"cash flow clarity, a budget you can actually use, books you can trust."*
  Triads are common.
- **Positioning lines:** *"Big Firm Expertise. Small Firm Heart."* · *"Outcomes,
  not billable hours."* · *"Built for businesses others overlook."* · *"Every
  business deserves a great CFO."*
- **Vocabulary:** clarity, confidence, foundations, partnership, hands-on,
  senior-level, fractional, outcomes, rigor, discipline. Names the audience plainly
  (small businesses, sole proprietors, nonprofits). Credentials matter (CPA, PwC
  alumna, CFO of the Year). Avoid buzzwords and hyperbole.
- **Emoji:** **none.** This is a finance-leadership brand.
- **Punctuation:** restrained. Em dashes for asides. Sparing, purposeful.
- **Headline pattern:** a bold human claim, then a plain clarifier. e.g.
  *"Big firm expertise. Small firm heart. — Senior-level financial leadership for
  growing businesses, sole proprietors, and nonprofits."*

**Example phrases (brand-true):**
- "Big firm expertise. Small firm heart."
- "Every business deserves a great CFO."
- "We bring the expertise and do the work alongside you."
- "Outcomes you can see: cash flow clarity, a budget you can use, books you can trust."

---

## 4. Visual foundations

The system is **warm, geometric, and editorial** — confident rust against calm
cream, sharp type, generous space, minimal ornament.

### Color
- **Rust `#982407`** is the primary brand color — logos, headlines, key surfaces,
  high-impact moments. It is the single most recognizable brand asset. Use it with
  conviction but not everywhere; it reads best as the accent on cream or as a
  full-bleed brand panel.
- **Ember `#C6620C`** (orange) is the secondary accent — highlights, links,
  hovers, small emphasis. It is the warmer, brighter cousin of rust.
- **Ink `#1E1E1E`** is the near-black for text and dark surfaces. Not pure black —
  it's warm and soft.
- **Cream `#F8F6F2`** is the default page surface ("paper"). The brand lives on
  cream far more than on white; white is reserved for cards and elevated surfaces.
- Tints/shades and a warm neutral gray ramp are derived in `tokens/colors.css`.
  Status colors are intentionally muted (finance-grade), never candy-bright.
- **Imagery vibe:** warm, natural, professional — boardrooms, architecture,
  landscapes echoing the peak mark. Lean warm/neutral, not cool blue corporate.

### Typography
- **Be Vietnam Pro** — display face. Headlines, the wordmark, key brand moments.
  Geometric, confident, structured yet approachable. Used at extrabold/black for
  display, bold/semibold for headings.
- **Inter Tight** — body and UI face. Long-form content, labels, controls.
  Regular/Medium for text, Semibold/Bold for emphasis and subheads.
- Headlines are **tight**: negative letter-spacing (`--ls-tighter`/`--ls-tight`),
  line-height ~1.05–1.15, `text-wrap: balance`. Body is roomy (line-height 1.55).
- **Eyebrows / labels** use the signature **letter-spaced uppercase** treatment
  (`--ls-eyebrow: 0.18em`), usually in ember.

### Space & layout
- 4px base grid (`--space-*`). Generous section rhythm (`--section-y` up to 8rem).
- Content max-width ~1200px; prose ~68ch. Fluid gutters.
- Layout is calm and structured — clear columns, strong left alignment, plenty of
  negative space. Not dense; lets the rust accent and headlines breathe.

### Surfaces, borders, corners
- **Corner radii are modest** — 4–10px on cards/controls; the brand mark is sharp
  and geometric, so nothing is bubbly. Pills are reserved for deliberate chips/tags.
- **Cards:** white surface on cream page, hairline warm border
  (`--border-default`), small-to-medium soft shadow. Quiet, not floaty.
- **Borders** are warm-gray hairlines (1px). A 3px ember/rust accent border is a
  deliberate emphasis device (e.g. left rule on a pull-quote), used sparingly.

### Shadows
- Warm-tinted (rgba of ink `#1E1E1E`), **tight and low-spread** — restraint over
  drama. Scale `--shadow-xs … --shadow-xl`, plus a rust-tinted `--shadow-brand`
  for brand-colored elevated elements. No neon glows.

### Motion
- Purposeful and quick: `--dur-fast 120ms`, `--dur-base 200ms`. Easing is
  `--ease-standard` / `--ease-out` — **no bounce, no overshoot**. Fades and short
  translns. The brand is composed; animation should feel decisive, not playful.

### Interaction states
- **Hover:** darken brand surfaces one step (rust→`--rust-600`), or shift links to
  ember; subtle. Ghost/secondary buttons fill with a faint brand tint.
- **Press/active:** darken one more step + a 1px nudge down (no scale-shrink toys).
- **Focus:** 2px ember outline w/ offset, or a 3px soft focus ring (`--ring-focus`).
- **Disabled:** drop to ~45% opacity, no shadow.

### What to avoid
Bluish-purple gradients, glassmorphism, neon, emoji, candy colors, heavy drop
shadows, fully-rounded "pill everything" UI, decorative gradient blobs. The brand
is sober and warm.

---

## 5. Iconography

> ⚠️ **No icon set was provided** in the brand package — no icon font, sprite, or
> SVG icon library, and the guidelines do not specify one. The logo mark is the
> only proprietary graphic.

**Substitution (flagged):** the system uses **[Lucide](https://lucide.dev)** —
clean, geometric, **2px stroke** outline icons — linked from CDN. Lucide's
disciplined, structured line style matches Be Vietnam Pro and the sharp peak mark
far better than filled or rounded sets. Stroke icons in **ink** (or **ember** for
active/accent) at 20–24px. If the firm adopts an official icon set, swap it here.

- **Style rule:** outline (stroke) only, 2px, square-ish caps. No filled glyphs,
  no duotone, no emoji, no Unicode dingbats as icons.
- **Color:** `--text-strong` default; `--accent` for active/emphasis; inherit on
  brand surfaces.
- **The peak mark** (`assets/logos/logo-mark.svg`) is the brand's hero graphic —
  use it as a favicon, loader, bullet, and section ornament. Don't redraw it.

Lucide CDN (used in cards/kits):
```html
<script src="https://unpkg.com/lucide@latest"></script>
<script>lucide.createIcons();</script>
```

---

## 6. Assets (`assets/`)

**Logos** (`assets/logos/`)
- `logo-mark.svg` — the two-peak mark only (rust + ink), clean vector. Hero graphic.
- `logo-mark-wordmark.svg` — full primary lockup (mark + "MakeBold" + spaced
  "SOLUTIONS"), brand-colored vector.
- `logo-vertical-full-color.png` / `-bw.png` / `-single-color.png` — stacked
  lockups (PNG exports).
- `wordmark-horizontal.png` / `-dark.png` — horizontal wordmark lockups.
- `social-profile.png` — square social avatar.

Logo usage rules (from guide): preserve clear space = **1× X** (X = height of the
tallest peak) on all sides; never recolor, distort, rotate, or crowd the logo.

**Fonts** (`assets/fonts/`) — Be Vietnam Pro static weights (400–900) + Inter Tight
variable (roman + italic). Declared in `tokens/fonts.css`.

---

## 7. Index / manifest

**Root**
- `styles.css` — global entry point (consumers link this). `@import` list only.
- `readme.md` — this file.
- `SKILL.md` — portable Agent-Skill wrapper.

**Tokens** (`tokens/`, all reachable from `styles.css`)
- `fonts.css` — `@font-face` declarations.
- `colors.css` — brand palette, ramps, neutrals, status, semantic aliases.
- `typography.css` — families, weights, fluid scale, line-height, letter-spacing.
- `spacing.css` — 4px space scale + layout/container tokens.
- `effects.css` — radii, borders, shadows, motion.
- `base.css` — element resets + brand defaults + a few utility helpers.

**Foundation cards** (`guidelines/`) — Design System tab specimens (Type, Colors,
Spacing, Brand).

**Components** (`components/core/`) — reusable React primitives, each with a
sibling `.d.ts` (props), `.prompt.md` (usage) and a directory `@dsCard` preview.
Shipped: **Button** (`primary` / `accent` / `secondary` / `ghost` / `dark`, three
sizes). More primitives (Badge, Card, Input, Eyebrow, Tag) are queued.

**UI kit** (`ui_kits/website/`, planned) — marketing-website screens (home,
services, about, contact) composed from the components.

**Slides / decks** (`templates/mbs-deck/`) — **Make Bold Solutions Deck**: a
reusable 16:9 presentation template (Design Component) with title, content, stat,
2×2 grid, 3-card, and dark-closing layouts. Shipped populated with the live site's
10-slide Fractional CFO carousel, plus an editable PowerPoint export
(`MakeBoldSolutions-FractionalCFO.pptx`). Copy the folder and swap the slide
content to build future decks.

> Consuming projects seed new work from **templates** (`templates/<slug>/`), not
> from component starting points. Build a template per surface (e.g. a deck, a
> landing page) that showcases the components in context.

**Working scratch** (`_src/`) — imported originals (PDF, raw fonts, raw logos).
Not shipped; safe to ignore.

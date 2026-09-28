# Handoff: GitHubSpark — Make Bold Solutions / Make Bold Spark redesign

## Overview
A full visual redesign of the GitHubSpark dashboard (https://github-stats.makeboldspark.com, repo `MakeBoldSolutions/github-stats-spark`, app in `frontend/`). The functionality and data are unchanged: Overview, Insights, Health, repository detail, export, mobile tab bar, toasts, offline and error states. The look and feel moves from GitHub-blue to the **Make Bold Solutions design system**: rust and ember on cream, Be Vietnam Pro and Inter Tight, a warm ink neutral scale, outline icons, and no emoji.

## About the design files
Everything in `design/` is a **design reference built in HTML**. It is a working prototype of the intended look and behavior, not production code. The task is to **recreate it inside the existing React 19 + Vite app in `frontend/src`**, keeping the app's current architecture: hooks (`useRepositoryData`, `useTableSort`), services (`dataService`, `metricsCalculator`), CSS Modules, lazy loading, the service worker and offline cache. The data contract is unchanged (`repositories.json` schema 2.3.0).

To view the prototype: serve the `design/` folder with any static server (for example `npx serve design`) and open `GitHubSpark.dc.html`. It loads the real `docs/data/users/makeboldsolutions/repositories.json`.

The prototype has design-review switches (props on the root component). **These are not product features.**
- `heroVariant`: `cream` (default, recommended) or `rust` (a full-bleed rust hero)
- `cardLayout`: `grid` (default) or `list`
- `showHeatmap`: boolean
- `previewState`: `live` / `offline` / `update-available` / `toasts` / `empty` / `error` / `crash`. This forces each state for review.

## Fidelity
**High fidelity.** Colors, type, spacing, radii, copy and interactions are final. Recreate the UI pixel-for-pixel using CSS Modules and the tokens below.

---

## Step 1: Install the design system
1. Copy `design/_ds/make-bold-solutions-design-system-*/tokens/*.css` into `frontend/src/styles/brand/`. Copy `assets/fonts/*.ttf` into `frontend/public/fonts/`, and fix the `url()` paths in `fonts.css`.
2. Import the brand token files in `main.jsx` **before** `global.css`, in this order: `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `effects.css`, `base.css`.
3. Remap or replace the old variables in `global.css` (`--color-*`, `--spacing-*`, `--font-size-*`, `--border-radius`) with the brand tokens. Delete the GitHub-blue palette.
4. Port the four DS primitives in `ds-components/` (**Button, Badge, Card, Eyebrow**) into `frontend/src/components/Brand/`. They are plain React and use only the CSS variables. Use them everywhere the prototype does.
5. `index.html`: set `theme-color` to `#982407`. Replace `favicon.svg` and the og:image with `design/assets/logo-mark.svg` (a PNG export for og:image). Title stays `GitHubSpark — Make Bold Solutions Repository Portfolio`.
6. Remove `ThemeToggle` and dark mode for now. The brand has no approved dark palette yet. `ThemeContext` can stay as a no-op.

---

## Design tokens (from `tokens/*.css`)

**Brand colors**
| Token | Hex | Use |
|---|---|---|
| `--rust-500` (`--brand`) | `#982407` | Primary: headlines accent, active nav, primary buttons, focus of the brand |
| `--rust-600` | `#841e05` | Primary hover |
| `--rust-50` / `--rust-100` | `#fbeeea` / `#f4d2c8` | Row hover, subtle brand tint |
| `--rust-400` / `--rust-700` | `#b8431f` / `#6c1804` | Heatmap levels 3–4 |
| `--ember-500` (`--accent`) | `#c6620c` | Eyebrows, recent-activity bars, links on hover, focus ring |
| `--ember-100/300/400` | `#f9dabc` / `#e88f3d` / `#d97518` | Heatmap L1–L2, weekly bars, dark-surface accents |
| `--ink-900` | `#1e1e1e` | Text, footer, dark panels, toasts |
| `--ink-800/700/600/500/400/300/200/100/50` | `#2c2c2b` `#3d3d3b` `#56544f` `#76736c` `#9b988f` `#c2bfb6` `#ddd9d0` `#ece9e2` `#f4f2ec` | Neutral scale |
| `--cream` | `#f8f6f2` | Page background |
| `--white` | `#ffffff` | Cards |
| `--positive` / soft | `#2f6f4c` / `#e4efe7` | Healthy tier, quality "on" |
| `--caution` / soft | `#b8821a` / `#f6edd6` | Elevated tier, outdated dependency |
| `--critical` / soft | `#a8321a` / `#f6e2dc` | Critical tier, errors, missing README |
| `--info` / soft | `#2f5a8f` / `#e2e9f2` | Info badges |
| `--border-subtle/default/strong` | ink-100 / ink-200 / ink-300 | Hairlines |

**Language colors** replace GitHub's language colors, which clash with the brand. Use them for dots, bars and the language legend:
`C#` #982407 · `HTML` #c6620c · `TypeScript` #2f5a8f · `Python` #2f6f4c · `PowerShell` #56544f · `GDScript` #b8821a · `PHP` #d4715a · `JavaScript` #e88f3d · `CSS` #6c1804 · `Shell` #3d3d3b · fallback #9b988f.

**Health tiers → Badge tone:** critical → `critical`, elevated → `caution`, watch → `accent`, healthy → `positive`.

**Typography**
- Display: `"Be Vietnam Pro"` (weights 700/800). Body/UI: `"Inter Tight"` (400/500/600). Mono: `ui-monospace, SFMono-Regular, Menlo`.
- H1 hero: 800, `clamp(2.5rem, 4.5vw + 1rem, 4.25rem)`, line-height 1.04, letter-spacing -0.035em, `text-wrap: balance`.
- H2 page title (Insights/Health): 800, `clamp(2rem, 2.5vw + 1rem, 2.75rem)`, lh 1.08, ls -0.03em.
- H2 section ("The Spark catalog"): 800, `clamp(1.75rem, 2vw + 1rem, 2.25rem)`, ls -0.025em.
- Card/panel H3: 700, 19px. Drawer section H3: 700, 17px. Repo card name: 700, 19px, ls -0.015em.
- Big stat numbers: 800, 36–48px, lh 1, ls -0.03em.
- Eyebrow/label: 600, 11px, uppercase, letter-spacing 0.18em (table headers: 0.14em). Eyebrow component color is ember.
- Body: 15–18px, line-height 1.55. Meta text: 12–13px, `--text-muted` (#76736c).
- Wordmark sub-label "MAKE BOLD SPARK": 600, 10px, letter-spacing 0.3em.

**Radii:** 4px (badges, chips), 6px (inputs, buttons, small tiles), 8px (cards, panels, menus). No pills except 50% dots.
**Shadows:** cards use DS Card defaults. Menus use `0 10px 28px rgba(30,30,30,.14)`. Toasts use `0 10px 28px rgba(30,30,30,.28)`. The drawer uses `-12px 0 32px rgba(30,30,30,.18)`.
**Focus:** `box-shadow: 0 0 0 3px rgba(198,98,12,.18–.35)`, with an ember border on inputs.
**Motion:** 120ms color transitions. No bounce.
**Layout:** container max-width 1200px, side padding 24px. 4px spacing grid.

**Icons:** Lucide-style outline icons, 2px stroke, round caps, 15–22px, `currentColor`. Used: search, x, star, git-fork, git-commit, clock, external-link, github, refresh-cw, download, chevron up/down, wifi-off, layout-grid, bar-chart, alert-triangle, check, info. Install `lucide-react`. **Remove every emoji** in the current app: 📦💻⭐🍴 in ProfileHero, 🔥📄⚖️🔄🧪🔍 in RepositoryGrid, 🌐 in WebsiteSection, ⚠️ in ErrorBoundary, and the EmptyState default icon.

---

## Screens and views

### Global header (`App.jsx` header)
- Sticky, `rgba(248,246,242,.95)` with an 8px backdrop blur and a 1px `--border-default` bottom border. Inner container min-height 68px, flex space-between.
- Brand (link to `/`): `logo-mark.svg` at 30px tall, 12px gap, then a stack with 5px gap:
  - "GitHub" + "Spark" in Be Vietnam Pro 800, 19px, ls -0.02em. "Spark" is rust.
  - "MAKE BOLD SPARK" sub-label.
- **Replace the GitHub Octocat logo** with the peak mark.
- Nav (≥768px): Overview / Insights / Health as text buttons, 600 15px, 14px horizontal padding, full header height, 2px bottom border.
  - Active tab: rust text and a rust border.
  - Inactive: `--ink-700`, rust on hover.
- Hash routing is unchanged: `#` = Overview, `#visualizations` / `#insights` = Insights, `#attention` / `#health` = Health. Keep the old hashes working.
- **Offline banner** (`OfflineIndicator`) is rendered inside the header, below the nav row, when `navigator.onLine` is false.
  - Full-width `--ink-900` strip, 10px vertical padding, 14px text.
  - Left to right: a wifi-off icon in ember-300; **"Offline mode"** (600); then in ink-300 "Showing cached data · Last synced {relative}"; then a right-aligned outline "Try again" button (ink-600 border, ember on hover) that triggers a refetch.

### Overview (default view)
**Hero** (replaces `ProfileHero`). Grid `repeat(auto-fit, minmax(min(100%,380px),1fr))`, gap 48px, padding 64px 24px 48px.
- Left column (gap 20px):
  - Eyebrow "Open-source portfolio"
  - H1 "Built to scale, **in the open.**" (the second clause is rust)
  - Lead paragraph, 18px, ink-600, max 56ch: "Explore Make Bold Solutions' public GitHub repositories — an AI-powered analytics dashboard showcasing .NET, React, Python, and more."
  - Buttons: primary lg "View on GitHub" (opens github.com/MakeBoldSolutions) and secondary lg "Visit Make Bold Spark" (opens makeboldspark.com).
- Right column: DS `Card` with padding lg and `accent` (3px rust top rule).
  - Header row: "@MakeBoldSolutions" (display 700, 17px) and "Updated {Mon D, YYYY}" (12px muted).
  - A 2×2 stat grid with hairline row separators: Repositories / Commits / Stars / Forks from `profile.total_*`. Values: display 800, 40px. Labels: eyebrow style.
- The avatar image is removed.
- Alternate `rust` hero (optional): rust full-bleed panel, cream text, Eyebrow `onDark`, dark and accent buttons, and a 4-up stat row separated by `rgba(248,246,242,.3)` hairlines.

**Contribution heatmap** (`ContributionHeatmap`)
- DS Card, padding lg.
- Header: Eyebrow "Contribution activity" and a 20px display line "{total} contributions across {n} active days". On the right, a legend "Less ▢▢▢▢▢ More".
- 53 columns (weeks, Sunday start) × 7 cells. Cells are 11×11px with 2px radius and a 3px gap. Month labels (10px muted) sit above the first week of each month. The grid scrolls horizontally on narrow screens.
- Levels by count:
  - 0 → `--ink-100`
  - 1–3 → `--ember-100`
  - 4–10 → `--ember-300`
  - 11–20 → `--rust-400`
  - 21+ → `--rust-700`
- The window ends at `metadata.generated_at`. Each cell's title reads "{n} contributions on YYYY-MM-DD". Footnote: "Trailing 365 days".

**Repository catalog** (`RepositoryGrid`)
- Header: Eyebrow "Repositories" and H2 "The Spark catalog". On the right: "{n} repositories" or "{x} of {n} repositories".
- Toolbar (flex-wrap, gap 10px, all controls 44px tall, white, 1px border, 6px radius):
  - Search input with an icon (grows, min 280px), placeholder "Search repositories…", with a clear (x) button when it has a value.
  - Select "All languages".
  - Select "All health tiers". This **replaces the maturity filter** (`ai_summary` is null in the current data) and filters on `attention_metrics.tier`.
  - Select sort: Recent activity (default), Stars, Commits, Name (A–Z), Newest first.
  - A ghost "Clear filters" button when any filter is active.
  - A right-aligned **Export** button (download icon) opening the export menu.
- Grid: `repeat(auto-fill, minmax(min(100%,340px),1fr))`, gap 20px.
- **Repo card** (DS Card, `interactive`, padding none; inner padding 22px 22px 18px; flex column with 14px gap; equal heights). The whole card is a button that opens the detail drawer, with Enter/Space support and an ember focus ring.
  - Top row: repo name (display 700, 19px). If `homepage` is set, a 34×34 outline icon link to the live site on the right (rust tint on hover).
  - Meta row: a language chip (9px dot plus the name at 13px/500, ink-600), then a tier Badge. If pushed within 3 days, a brand Badge "Active this week" (replaces "🔥 Hot").
  - Excerpt: 14.5px, lh 1.55, ink-600, up to 150 characters. Source is `ai_summary.summary`, then `summary.text`, then `description`, **stripped of markdown**: remove badge images/links, including truncated fragments like `[![TypeScript](https`, bare URLs, brackets, and `* _ \` # > |`.
  - Quality chips (replace the emoji badges): README / License / CI/CD / Tests. Each is 12px/500 with 3px 8px padding, 4px radius, and a 6px dot.
    - On: `--positive-soft` background, `--positive` text and dot.
    - Off: `--ink-50` background, `--ink-400` text, `--ink-300` dot.
  - Footer (1px `--border-subtle` top border, 14px top padding, 13px ink-600): star count, fork count, commit count, and a right-aligned clock icon with relative time (Today / Yesterday / Nd / Nw / Nmo / Ny ago). The time is rust when pushed within 3 days.
- **Empty state:** 64px padding, 1px dashed `--border-strong` border, 8px radius, centered. Title "No repositories found" (display 700, 20px), then "Try adjusting your search or filters.", then a secondary sm "Clear filters" button.

### Insights (`DashboardView`, `StatCards`, charts)
- Page header: Eyebrow "Insights", H2 "Repository insights", and "Showing {n} repositories".
- **Stat cards:** 6 DS Cards (padding md) in a `repeat(auto-fit,minmax(170px,1fr))` grid. Each has a label (eyebrow style), a value (display 800, 36px) and a sub-line (13px).
  - Repositories: "{n} active in 30 days"
  - Total commits: "All-time"
  - Languages: "Primary languages"
  - README coverage: "{x}%" / "Repos with a README"
  - Open pull requests: value in **rust**, "{n} repos with open PRs"
  - Security alerts: value in critical if above 0, otherwise positive; "{n} repos with alerts"
- A two-column grid, `repeat(auto-fit,minmax(min(100%,460px),1fr))`:
  - **Total commits:** horizontal bars. Each row is a grid `140px 1fr 44px`. The track is 14px `--ink-50` with 2px radius. The fill is the language color. Values are tabular-nums. Rows are clickable and open the drawer.
  - Right column, stacked:
    - **Language distribution:** an 18px segmented bar (2px gaps) plus a legend grid (10px swatch, name, count).
    - **Commits, last 90 days:** the same bars with an ember fill; only repos with commits in that window.
- **Weekly activity timeline:** 52 columns in a 180px-tall area with a baseline border. Weeks with commits get ember-300 bars. The peak week is rust. Empty weeks get a 0.8% ink-100 stub. A tick label appears every 8th week. The header shows "Peak week: {label} · {n} commits".
- **Quality coverage matrix:** a table with repository rows × README / License / CI/CD / Tests / Docs columns. Cells are 14px squares: filled positive when true, a 1px ink-300 outline when false. Rows are clickable.
- Chart.js can stay for the bar and scatter charts if preferred. Restyle them with these colors, the Inter Tight font, ink-200 gridlines and no legends. The HTML-bar versions in the prototype are the visual target.

### Health (`AttentionView`)
- Header: Eyebrow "Health", H2 "Repositories needing attention", and the sub-line "Ranked by pull request pressure, security findings, staleness, and dependency health".
- **Summary tiles** (4, grid min 200px, 22px padding, 8px radius):
  - "Need attention" is a **solid rust tile** with cream text (value) and rust-100 text (label).
  - "Critical" / "Security backlog" / "Stale 90+ days" are white with a 1px border. The Critical value is shown in critical red when above 0.
  - Values: display 800, 44px.
- **Use the backend's `attention_score`, `attention_metrics.tier` and `attention_metrics.components`.** Stop using the client-side `computeAttentionScore()` so the dashboard matches the pipeline.
- Layout: flex-wrap with gap 20px. The table card is `flex: 2 1 620px` and the aside is `flex: 1 1 300px`, so they stack on narrow screens.
- **Maintenance ranking table** (DS Card, padding none):
  - Header: "Maintenance ranking" and "Higher scores indicate greater need for maintainer attention.", with an Export button on the right.
  - Columns: # / Repository (name 600 plus language 12px muted) / Tier (Badge) / Score / PRs / Alerts / Stale (days) / README.
    - Score is a 48×6px bar plus the value. The bar color is critical at ≥60, caution at ≥30, otherwise positive.
    - README "No" is shown in critical.
  - The header row has a cream background. Header labels are uppercase 11px with 0.14em spacing. The active sort column is rust with a ↑/↓ arrow. Clicking a column toggles desc/asc.
  - Rows get a rust-50 background on hover and open the drawer on click. The table wrapper scrolls horizontally, with a table min-width of 640px.
- **Methodology aside:** `--ink-900` panel, 28px padding.
  - Eyebrow `onDark` "Methodology", then H3 "What drives the score" (cream, 22px).
  - One row per score component: Pull requests / Security findings / Staleness / Dependency health. Each shows "{hit} of {n} repos" and a 4px ember-400 bar with the average component score.
  - Footnote: "Bars show average component score across the portfolio. Tiers: Healthy, Watch, Elevated, Critical."

### Repository detail drawer (`RepositoryDetail`)
Replaces the centered modal with a **right-side drawer**.
- Backdrop `rgba(30,30,30,.5)`. Panel `width: min(680px,100%)`, full height, cream background, flex column.
- Header (white, 3px rust top border, 1px bottom border):
  - Eyebrow "Repository {i} of {n}", name (display 800, 30px) and a 38×38 close button.
  - Meta row: language dot, tier Badge, "Attention score {x.x}".
  - Actions: a solid rust "Repository" link (github icon) and, when there's a homepage, an outline "Live site" link.
- Scrolling body (24px 28px padding, 24px gap):
  1. **Stats:** a 3×2 grid of white tiles with 1px dividers: Stars, Forks, Commits, Last 90 days, Last push, Age.
  2. **Summary:** cleaned markdown text, 15px, lh 1.65, up to 900 characters. Rendering it as real markdown with `MarkdownContent` is fine, styled with brand type.
  3. **Quality:** 5 tiles (README, License, CI/CD, Tests, Docs), using the same on/off colors as the card chips.
  4. **Attention breakdown:** one row per component, `150px 1fr 40px`, with an 8px bar colored by score threshold.
  5. **Fix score prompt** (`FixScorePromptSection`), collapsible.
     - An `--ink-900` panel. Its header shows "Fix score prompt" with `/devspark.fix-score` below in mono ember-300, a Badge ("{n} signals" caution, or "Ready" positive) and a chevron.
     - When expanded: a list of blockers. Each blocker has a severity Badge (high → critical, medium → caution, external → info, low → positive), a label in 600 and detail text in ink-300.
     - Then a read-only mono textarea (ink-800 background, 180px tall) holding the prompt, and an accent sm "Copy prompt" button that shows "Copied" for 1.8s.
     - **Keep the existing `getFixScoreBlockers` / `buildPrompt` logic as-is.** Restyle only.
  6. **Signals:** a key/value list: Open pull requests, Oldest open PR, Security state, Open security alerts, Recent workflow runs ("{s} passed · {f} failed"), Created.
  7. **Dependencies** (if `tech_stack.dependencies` is present): the header shows "{outdated} of {total} outdated". Rows show the name, then `current → latest` in mono, then a status Badge (current → positive, major → critical, other outdated → caution). Outdated rows come first, top 10.
  8. **Website preview** (`WebsiteSection`): not shown in the prototype because the current data has no screenshots. When present, show a 16:10 image in an 8px-radius frame with a 1px border, and a caption "Captured {date} · Audit: {status}" in 12px muted.
- Footer (white, 1px top border): secondary sm "Previous" and "Next" buttons, disabled at the ends, with centered help text "Arrow keys to navigate · Esc to close".
- Keyboard: Esc closes; ← and → move through the list. On Overview the list order follows the current filter and sort.

### Footer
- `--ink-900` background, 48px 24px 40px padding.
- Left: the "GitHubSpark" wordmark (cream, with "Spark" in ember-400, 24px/800), "MAKE BOLD SPARK" (ink-400), and "Built by Mark Hazleton · Make Bold Solutions · Make Bold Spark" with cream links that turn ember-300 on hover.
- Right: "Data: {generated_at locale string}" (ink-400) and an outline **Refresh** button (refresh icon, "Refresh" or "Refreshing…"). It keeps the existing `clearCache()` + `refetch({forceRefresh:true})` behavior.
- Bottom bar (1px ink-800 top border, 12px ink-500): "github-stats.makeboldspark.com" and "Wichita, Kansas".

### Mobile tab bar (`TabBar`, <768px)
- The top nav is hidden. A bottom bar is fixed with a white background, a 1px top border, `env(safe-area-inset-bottom)` padding and a 3-column grid.
- Each tab has a 22px icon over a 12px/600 label with min-height 64px: Overview (layout-grid), Insights (bar-chart), Health (alert-triangle). Rename the "Attention" label to "Health" to match the top nav.
- The active tab is rust with a 2px rust top border. Inactive tabs are ink-500.
- `main` gets 72px of bottom padding.

### Toasts (`Toast`, `ToastContainer`)
- Fixed and centered, bottom 28px (88px above the tab bar on mobile), width `min(440px, 100% - 32px)`, stacked with an 8px gap.
- Each toast: `--ink-900` background, cream 14px text, 8px radius, padding 12px 12px 12px 14px.
- Content: a 26px round icon badge filled with the variant color and a cream 2.5px-stroke icon.
  - success = positive + check
  - error = critical + x
  - warning = caution + alert-triangle
  - info = ember + info
- Then the message and an optional action button (ember fill, "Update" for the service-worker toast, which stays until dismissed), then an x close button.
- Copy: "Data refreshed successfully", "Data refreshed and cache cleared", "Refresh failed. Check the console for details.", "A new version is available." + [Update], "No data to export", "Exported {n} repositories as CSV/JSON".

### Export menu (`ExportButton`)
- Trigger: an outline button with a download icon and "Export". The ▼ glyph is dropped.
- Menu: absolute and right-aligned, 260px, white, 1px border, 8px radius, a menu shadow and 6px padding.
- Contents: a count line (12px muted) such as "{n} repositories in current view", then two menu items with a rust-50 hover:
  - "Export as CSV" / "Spreadsheet-ready summary columns"
  - "Export as JSON" / "Full repository records"
- Click outside to close. Export uses the currently filtered list (Overview) or the ranked list (Health). **Keep the existing CSV column set**. Replace the `alert()` calls with toasts.

### Loading, load error and crash
- **Loading:** centered peak mark (44px) and "Loading repository data…" in 15px muted, with 120px vertical padding.
- **Data load error:** a DS Card (accent) with "Error loading data", the message, and a primary "Retry" button.
- **Crash** (`ErrorBoundary`): left-aligned, max 640px, 96px top padding.
  - Peak mark 40px, then Eyebrow "Unexpected error", then H1 "Something went wrong." (display 800).
  - Body: "We're sorry for the inconvenience. The application encountered an unexpected error."
  - Buttons: primary "Try again" and secondary "Reload page".
  - Help line above a hairline: "If the problem persists, please try clearing your browser cache or contact support."
  - Keep the 30s auto-retry and the dev-only error details.

---

## State (additions and changes)
- `view`: overview / insights / health, synced with the hash (as today).
- Overview filters: `search`, `lang`, `tier` (new, replaces maturity) and `sort` (default `activity`).
- Health sort: `{ key, dir }`, default score desc.
- `selectedRepo` for the drawer, with prev/next over the current list.
- `toasts[]` holding `{ id, message, variant, duration, action? }`.
- `exportOpen`: which export menu is open, or none.
- `fixOpen`, `copied` for the fix score prompt section.
- Viewport width below 768 means mobile. Reuse `ViewportContext`.
- Online/offline status and last-sync time (reuse `OfflineCacheContext`).

## Assets
- `design/assets/logo-mark.svg`: the brand peak mark (rust + ink). Use it for the header, favicon, loading and crash screens. Don't recolor it.
- `design/assets/logo-mark-wordmark.svg`: the full Make Bold lockup, for use where needed.
- Fonts: Be Vietnam Pro (static 400–900) and Inter Tight (variable) in `design/_ds/.../assets/fonts/`.
- Icons: Lucide (`lucide-react`), outline style.

## Files
- `design/GitHubSpark.dc.html`: the full prototype. Its template is HTML with inline styles (exact values), and its logic class sits at the bottom of the file. The data shaping, markdown cleaning, heatmap build and export logic are all there.
- `design/_ds/…`: the Make Bold Solutions tokens (`tokens/*.css`), fonts and component bundle.
- `design/docs/data/users/makeboldsolutions/repositories.json`: a data snapshot used by the prototype.
- `ds-components/`: React source and type definitions for Button, Badge, Card and Eyebrow, to port into the app.
- Mapping to the repo (`frontend/src/components/...`):
  - Header, footer, routing → `App.jsx`
  - Hero → `ProfileHero/`
  - Heatmap → `Visualizations/ContributionHeatmap.jsx`
  - Catalog → `RepositoryGrid/`
  - Insights → `Visualizations/DashboardView.jsx`, `StatCards.jsx`, `HealthChart.jsx`, `BarChart.jsx`, `PieChart.jsx`, `ActivityTimeline.jsx`
  - Health → `Attention/AttentionView.jsx`
  - Drawer → `DrillDown/RepositoryDetail.jsx` + `sections/*`
  - Export → `Common/ExportButton.jsx`
  - Tab bar → `Mobile/TabBar/`
  - Toasts → `Mobile/Toast/`
  - Offline banner → `Mobile/OfflineIndicator/`
  - Empty state → `Mobile/EmptyState/`
  - Crash screen → `ErrorBoundary/`
  - Theme toggle → `Common/ThemeToggle.jsx` (remove)

## Suggested prompt for Claude Code
> Read `design_handoff_githubspark_redesign/README.md` and open `design/GitHubSpark.dc.html` as the visual reference. On a new branch `feat/mbs-brand-redesign`, install the brand tokens and fonts, port the DS primitives, then restyle each component listed under "Files" to match. Keep all existing data, hooks, service worker and tests working. Update tests that assert on removed emoji or old copy. Run `npm run lint`, `npm test` and `npm run build`.

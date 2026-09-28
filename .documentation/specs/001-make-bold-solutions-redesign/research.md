# Research: Make Bold Solutions Dashboard Redesign

## Decision 1: Package And Serve The Brand System Locally

**Decision**: Copy the supplied token styles, font files, and logo assets into the frontend source and public-asset locations; load the brand layers before global styles.

**Rationale**: The handoff defines exact assets and typography. Local serving keeps the dashboard usable offline and avoids a new runtime dependency.

**Alternatives considered**:

- Load fonts or tokens from a third-party CDN: rejected because it weakens offline behavior and makes visual output dependent on another service.
- Recreate fonts, colors, and primitives manually: rejected because the handoff provides approved source assets and exact token definitions.

## Decision 2: Use Lucide For Product Iconography

**Decision**: Add `lucide-react` and replace custom inline symbols and all emoji UI with approved outline icons.

**Rationale**: A single icon family provides consistent stroke, sizing, accessible labels, and the icon set named by the handoff.

**Alternatives considered**:

- Preserve scattered inline SVG markup: rejected because it duplicates styling and does not address the required emoji removal.
- Draw a new icon set: rejected because it introduces unnecessary custom visual code.

## Decision 3: Lift Active Result-List Ownership To The App Shell

**Decision**: The app shell owns the selected repository and the ordered active list; each view exposes its filtered or ranked list when opening detail.

**Rationale**: Drawer navigation must follow the current Overview filters or Health ranking. The current Overview and Health views each derive lists internally, while the app shell currently navigates a separate sorted list.

**Alternatives considered**:

- Keep navigation derived only in the app shell: rejected because it would diverge from view-specific filters and sorting.
- Keep navigation inside each view: rejected because the detail drawer is composed by the app shell and would require duplicated keyboard and lifecycle behavior.

## Decision 4: Preserve The Data Contract And Trust Pipeline Attention Metrics

**Decision**: Consume `attention_score`, `attention_metrics.tier`, and `attention_metrics.components` as read-only source fields; render neutral unavailable states if an older record lacks a field.

**Rationale**: The pipeline is the source of truth. Recomputing a score in the browser causes display discrepancies and violates the specification.

**Alternatives considered**:

- Continue the local scoring function: rejected because it produces conflicting scores.
- Add a fallback score formula: rejected because it recreates the same disagreement; unavailable source data should be explicit.

## Decision 5: Preserve Existing Dependencies And Use CSS-Led Charts Where The Handoff Is Specific

**Decision**: Retain existing chart dependencies where they meet the visual target, while implementing the handoff's bar, timeline, and matrix treatments as semantic HTML and CSS when their prescribed layout is more direct.

**Rationale**: This limits new dependencies and supports exact interaction, responsive scrolling, and keyboard activation for repository rows.

**Alternatives considered**:

- Replace all charts: rejected because existing lazy-loaded charts and their data shaping remain useful.
- Force every visualization into a canvas chart: rejected because the handoff's matrix and bars require richer semantic interaction.

## Decision 6: Use A Side Drawer Without Changing Detail Data Semantics

**Decision**: Reuse repository-detail hooks and section data logic, changing presentation and focus behavior from a centered modal to a right-side drawer.

**Rationale**: The existing detail content and fix-score prompt are already functional; the redesign is a presentation and navigation change, not a data-model replacement.

**Alternatives considered**:

- Build a second detail screen: rejected because it duplicates existing detail behavior.
- Keep the centered modal: rejected because it does not meet the approved experience.

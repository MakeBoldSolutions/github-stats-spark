# UI Contract: Make Bold Solutions Dashboard Redesign

## Application Shell

| Consumer                  | Input                                                         | Output/Behavior                                                               |
| ------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Header and mobile tab bar | Current view                                                  | Navigate Overview, Insights, and Health while accepting legacy hashes.        |
| View components           | Repository collection and callbacks                           | Report selected repository plus the ordered active result list.               |
| Repository drawer         | Selected repository, active result list, navigation callbacks | Close on Escape; move with left/right keys and enabled Previous/Next actions. |
| Offline banner            | Online state, last sync, retry callback                       | Show only while offline and retry existing refetch behavior.                  |
| Toast container           | Toast collection and dismissal/action callbacks               | Render status feedback above mobile navigation.                               |

## Brand Primitives

| Primitive | Contract                                                                                                    |
| --------- | ----------------------------------------------------------------------------------------------------------- |
| Button    | Supports primary, secondary, accent, ghost, and icon-only treatments with visible focus and disabled state. |
| Badge     | Supports positive, caution, critical, info, accent, and neutral presentations.                              |
| Card      | Supports prescribed padding, accent rule, and interactive focus treatment without nesting card surfaces.    |
| Eyebrow   | Supports normal and dark-surface text treatment.                                                            |

## Repository Views

| View             | Source                                       | User-visible Contract                                                                                        |
| ---------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Overview catalog | Filtered and sorted repositories             | Supports search, language, health tier, sort, clear, export, empty state, and card activation.               |
| Insights         | Repository collection and profile totals     | Exposes six summary values, clickable repository activity views, timeline, distribution, and quality matrix. |
| Health           | Source attention fields and quality metadata | Displays a sortable maintenance ranking and methodology without deriving a new score.                        |
| Detail drawer    | One repository and active result list        | Displays available details in the specified sequence without changing source data.                           |

## Compatibility Rules

- The export contract remains current CSV fields and complete JSON records; it accepts the active Overview list or Health ranking.
- Existing public-only filtering, browser cache, service-worker update notifications, retry behavior, and prompt-generation logic are preserved.
- At widths below 768px, the tab bar replaces top navigation and all horizontally dense content remains scrollable and reachable.

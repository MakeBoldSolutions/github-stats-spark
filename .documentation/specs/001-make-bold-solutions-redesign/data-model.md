# Data Model: Make Bold Solutions Dashboard Redesign

## Contract Boundary

`repositories.json` remains unchanged. The redesign adds browser-only presentation state and derives display values without writing data back to cache or source artifacts.

## Source Entities

### Portfolio Data

| Field Group             | Required Use                                                  |
| ----------------------- | ------------------------------------------------------------- |
| `profile.total_*`       | Overview portfolio-stat card and Insights summary values.     |
| `repositories[]`        | Catalog, Insights, Health, drawer, and export source records. |
| `metadata.generated_at` | Update label, footer source timestamp, and heatmap end date.  |
| `activity_calendar`     | Trailing 365-day contribution heatmap.                        |

### Repository

| Field Group        | Required Use                                                                                                    |
| ------------------ | --------------------------------------------------------------------------------------------------------------- |
| Identity and links | Name, GitHub URL, homepage, language, topics, and creation/push dates.                                          |
| Activity           | Total commits, recent commits, relative push time, and commit history.                                          |
| Quality            | README, license, CI/CD, tests, documentation, dependencies, and website audit.                                  |
| Health             | `attention_score`, `attention_metrics.tier`, and `attention_metrics.components`; all are display source fields. |
| Descriptive text   | AI summary, summary text, or description in that precedence order after display sanitization.                   |

## Presentation State

| Entity              | Fields                                          | Rules                                                                           |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------- |
| View state          | `overview`, `insights`, `health`                | Derived from existing and backward-compatible hash routes.                      |
| Catalog filters     | Search text, language, tier, sort               | Operate on public repository records only; no mutation.                         |
| Health sort         | Key and direction                               | Defaults to source attention score descending.                                  |
| Active result list  | Ordered repositories and source view            | Becomes the drawer's previous/next sequence.                                    |
| Selected repository | Repository identity or record                   | Cleared on drawer close.                                                        |
| Export state        | Open menu identity                              | Closes on outside interaction or after an export selection.                     |
| Toast               | ID, message, variant, duration, optional action | Persistent service-worker update messages require explicit dismissal or action. |
| Fix prompt state    | Expanded and copied flags                       | Does not change prompt generation or blocker rules.                             |

## Derived Values And Validation

- Summary excerpt removes markdown links, badges, URLs, bracket fragments, and markdown punctuation before truncation.
- Health tier presentation maps `critical`, `elevated`, `watch`, and `healthy` to the approved badge tones; an unknown tier receives a neutral accessible fallback.
- Relative push labels use the supplied day, week, month, and year wording, with a safe unavailable fallback for missing or invalid dates.
- Heatmap uses 365 days ending at `metadata.generated_at`; no future date or missing calendar may produce invalid cells.
- Dependency lists display at most ten entries, with outdated entries first.

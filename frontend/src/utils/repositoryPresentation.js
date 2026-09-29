/**
 * Pure display helpers for the Make Bold Solutions dashboard redesign.
 * These functions only format/derive presentation values from the existing
 * repositories.json data contract; they never mutate or refetch data.
 */

const LANGUAGE_COLORS = {
  "C#": "#982407",
  HTML: "#c6620c",
  TypeScript: "#2f5a8f",
  Python: "#2f6f4c",
  PowerShell: "#56544f",
  GDScript: "#b8821a",
  PHP: "#d4715a",
  JavaScript: "#e88f3d",
  CSS: "#6c1804",
  Shell: "#3d3d3b",
};

const LANGUAGE_COLOR_FALLBACK = "#9b988f";

/** Approved outline-icon color for a repository's primary language. */
export function getLanguageColor(language) {
  return LANGUAGE_COLORS[language] || LANGUAGE_COLOR_FALLBACK;
}

const TIER_TONE = {
  critical: "critical",
  elevated: "caution",
  watch: "accent",
  healthy: "positive",
};

/** Maps a source `attention_metrics.tier` value to an approved Badge tone. */
export function getTierTone(tier) {
  return TIER_TONE[tier] || "neutral";
}

const TIER_LABEL = {
  critical: "Critical",
  elevated: "Elevated",
  watch: "Watch",
  healthy: "Healthy",
};

/** Human-readable label for a source `attention_metrics.tier` value. */
export function getTierLabel(tier) {
  return TIER_LABEL[tier] || "Unknown";
}

/**
 * Strips markdown links/images, badge syntax, bare URLs, bracket fragments,
 * and stray markdown punctuation from a text excerpt before display.
 */
export function sanitizeSummaryText(text) {
  if (!text || typeof text !== "string") return "";

  let clean = text;

  // Markdown images/links: ![alt](url) or [text](url) -> keep visible text only
  clean = clean.replace(/!\[([^\]]*)\]\([^)]*\)/g, "");
  clean = clean.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");

  // Reference-style badges/shields left as bracket fragments: [text][ref]
  clean = clean.replace(/\[([^\]]*)\]\[[^\]]*\]/g, "$1");

  // Bare URLs
  clean = clean.replace(/https?:\/\/\S+/g, "");

  // Leftover bracket fragments
  clean = clean.replace(/\[[^\]]*\]/g, "");

  // Markdown emphasis/heading/punctuation
  clean = clean.replace(/[*_`#>]+/g, "");

  // Collapse whitespace
  clean = clean.replace(/\s+/g, " ").trim();

  return clean;
}

const SUMMARY_EXCERPT_LENGTH = 140;

/**
 * Selects a repository's summary text using the approved precedence
 * (ai_summary.summary -> summary.text -> description), sanitizes it, and
 * truncates it to the approved excerpt length.
 */
export function getRepositorySummaryExcerpt(
  repo,
  maxLength = SUMMARY_EXCERPT_LENGTH,
) {
  const raw =
    repo?.ai_summary?.summary || repo?.summary?.text || repo?.description || "";
  const clean = sanitizeSummaryText(raw);

  if (!clean) return "";
  if (clean.length <= maxLength) return clean;
  return `${clean.slice(0, maxLength - 1).trimEnd()}…`;
}

/**
 * Formats "days since last push" as a relative-time label with a safe
 * fallback for missing or invalid values.
 */
export function getRelativePushLabel(daysSincePush) {
  if (
    daysSincePush === null ||
    daysSincePush === undefined ||
    Number.isNaN(daysSincePush)
  ) {
    return "Unknown";
  }

  const days = Number(daysSincePush);
  if (!Number.isFinite(days) || days < 0) return "Unknown";

  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return `${days}d ago`;
  if (days <= 30) return `${Math.round(days / 7)}w ago`;
  if (days <= 365) return `${Math.round(days / 30)}mo ago`;
  return `${Math.round(days / 365)}y ago`;
}

/**
 * Formats an ISO timestamp (e.g. metadata.generated_at) as a short display
 * date, with a safe fallback for missing or invalid values.
 */
export function formatSourceDate(timestamp) {
  if (!timestamp) return "Unknown";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Returns the source-derived health tone/label pair for a repository,
 * falling back to a neutral, accessible value when metrics are absent.
 */
export function getRepositoryHealthPresentation(repo) {
  const tier = repo?.attention_metrics?.tier;
  return {
    tier: tier || null,
    tone: getTierTone(tier),
    label: getTierLabel(tier),
    score:
      typeof repo?.attention_score === "number" ? repo.attention_score : null,
  };
}

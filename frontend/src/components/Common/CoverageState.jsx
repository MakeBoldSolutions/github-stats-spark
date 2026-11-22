import PropTypes from "prop-types";
import { Badge } from "@/components/Brand";
import styles from "./DataViews.module.css";

/**
 * The states a collector reports for one subject (a repository, a site).
 * Zero is a real reading; every other non-"count" state means the number
 * is missing or incomplete and must never be read as zero.
 */
export const COVERAGE_STATES = {
  count: { label: (n) => `${n} open`, tone: "caution" },
  zero: { label: () => "None open", tone: "positive" },
  partial: { label: () => "Only partly read", tone: "caution" },
  stale: { label: () => "Out of date", tone: "caution" },
  unavailable: { label: () => "Not available", tone: "caution" },
  unauthorized: { label: () => "No access", tone: "critical" },
  unsupported: { label: () => "Not enabled", tone: "neutral" },
  not_checked: { label: () => "Not checked yet", tone: "neutral" },
};

/** Collector status values, mapped to a coverage state. */
const STATUS_STATE = {
  available: "count",
  partial: "partial",
  unavailable: "unavailable",
  unauthorized: "unauthorized",
  disabled: "unsupported",
  unsupported: "unsupported",
  not_checked: "not_checked",
};

/**
 * Pure: which state to show for a reading. A successful reading older than
 * `staleAfterSeconds` (when given) is stale.
 */
export function coverageStateOf({
  status,
  count,
  checkedAt,
  staleAfterSeconds,
  now = Date.now(),
}) {
  const state = STATUS_STATE[status] || "unavailable";
  if (state === "count" || state === "partial") {
    const checked = checkedAt ? Date.parse(checkedAt) : NaN;
    if (
      staleAfterSeconds &&
      Number.isFinite(checked) &&
      now - checked > staleAfterSeconds * 1000
    ) {
      return "stale";
    }
  }
  if (state === "count") return count ? "count" : "zero";
  return state;
}

/**
 * Shows a collector reading so that zero, unavailable, unauthorized,
 * unsupported and stale all look different. `reason` is the plain-language
 * explanation shown beside a missing reading.
 */
export default function CoverageState({
  status,
  count = 0,
  checkedAt = null,
  staleAfterSeconds = null,
  reason = "",
}) {
  const state = coverageStateOf({
    status,
    count,
    checkedAt,
    staleAfterSeconds,
  });
  const { label, tone } = COVERAGE_STATES[state];
  const showReason = reason && state !== "count" && state !== "zero";
  return (
    <span className={styles.coverage} data-coverage={state}>
      <Badge tone={tone}>{label(count)}</Badge>
      {showReason && <span className={styles.coverageReason}>{reason}</span>}
    </span>
  );
}

CoverageState.propTypes = {
  status: PropTypes.string.isRequired,
  count: PropTypes.number,
  checkedAt: PropTypes.string,
  staleAfterSeconds: PropTypes.number,
  reason: PropTypes.string,
};

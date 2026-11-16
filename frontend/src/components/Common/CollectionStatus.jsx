import PropTypes from "prop-types";
import useCollectionStatus from "@/hooks/useCollectionStatus";
import styles from "./CollectionStatus.module.css";

export function formatAge(timestamp, now = Date.now()) {
  if (!timestamp) return null;
  const diff = now - new Date(timestamp).getTime();
  if (Number.isNaN(diff)) return null;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

/** Summarise a status.json payload as { tone, label, detail }. */
export function summarize(status, now = Date.now()) {
  const attempt = status.last_attempt;
  const ago = formatAge(status.last_success_at, now);
  const intervalMs = (status.interval_seconds || 0) * 1000;
  const stale =
    status.last_success_at &&
    intervalMs &&
    now - new Date(status.last_success_at).getTime() > intervalMs * 2;

  if (status.state === "running") {
    return {
      tone: "info",
      label: "Refreshing data",
      detail: ago ? `Last updated ${ago}` : "First collection in progress",
    };
  }
  if (!attempt) {
    return {
      tone: "warn",
      label: "No data collected yet",
      detail: "Waiting for the first collection run",
    };
  }
  const reason = attempt.reason ? ` — ${attempt.reason}` : "";
  if (attempt.outcome === "failed") {
    return {
      tone: "error",
      label: "Last refresh failed",
      detail: `${ago ? `Showing data from ${ago}` : "No successful refresh yet"}${reason}`,
    };
  }
  if (attempt.outcome === "skipped") {
    return {
      tone: "warn",
      label: "Refresh paused",
      detail: `${ago ? `Data from ${ago}` : "No data yet"}${reason}`,
    };
  }
  if (attempt.outcome === "partial") {
    return {
      tone: "warn",
      label: "Refreshed with errors",
      detail: `Updated ${ago}${reason}`,
    };
  }
  if (stale) {
    return {
      tone: "warn",
      label: "Data may be stale",
      detail: `Last successful refresh ${ago}`,
    };
  }
  return {
    tone: "ok",
    label: "Data up to date",
    detail: `Updated ${ago}`,
  };
}

const ICONS = { ok: "✓", info: "↻", warn: "!", error: "✕" };

export function CollectionStatusView({ status, now }) {
  const { tone, label, detail } = summarize(status, now);
  return (
    <div
      className={`${styles.bar} ${styles[tone]}`}
      role="status"
      aria-live="polite"
      data-testid="collection-status"
    >
      <span className={styles.icon} aria-hidden="true">
        {ICONS[tone]}
      </span>
      <span className={styles.label}>{label}</span>
      <span className={styles.detail}>{detail}</span>
    </div>
  );
}

CollectionStatusView.propTypes = {
  status: PropTypes.object.isRequired,
  now: PropTypes.number,
};

export default function CollectionStatus() {
  const status = useCollectionStatus();
  if (!status) return null;
  return <CollectionStatusView status={status} />;
}

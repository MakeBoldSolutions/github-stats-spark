import PropTypes from "prop-types";
import { Eyebrow } from "@/components/Brand";
import styles from "./DataViews.module.css";

const formatTime = (value) => {
  const parsed = value ? new Date(value) : null;
  return parsed && !Number.isNaN(parsed.getTime())
    ? parsed.toLocaleString()
    : "not yet";
};

/**
 * The heading every section starts with: eyebrow, title and an optional
 * status line. In the self-hosted deployment it also names the scope being
 * shown and how fresh each kind of data is. Without `scope` or `freshness`
 * it renders exactly the original markup, so the public dashboard is
 * unchanged.
 */
export default function PageHeader({
  eyebrow,
  title,
  titleId,
  description = null,
  scope = null,
  freshness = [],
}) {
  return (
    <div className="mb-lg">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 id={titleId}>{title}</h2>
      {description && (
        <p className="text-muted" role="status" aria-live="polite">
          {description}
        </p>
      )}
      {(scope || freshness.length > 0) && (
        <p className={styles.headerMeta}>
          {scope && <span>Showing: {scope}</span>}
          {freshness.map((item) => (
            <span key={item.label}>
              {item.label} updated {formatTime(item.at)}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

PageHeader.propTypes = {
  eyebrow: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  titleId: PropTypes.string.isRequired,
  description: PropTypes.node,
  scope: PropTypes.string,
  freshness: PropTypes.arrayOf(
    PropTypes.shape({ label: PropTypes.string, at: PropTypes.string }),
  ),
};

import styles from "../../RepositoryDetail.module.css";
import CollapsibleSection from "../CollapsibleSection";

function RepositoryInfoSection({
  repository,
  expanded,
  onToggle,
  formatDate,
  formatRelativeDate,
  formatNumber,
}) {
  return (
    <CollapsibleSection
      section="info"
      title="Repository Info"
      expanded={expanded}
      onToggle={onToggle}
    >
      <dl className={styles.detailList}>
        <div className={styles.detailItem}>
          <dt>Language</dt>
          <dd>
            <span className={styles.badge}>
              {repository.language || "Unknown"}
            </span>
          </dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Created</dt>
          <dd>{formatDate(repository.created_at)}</dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Last Updated</dt>
          <dd>{formatDate(repository.updated_at)}</dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Last Push</dt>
          <dd>
            {formatDate(repository.pushed_at)}
            {repository.days_since_last_push != null && (
              <span className={styles.textMuted}>
                {" "}
                ({formatRelativeDate(repository.days_since_last_push)})
              </span>
            )}
          </dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Age</dt>
          <dd>{repository.age_days ? `${repository.age_days} days` : "N/A"}</dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Size</dt>
          <dd>
            {repository.size_kb
              ? `${formatNumber(repository.size_kb)} KB`
              : "N/A"}
          </dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Watchers</dt>
          <dd>{formatNumber(repository.watchers ?? 0)}</dd>
        </div>
        <div className={styles.detailItem}>
          <dt>Repository URL</dt>
          <dd>
            <a
              href={repository.url}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.link}
            >
              View on GitHub →
            </a>
          </dd>
        </div>
        {repository.homepage && (
          <div className={styles.detailItem}>
            <dt>Homepage</dt>
            <dd>
              <a
                href={repository.homepage}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                Visit Site →
              </a>
            </dd>
          </div>
        )}
        {repository.has_pages &&
          !repository.homepage &&
          repository.pages_url && (
            <div className={styles.detailItem}>
              <dt>GitHub Pages</dt>
              <dd>
                <a
                  href={repository.pages_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.link}
                >
                  View Site →
                </a>
              </dd>
            </div>
          )}
        {repository.homepage_status != null && (
          <div className={styles.detailItem}>
            <dt>Homepage Status</dt>
            <dd>
              <span
                style={{
                  color:
                    repository.homepage_status >= 200 &&
                    repository.homepage_status < 300
                      ? "#16a34a"
                      : "#dc2626",
                  fontWeight: 600,
                }}
              >
                HTTP {repository.homepage_status}
              </span>
              {repository.homepage_response_ms != null && (
                <span className={styles.textMuted}>
                  {" "}
                  ({repository.homepage_response_ms}ms)
                </span>
              )}
            </dd>
          </div>
        )}
      </dl>
    </CollapsibleSection>
  );
}

export default RepositoryInfoSection;

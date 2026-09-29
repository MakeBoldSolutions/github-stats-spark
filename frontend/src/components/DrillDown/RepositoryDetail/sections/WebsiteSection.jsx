import styles from "../../RepositoryDetail.module.css";
import CollapsibleSection from "../CollapsibleSection";

function WebsiteSection({
  repository,
  expanded,
  onToggle,
  formatDate,
  getScreenshotUrl,
  screenshotAudit,
}) {
  if (!repository.screenshot) return null;

  return (
    <CollapsibleSection
      section="website"
      title="Website Preview"
      expanded={expanded}
      onToggle={onToggle}
    >
      <div className={styles.sectionContent}>
        <div className={styles.screenshotContainer}>
          <a
            href={repository.website_url || repository.screenshot.url}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.screenshotLink}
          >
            <img
              src={getScreenshotUrl(repository.screenshot.path)}
              alt={`Screenshot of ${repository.name} website`}
              className={styles.screenshot}
              loading="lazy"
            />
            <div className={styles.screenshotOverlay}>
              <span>Visit Website →</span>
            </div>
          </a>
        </div>
        <div className={styles.screenshotMeta}>
          <span className={styles.textMuted}>
            Captured {formatDate(repository.screenshot.captured_at)}
            {repository.screenshot.file_size_kb && (
              <> • {repository.screenshot.file_size_kb.toFixed(1)} KB</>
            )}
          </span>
          {screenshotAudit?.status && (
            <span className={styles.textMuted}>
              {" "}
              • Audit: {screenshotAudit.status}
              {screenshotAudit.flags?.length > 0
                ? ` (${screenshotAudit.flags.join(", ")})`
                : ""}
            </span>
          )}
        </div>
      </div>
    </CollapsibleSection>
  );
}

export default WebsiteSection;

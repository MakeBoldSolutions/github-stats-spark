import { Code2, ExternalLink } from "lucide-react";
import { Eyebrow, Badge, Button } from "@/components/Brand";
import {
  getLanguageColor,
  getRepositoryHealthPresentation,
} from "@/utils/repositoryPresentation";
import styles from "../../RepositoryDetail.module.css";

function RepositoryDetailHeader({
  repository,
  onClose,
  resultIndex,
  resultTotal,
}) {
  const language = repository.language || "Unknown";
  const langColor = getLanguageColor(language);
  const health = getRepositoryHealthPresentation(repository);
  const position =
    typeof resultIndex === "number" && resultIndex >= 0 && resultTotal
      ? `Repository ${resultIndex + 1} of ${resultTotal}`
      : null;

  return (
    <>
      <div className={styles.modalAccent} />

      <div className={styles.modalHeader}>
        <div className={styles.headerContent}>
          {position && <Eyebrow>{position}</Eyebrow>}
          <h2 className={styles.modalTitle}>{repository.name}</h2>

          <div className={styles.headerMeta}>
            <span className={styles.langChip}>
              <span
                className={styles.langDot}
                style={{ background: langColor }}
              />
              <span className={styles.langName}>{language}</span>
            </span>
            {health.tier && <Badge tone={health.tone}>{health.label}</Badge>}
            {health.score !== null && (
              <span className={styles.attentionScoreLabel}>
                Attention score {health.score.toFixed(1)}
              </span>
            )}
            {repository.is_archived && <Badge tone="neutral">Archived</Badge>}
            {repository.is_fork && <Badge tone="neutral">Fork</Badge>}
          </div>

          <div className={styles.headerActions}>
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Code2 size={16} aria-hidden="true" />}
              onClick={() =>
                window.open(repository.url, "_blank", "noopener,noreferrer")
              }
            >
              Repository
            </Button>
            {repository.homepage && (
              <Button
                variant="secondary"
                size="sm"
                iconLeft={<ExternalLink size={16} aria-hidden="true" />}
                onClick={() =>
                  window.open(
                    repository.homepage,
                    "_blank",
                    "noopener,noreferrer",
                  )
                }
              >
                Live site
              </Button>
            )}
          </div>
        </div>

        <button
          className={styles.closeButton}
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
      </div>
    </>
  );
}

export default RepositoryDetailHeader;

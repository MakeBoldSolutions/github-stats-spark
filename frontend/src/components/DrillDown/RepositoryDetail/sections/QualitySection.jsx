import styles from "../../RepositoryDetail.module.css";
import CollapsibleSection from "../CollapsibleSection";

function QualityBadge({ label, active }) {
  return (
    <span
      className={`${styles.qualityBadge} ${active ? styles.qualityBadgeActive : styles.qualityBadgeInactive}`}
      title={active ? `Has ${label}` : `No ${label}`}
    >
      <span className={styles.qualityBadgeDot} aria-hidden="true" />
      <span className={styles.qualityBadgeLabel}>{label}</span>
    </span>
  );
}

function QualitySection({ repository, expanded, onToggle }) {
  return (
    <CollapsibleSection
      section="quality"
      title="Quality"
      expanded={expanded}
      onToggle={onToggle}
    >
      <div className={styles.qualityGrid}>
        <QualityBadge label="README" active={repository.has_readme} />
        <QualityBadge label="License" active={repository.has_license} />
        <QualityBadge label="CI/CD" active={repository.has_ci_cd} />
        <QualityBadge label="Tests" active={repository.has_tests} />
        <QualityBadge label="Docs" active={repository.has_docs} />
        <QualityBadge label="Discussions" active={repository.has_discussions} />
        <QualityBadge
          label="Contributing"
          active={repository.has_contributing}
        />
        <QualityBadge
          label="Security Policy"
          active={repository.has_security_policy}
        />
      </div>
    </CollapsibleSection>
  );
}

export default QualitySection;

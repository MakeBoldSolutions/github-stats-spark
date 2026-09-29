import { useMemo } from "react";
import styles from "./RepositoryDetail.module.css";
import { useRepositoryDetailInteractions } from "./RepositoryDetail/hooks/useRepositoryDetailInteractions";
import { useSectionToggles } from "./RepositoryDetail/hooks/useSectionToggles";
import {
  calculateLanguagePercentage,
  formatDate,
  formatNumber,
  formatReason,
  formatRelativeDate,
  formatSize,
  getAvailabilityBadgeClass,
  getDependencyBadgeClass,
  getScreenshotUrl,
  getSecurityStateBadgeClass,
  getTopDependencies,
} from "./RepositoryDetail/utils/repositoryDetailUtils";
import RepositoryDetailHeader from "./RepositoryDetail/sections/RepositoryDetailHeader";
import RepositoryDetailFooter from "./RepositoryDetail/sections/RepositoryDetailFooter";
import SummarySection from "./RepositoryDetail/sections/SummarySection";
import WebsiteSection from "./RepositoryDetail/sections/WebsiteSection";
import RepositoryInfoSection from "./RepositoryDetail/sections/RepositoryInfoSection";
import QualitySection from "./RepositoryDetail/sections/QualitySection";
import LanguagesSection from "./RepositoryDetail/sections/LanguagesSection";
import SignalsSection from "./RepositoryDetail/sections/SignalsSection";
import CommitHistorySection from "./RepositoryDetail/sections/CommitHistorySection";
import CommitMetricsSection from "./RepositoryDetail/sections/CommitMetricsSection";
import ActivityMetricsSection from "./RepositoryDetail/sections/ActivityMetricsSection";
import RankingSection from "./RepositoryDetail/sections/RankingSection";
import TechStackSection from "./RepositoryDetail/sections/TechStackSection";
import FixScorePromptSection from "./RepositoryDetail/sections/FixScorePromptSection";

/**
 * RepositoryDetail Component
 *
 * Modal/overlay component that displays comprehensive details for a single repository.
 * Mobile-first with collapsible sections for better mobile UX.
 * Shows all attributes from the unified repositories.json including:
 * - Basic metadata (name, description, dates)
 * - Repository stats (stars, forks, watchers, issues)
 * - Commit history and metrics
 * - Language statistics
 * - Tech stack and dependencies (if available)
 * - AI summary (if available)
 * - Quality indicators (CI/CD, tests, docs, license)
 *
 * @component
 * @param {Object} props - Component props
 * @param {Object} props.repository - Repository object with all attributes
 * @param {Function} props.onClose - Callback to close the modal
 * @param {Function} [props.onNext] - Callback to navigate to next repository
 * @param {Function} [props.onPrevious] - Callback to navigate to previous repository
 */
const STAT_TILES = [
  { key: "stars", label: "Stars" },
  { key: "forks", label: "Forks" },
  { key: "total_commits", label: "Commits" },
];

function AttentionBreakdown({ components }) {
  if (!components) return null;
  const rows = [
    ["Pull requests", components.pull_requests?.score],
    ["Security findings", components.security?.score],
    ["Staleness", components.staleness?.score],
    ["Dependency health", components.dependencies?.score],
  ].filter(([, score]) => typeof score === "number");

  if (rows.length === 0) return null;

  return (
    <div className={styles.attentionBreakdown}>
      {rows.map(([label, score]) => (
        <div key={label} className={styles.attentionRow}>
          <span className={styles.attentionLabel}>{label}</span>
          <div className={styles.attentionTrack}>
            <div
              className={`${styles.attentionFill} ${
                score >= 60
                  ? styles.attentionCritical
                  : score >= 30
                    ? styles.attentionCaution
                    : styles.attentionPositive
              }`}
              style={{ width: `${Math.min(score, 100)}%` }}
            />
          </div>
          <span className={styles.attentionValue}>{score.toFixed(0)}</span>
        </div>
      ))}
    </div>
  );
}

function RepositoryDetail({
  repository,
  onClose,
  onNext,
  onPrevious,
  resultIndex,
  resultTotal,
}) {
  const { expandedSections, toggleSection } = useSectionToggles();
  const bind = useRepositoryDetailInteractions({ onClose, onNext, onPrevious });

  const pullRequestSummary = repository.pull_request_summary || {};
  const securitySummary = repository.security_summary || {};
  const diagnosticsSummary = repository.diagnostics_summary || {};
  const screenshotAudit = repository.screenshot_audit || {};
  const openSecurityAlerts =
    securitySummary.active_alert_counts?.total_open || 0;
  const topDependencies = useMemo(
    () => getTopDependencies(repository),
    [repository],
  );
  const hasPrevious =
    typeof resultIndex === "number" ? resultIndex > 0 : Boolean(onPrevious);
  const hasNext =
    typeof resultIndex === "number" && typeof resultTotal === "number"
      ? resultIndex >= 0 && resultIndex < resultTotal - 1
      : Boolean(onNext);

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        {...bind()}
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.modalContent}>
          <RepositoryDetailHeader
            repository={repository}
            onClose={onClose}
            resultIndex={resultIndex}
            resultTotal={resultTotal}
          />

          {/* Body */}
          <div className={styles.modalBody}>
            <div className={styles.statsGrid}>
              {STAT_TILES.map(({ key, label }) => (
                <div key={key} className={styles.statTile}>
                  <span className={styles.statTileValue}>
                    {formatNumber(repository[key])}
                  </span>
                  <span className={styles.statTileLabel}>{label}</span>
                </div>
              ))}
              <div className={styles.statTile}>
                <span className={styles.statTileValue}>
                  {formatNumber(repository.recent_commits_90d)}
                </span>
                <span className={styles.statTileLabel}>Last 90 days</span>
              </div>
              <div className={styles.statTile}>
                <span className={styles.statTileValue}>
                  {formatRelativeDate(repository.days_since_last_push)}
                </span>
                <span className={styles.statTileLabel}>Last push</span>
              </div>
              <div className={styles.statTile}>
                <span className={styles.statTileValue}>
                  {repository.age_days
                    ? `${Math.floor(repository.age_days / 365)}y`
                    : "N/A"}
                </span>
                <span className={styles.statTileLabel}>Age</span>
              </div>
            </div>

            <SummarySection
              summary={repository.ai_summary}
              expanded={expandedSections.summary}
              onToggle={toggleSection}
            />

            <QualitySection
              repository={repository}
              expanded={expandedSections.quality}
              onToggle={toggleSection}
            />

            <AttentionBreakdown
              components={repository.attention_metrics?.components}
            />

            <FixScorePromptSection
              repository={repository}
              expanded={expandedSections.remediation}
              onToggle={toggleSection}
            />

            <SignalsSection
              pullRequestSummary={pullRequestSummary}
              securitySummary={securitySummary}
              diagnosticsSummary={diagnosticsSummary}
              screenshotAudit={screenshotAudit}
              openSecurityAlerts={openSecurityAlerts}
              expanded={expandedSections.signals}
              onToggle={toggleSection}
              formatNumber={formatNumber}
              formatReason={formatReason}
              getAvailabilityBadgeClass={(availability) =>
                getAvailabilityBadgeClass(styles, availability)
              }
              getSecurityStateBadgeClass={(overallState) =>
                getSecurityStateBadgeClass(styles, overallState)
              }
            />

            <TechStackSection
              repository={repository}
              expanded={expandedSections.tech}
              onToggle={toggleSection}
              topDependencies={topDependencies}
              formatNumber={formatNumber}
              getDependencyBadgeClass={(status) =>
                getDependencyBadgeClass(styles, status)
              }
            />

            <WebsiteSection
              repository={repository}
              expanded={expandedSections.website}
              onToggle={toggleSection}
              formatDate={formatDate}
              getScreenshotUrl={getScreenshotUrl}
              screenshotAudit={screenshotAudit}
            />

            {/* Supplementary detail (repository info, languages, commit history, ranking) */}
            <div className={styles.contentGrid}>
              <div className={styles.column}>
                <RepositoryInfoSection
                  repository={repository}
                  expanded={expandedSections.info}
                  onToggle={toggleSection}
                  formatDate={formatDate}
                  formatRelativeDate={formatRelativeDate}
                  formatNumber={formatNumber}
                />

                <LanguagesSection
                  repository={repository}
                  expanded={expandedSections.languages}
                  onToggle={toggleSection}
                  calculateLanguagePercentage={(bytes) =>
                    calculateLanguagePercentage(
                      repository.language_stats,
                      bytes,
                    )
                  }
                />
              </div>

              <div className={styles.column}>
                <CommitHistorySection
                  repository={repository}
                  expanded={expandedSections.commits}
                  onToggle={toggleSection}
                  formatDate={formatDate}
                  formatNumber={formatNumber}
                  formatSize={formatSize}
                />

                <CommitMetricsSection
                  repository={repository}
                  formatDate={formatDate}
                  formatNumber={formatNumber}
                  formatSize={formatSize}
                />

                <ActivityMetricsSection
                  repository={repository}
                  formatDate={formatDate}
                  formatNumber={formatNumber}
                />

                <RankingSection repository={repository} />
              </div>
            </div>
          </div>

          <RepositoryDetailFooter
            onNext={onNext}
            onPrevious={onPrevious}
            hasNext={hasNext}
            hasPrevious={hasPrevious}
          />
        </div>
      </div>
    </div>
  );
}

export default RepositoryDetail;

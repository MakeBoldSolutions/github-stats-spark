import PropTypes from "prop-types";
import CoverageState from "@/components/Common/CoverageState";
import DataTable from "@/components/Common/DataTable";
import { alertColumns, alertKey } from "@/components/Security/alertColumns";
import { REASON_LABELS, filterAlerts } from "@/utils/dependabot";
import styles from "../../RepositoryDetail.module.css";
import CollapsibleSection from "../CollapsibleSection";

const COLUMNS = alertColumns({ showRepository: false });

/**
 * The repository's stored Dependabot alerts (self-hosted deployment only):
 * whether they could be read, and the open alerts, most severe first.
 */
function SecuritySection({ security, expanded, onToggle }) {
  if (!security) return null;
  const { coverage, alerts } = security;
  const open = filterAlerts(
    { repositories: [coverage], alerts },
    { state: "open" },
  );

  return (
    <CollapsibleSection
      section="security"
      title="Security"
      expanded={expanded}
      onToggle={onToggle}
    >
      <div className={styles.sectionContent}>
        <p>
          Dependabot:{" "}
          <CoverageState
            status={coverage.status}
            count={coverage.counts?.open?.total ?? 0}
            reason={REASON_LABELS[coverage.reason] ?? coverage.reason}
          />
        </p>
        {open.length > 0 && (
          <DataTable
            caption={`${open.length} open alert${open.length === 1 ? "" : "s"}`}
            columns={COLUMNS}
            rows={open}
            rowKey={alertKey}
          />
        )}
      </div>
    </CollapsibleSection>
  );
}

SecuritySection.propTypes = {
  security: PropTypes.shape({
    coverage: PropTypes.object.isRequired,
    alerts: PropTypes.array.isRequired,
  }),
  expanded: PropTypes.bool,
  onToggle: PropTypes.func.isRequired,
};

export default SecuritySection;

import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Download } from "lucide-react";
import styles from "./ExportButton.module.css";

/**
 * ExportButton Component
 *
 * Accessible, dismissible export menu for the current Overview filtered
 * list or Health ranked list. Exports CSV or JSON client-side and reports
 * outcomes through the supplied toast callback instead of alert().
 *
 * @component
 * @param {Object} props
 * @param {Array} props.data - Array of repository objects to export
 * @param {string} [props.filename='repositories'] - Base filename for export
 * @param {string} [props.label='Export'] - Button label
 * @param {boolean} [props.disabled=false] - Whether button is disabled
 * @param {Function} [props.onToast] - (message, variant) => void, for export outcomes
 */
function ExportButton({
  data,
  filename = "repositories",
  label = "Export",
  disabled = false,
  onToast,
}) {
  const [showMenu, setShowMenu] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!showMenu) return;
    const handleClickOutside = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setShowMenu(false);
      }
    };
    const handleKeydown = (e) => {
      if (e.key === "Escape") setShowMenu(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeydown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeydown);
    };
  }, [showMenu]);

  const notify = (message, variant = "info") => {
    if (onToast) onToast(message, variant);
  };

  const convertToCSV = (repositories) => {
    if (!Array.isArray(repositories) || repositories.length === 0) return "";

    const columns = [
      { key: "name", label: "Repository Name" },
      { key: "language", label: "Language" },
      { key: "stars", label: "Stars" },
      { key: "forks", label: "Forks" },
      { key: "watchers", label: "Watchers" },
      { key: "open_issues", label: "Open Issues" },
      { key: "created_at", label: "Created At" },
      { key: "updated_at", label: "Last Updated" },
      { key: "commit_history.total_commits", label: "Total Commits" },
      { key: "commit_history.recent_90d", label: "Commits (90d)" },
      { key: "commit_history.recent_180d", label: "Commits (180d)" },
      { key: "commit_history.recent_365d", label: "Commits (365d)" },
      { key: "commit_history.first_commit_date", label: "First Commit" },
      { key: "commit_history.last_commit_date", label: "Last Commit" },
      { key: "commit_metrics.avg_size", label: "Avg Commit Size" },
      { key: "commit_metrics.largest_commit.size", label: "Largest Commit" },
      { key: "commit_metrics.smallest_commit.size", label: "Smallest Commit" },
      { key: "commit_velocity", label: "Commit Velocity" },
      { key: "age_days", label: "Age (days)" },
      { key: "days_since_last_push", label: "Days Since Push" },
      { key: "has_readme", label: "Has README" },
      { key: "has_license", label: "Has License" },
      { key: "has_ci_cd", label: "Has CI/CD" },
      { key: "has_tests", label: "Has Tests" },
      {
        key: "pull_request_summary.availability",
        label: "PR Data Availability",
      },
      { key: "pull_request_summary.total_open", label: "Open Pull Requests" },
      { key: "pull_request_summary.draft_count", label: "Draft Pull Requests" },
      {
        key: "pull_request_summary.review_requested_count",
        label: "PRs Awaiting Review",
      },
      {
        key: "security_summary.availability",
        label: "Security Data Availability",
      },
      {
        key: "security_summary.overall_state",
        label: "Security Overall State",
      },
      {
        key: "security_summary.active_alert_counts.total_open",
        label: "Open Security Alerts",
      },
      {
        key: "security_summary.active_alert_counts.critical",
        label: "Critical Alerts",
      },
      {
        key: "security_summary.active_alert_counts.high",
        label: "High Alerts",
      },
      {
        key: "diagnostics_summary.availability",
        label: "Diagnostics Availability",
      },
      {
        key: "diagnostics_summary.issues.total_open",
        label: "Open Issues (Diagnostics)",
      },
      {
        key: "diagnostics_summary.security.dependabot.open_alerts",
        label: "Dependabot Open Alerts",
      },
      {
        key: "diagnostics_summary.actions.failure_count",
        label: "Workflow Failures",
      },
      { key: "screenshot_audit.status", label: "Screenshot Audit Status" },
      { key: "screenshot_audit.flags", label: "Screenshot Audit Flags" },
    ];

    const getNestedValue = (obj, path) =>
      path.split(".").reduce((acc, part) => acc?.[part], obj);

    const header = columns.map((col) => `"${col.label}"`).join(",");

    const rows = repositories.map((repo) =>
      columns
        .map((col) => {
          const value = getNestedValue(repo, col.key);
          if (value === null || value === undefined) return '""';
          if (typeof value === "boolean") return value ? "Yes" : "No";
          if (typeof value === "number") return value;
          return `"${String(value).replace(/"/g, '""')}"`;
        })
        .join(","),
    );

    return [header, ...rows].join("\n");
  };

  const downloadFile = (content, downloadFilename, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = downloadFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    setShowMenu(false);
    if (!data || data.length === 0) {
      notify("No data to export", "warning");
      return;
    }
    try {
      const csv = convertToCSV(data);
      const timestamp = new Date().toISOString().split("T")[0];
      downloadFile(
        csv,
        `${filename}-${timestamp}.csv`,
        "text/csv;charset=utf-8;",
      );
      notify(`Exported ${data.length} repositories as CSV`, "success");
    } catch (error) {
      console.error("CSV export failed:", error);
      notify("Export failed. Check the console for details.", "error");
    }
  };

  const handleExportJSON = () => {
    setShowMenu(false);
    if (!data || data.length === 0) {
      notify("No data to export", "warning");
      return;
    }
    try {
      const json = JSON.stringify(data, null, 2);
      const timestamp = new Date().toISOString().split("T")[0];
      downloadFile(
        json,
        `${filename}-${timestamp}.json`,
        "application/json;charset=utf-8;",
      );
      notify(`Exported ${data.length} repositories as JSON`, "success");
    } catch (error) {
      console.error("JSON export failed:", error);
      notify("Export failed. Check the console for details.", "error");
    }
  };

  const count = data?.length ?? 0;

  return (
    <div className={styles.wrapper} ref={rootRef}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setShowMenu((open) => !open)}
        disabled={disabled}
        aria-label="Export data"
        aria-expanded={showMenu}
        aria-haspopup="true"
      >
        <Download size={16} aria-hidden="true" />
        {label}
      </button>

      {showMenu && (
        <div className={styles.menu} role="menu">
          <p className={styles.menuCount}>
            {count} repositories in current view
          </p>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={handleExportCSV}
          >
            <span className={styles.menuItemLabel}>Export as CSV</span>
            <span className={styles.menuItemDesc}>
              Spreadsheet-ready summary columns
            </span>
          </button>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={handleExportJSON}
          >
            <span className={styles.menuItemLabel}>Export as JSON</span>
            <span className={styles.menuItemDesc}>Full repository records</span>
          </button>
        </div>
      )}
    </div>
  );
}

ExportButton.propTypes = {
  data: PropTypes.array.isRequired,
  filename: PropTypes.string,
  label: PropTypes.string,
  disabled: PropTypes.bool,
  onToast: PropTypes.func,
};

export default ExportButton;

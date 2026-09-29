import PropTypes from "prop-types";
import { Card, Eyebrow } from "@/components/Brand";
import styles from "./QualityMatrix.module.css";

const COLUMNS = [
  { key: "has_readme", label: "README" },
  { key: "has_license", label: "License" },
  { key: "has_ci_cd", label: "CI/CD" },
  { key: "has_tests", label: "Tests" },
  { key: "has_docs", label: "Docs" },
];

export default function QualityMatrix({ repositories, onRepoClick }) {
  if (!repositories || repositories.length === 0) {
    return null;
  }

  return (
    <Card padding="none" className={styles.card}>
      <div className={styles.header}>
        <Eyebrow>Quality</Eyebrow>
        <h3 className={styles.title}>Quality coverage matrix</h3>
      </div>
      <div className={styles.scrollArea}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.repoHeader}>Repository</th>
              {COLUMNS.map((col) => (
                <th key={col.key} className={styles.colHeader}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {repositories.map((repo) => (
              <tr
                key={repo.name}
                className={styles.row}
                tabIndex={0}
                role="button"
                onClick={() => onRepoClick?.(repo)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRepoClick?.(repo);
                  }
                }}
              >
                <td className={styles.repoName}>{repo.name}</td>
                {COLUMNS.map((col) => (
                  <td key={col.key} className={styles.cell}>
                    <span
                      className={`${styles.square} ${repo[col.key] ? styles.squareOn : styles.squareOff}`}
                      aria-label={
                        repo[col.key]
                          ? `Has ${col.label}`
                          : `Missing ${col.label}`
                      }
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

QualityMatrix.propTypes = {
  repositories: PropTypes.array.isRequired,
  onRepoClick: PropTypes.func,
};

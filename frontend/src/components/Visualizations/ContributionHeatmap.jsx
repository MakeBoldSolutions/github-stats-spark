import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { computeHeatmapData } from "@/services/metricsCalculator";
import { Card, Eyebrow } from "@/components/Brand";
import styles from "./ContributionHeatmap.module.css";

const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * ContributionHeatmap renders the approved trailing-365-day calendar heatmap
 * of daily commit counts, ending at `generatedAt` (falls back to today when
 * absent). Each cell is coloured by one of five approved intensity levels.
 *
 * @param {Object} props
 * @param {Object} props.activityCalendar  - Map of "YYYY-MM-DD" → commit count
 * @param {string} [props.generatedAt]     - metadata.generated_at; window end date
 * @param {string} [props.className]       - Extra CSS class
 */
export default function ContributionHeatmap({
  activityCalendar,
  generatedAt,
  className,
}) {
  const [tooltip, setTooltip] = useState(null);

  const cells = useMemo(
    () => computeHeatmapData(activityCalendar, generatedAt),
    [activityCalendar, generatedAt],
  );

  if (!activityCalendar || Object.keys(activityCalendar).length === 0) {
    return (
      <Card
        padding="lg"
        className={`${styles.heatmap} ${className ?? ""}`.trim()}
      >
        <p className={styles.empty}>No activity data available.</p>
      </Card>
    );
  }

  const totalContributions = cells.reduce((sum, c) => sum + c.count, 0);
  const activeDays = cells.filter((c) => c.count > 0).length;

  // Group cells by ISO week (column) and day-of-week (row), Sunday-first
  const columns = [];
  let currentCol = null;
  let currentColKey = null;

  for (const cell of cells) {
    const date = new Date(cell.date + "T00:00:00");
    const dow = date.getDay(); // 0 = Sun

    const colDate = new Date(date);
    colDate.setDate(colDate.getDate() - dow);
    const colKey = colDate.toISOString().slice(0, 10);

    if (colKey !== currentColKey) {
      currentCol = { key: colKey, month: date.getMonth(), cells: [] };
      columns.push(currentCol);
      currentColKey = colKey;
    }

    if (currentCol.cells.length === 0 && dow > 0 && columns.length === 1) {
      for (let i = 0; i < dow; i++) {
        currentCol.cells.push(null);
      }
    }

    currentCol.cells.push(cell);
  }

  const monthOffsets = [];
  let lastMonth = -1;
  columns.forEach((col, idx) => {
    if (col.month !== lastMonth) {
      monthOffsets.push({ month: col.month, colIdx: idx });
      lastMonth = col.month;
    }
  });

  return (
    <Card
      padding="lg"
      className={`${styles.heatmap} ${className ?? ""}`.trim()}
    >
      <div className={styles.header}>
        <div>
          <Eyebrow>Contribution activity</Eyebrow>
          <p className={styles.summary}>
            {totalContributions.toLocaleString()} contributions across{" "}
            {activeDays.toLocaleString()} active days
          </p>
        </div>
        <div className={styles.legend} aria-hidden="true">
          <span className={styles.legendLabel}>Less</span>
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className={`${styles.cell} ${styles[`intensity${i}`]} ${styles.legendCell}`}
            />
          ))}
          <span className={styles.legendLabel}>More</span>
        </div>
      </div>

      <div className={styles.wrapper}>
        <div className={styles.scrollArea}>
          <div
            className={styles.monthRow}
            style={{
              gridTemplateColumns: `repeat(${columns.length}, var(--cell-size))`,
            }}
          >
            {columns.map((col, idx) => {
              const mo = monthOffsets.find((m) => m.colIdx === idx);
              return (
                <span key={col.key} className={styles.monthLabel}>
                  {mo ? MONTH_LABELS[mo.month] : ""}
                </span>
              );
            })}
          </div>

          <div className={styles.grid}>
            {columns.map((col) => (
              <div key={col.key} className={styles.column}>
                {Array.from({ length: 7 }).map((_, dow) => {
                  const cell = col.cells[dow] ?? null;
                  if (!cell) {
                    return <div key={dow} className={styles.cellEmpty} />;
                  }
                  return (
                    <div
                      key={cell.date}
                      className={`${styles.cell} ${styles[`intensity${cell.intensity}`]}`}
                      role="img"
                      tabIndex={0}
                      aria-label={`${cell.count} contribution${cell.count !== 1 ? "s" : ""} on ${cell.date}`}
                      title={`${cell.count} contribution${cell.count !== 1 ? "s" : ""} on ${cell.date}`}
                      onMouseEnter={(e) =>
                        setTooltip({
                          date: cell.date,
                          count: cell.count,
                          x: e.clientX,
                          y: e.clientY,
                        })
                      }
                      onMouseLeave={() => setTooltip(null)}
                      onFocus={() =>
                        setTooltip({ date: cell.date, count: cell.count })
                      }
                      onBlur={() => setTooltip(null)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className={styles.footnote}>Trailing 365 days</p>

      {tooltip && tooltip.x !== undefined && (
        <div
          className={styles.tooltip}
          style={{ left: tooltip.x + 12, top: tooltip.y - 36 }}
          role="tooltip"
        >
          <strong>
            {tooltip.count} contribution{tooltip.count !== 1 ? "s" : ""}
          </strong>
          {" on "}
          {tooltip.date}
        </div>
      )}
    </Card>
  );
}

ContributionHeatmap.propTypes = {
  activityCalendar: PropTypes.objectOf(PropTypes.number),
  generatedAt: PropTypes.string,
  className: PropTypes.string,
};

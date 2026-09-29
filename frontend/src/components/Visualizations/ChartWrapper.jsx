/**
 * ChartWrapper Component
 *
 * Responsive wrapper for Chart.js canvas with horizontal scroll support,
 * loading states, error boundaries, and mobile optimizations.
 *
 * @component
 */

import React, { useRef, useMemo } from "react";
import PropTypes from "prop-types";
import { useChart, useResponsiveChartSize } from "@/hooks/useChart";
import LoadingState from "@/components/Common/LoadingState";
import "./ChartWrapper.css";

export const ChartWrapper = ({
  type,
  data,
  options = {},
  title,
  enableHorizontalScroll = true,
  maxDataPoints = 10,
  loading = false,
  error = null,
  emptyMessage = "No data to display",
  className = "",
}) => {
  const { width, height } = useResponsiveChartSize({
    minHeight: 300,
    maxHeight: 500,
    mobileAspectRatio: 1.2,
    desktopAspectRatio: 2.5,
  });

  const containerRef = useRef(null);

  // Determine if horizontal scroll is needed
  const needsHorizontalScroll =
    enableHorizontalScroll && data?.labels?.length > maxDataPoints;

  // Calculate scrollable width for horizontal scroll
  const scrollableWidth = useMemo(() => {
    if (needsHorizontalScroll && data?.labels?.length) {
      // Each data point gets minimum 60px width on mobile, 80px on desktop
      const isMobile = window.innerWidth < 768;
      const minPointWidth = isMobile ? 60 : 80;
      const calculatedWidth = data.labels.length * minPointWidth;
      return Math.max(width, calculatedWidth);
    }
    return width;
  }, [needsHorizontalScroll, data?.labels?.length, width]);

  // Prepare chart data - limit to maxDataPoints if not scrollable
  const chartData = needsHorizontalScroll
    ? data
    : {
        ...data,
        labels: data?.labels?.slice(0, maxDataPoints) || [],
        datasets:
          data?.datasets?.map((dataset) => ({
            ...dataset,
            data: dataset.data?.slice(0, maxDataPoints) || [],
          })) || [],
      };

  const { canvasRef } = useChart({
    type,
    data: chartData,
    options: {
      ...options,
      maintainAspectRatio: false,
    },
    enableTouchAndHold: true,
    debounceDelay: 150,
  });

  // Show loading state
  if (loading) {
    return (
      <div className={`chart-wrapper ${className}`}>
        {title && <h3 className="chart-title">{title}</h3>}
        <div className="chart-loading">
          <LoadingState type="chart" />
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className={`chart-wrapper ${className}`}>
        {title && <h3 className="chart-title">{title}</h3>}
        <div className="chart-error">
          <p>Error loading chart</p>
          <p className="chart-error-message">{error}</p>
        </div>
      </div>
    );
  }

  // Show empty state - check labels for label-based charts, datasets for scatter/bubble
  const hasData =
    data &&
    ((data.labels && data.labels.length > 0) ||
      (data.datasets &&
        data.datasets.length > 0 &&
        data.datasets.some((ds) => ds.data && ds.data.length > 0)));
  if (!hasData) {
    return (
      <div className={`chart-wrapper ${className}`}>
        {title && <h3 className="chart-title">{title}</h3>}
        <div className="chart-empty">
          <p>{emptyMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`chart-wrapper ${className}`}>
      {title && <h3 className="chart-title">{title}</h3>}

      {needsHorizontalScroll && (
        <div className="chart-scroll-hint">← Scroll to see more data →</div>
      )}

      <div
        ref={containerRef}
        className={`chart-container ${needsHorizontalScroll ? "chart-scrollable" : ""}`}
        style={{ height: `${height}px` }}
      >
        <div
          className="chart-canvas-wrapper"
          style={{
            width: needsHorizontalScroll ? `${scrollableWidth}px` : "100%",
            height: "100%",
          }}
        >
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={title || "Chart visualization"}
          />
        </div>
      </div>

      {needsHorizontalScroll && data.labels.length > maxDataPoints && (
        <div className="chart-data-info">
          Showing {data.labels.length} data points (scroll to view all)
        </div>
      )}
    </div>
  );
};

ChartWrapper.propTypes = {
  type: PropTypes.oneOf(["bar", "line", "pie", "doughnut", "scatter", "bubble"])
    .isRequired,
  data: PropTypes.shape({
    labels: PropTypes.arrayOf(PropTypes.string),
    datasets: PropTypes.arrayOf(
      PropTypes.shape({
        label: PropTypes.string,
        data: PropTypes.arrayOf(PropTypes.number),
        backgroundColor: PropTypes.oneOfType([
          PropTypes.string,
          PropTypes.arrayOf(PropTypes.string),
        ]),
        borderColor: PropTypes.oneOfType([
          PropTypes.string,
          PropTypes.arrayOf(PropTypes.string),
        ]),
      }),
    ),
  }).isRequired,
  options: PropTypes.object,
  title: PropTypes.string,
  enableHorizontalScroll: PropTypes.bool,
  maxDataPoints: PropTypes.number,
  loading: PropTypes.bool,
  error: PropTypes.string,
  emptyMessage: PropTypes.string,
  className: PropTypes.string,
};

export default ChartWrapper;

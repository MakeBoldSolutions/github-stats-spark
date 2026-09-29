/**
 * BarChart Component
 *
 * Renders a bar chart visualization using Chart.js with mobile optimizations.
 * Vertical orientation on mobile, limited to max 10 bars for readability.
 *
 * @component
 */

import React from "react";
import PropTypes from "prop-types";
import ChartWrapper from "./ChartWrapper";

const COLORS = [
  "#982407", // rust-500
  "#c6620c", // ember-500
  "#2f5a8f", // info
  "#2f6f4c", // positive
  "#b8821a", // caution
  "#a8321a", // critical
  "#d4715a", // rust-300
  "#e88f3d", // ember-300
  "#76736c", // ink-500
  "#6c1804", // rust-700
];

/**
 * Format values based on metric type
 */
function formatValue(value, metricLabel) {
  if (!value && value !== 0) return "N/A";

  if (metricLabel?.includes("Date")) {
    return new Date(value).toLocaleDateString();
  }
  if (metricLabel?.includes("Size")) {
    return `${value.toLocaleString()} changes`;
  }
  if (typeof value === "number") {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toLocaleString();
  }
  return value;
}

/**
 * BarChart Component
 *
 * @param {Object} props
 * @param {Array} props.data - Chart data array with {name, value} objects
 * @param {string} props.metricLabel - Label for the metric being displayed
 * @param {Function} props.onBarClick - Handler for bar click events
 * @param {boolean} props.horizontal - Display horizontal bars (default: false for mobile)
 * @param {number} props.maxBars - Maximum number of bars to display (default: 10 for mobile)
 */
export default function BarChart({
  data,
  metricLabel = "Value",
  onBarClick,
  horizontal = false,
  maxBars = 10,
}) {
  if (!data || data.length === 0) {
    return (
      <ChartWrapper
        type="bar"
        data={{ labels: [], datasets: [] }}
        emptyMessage="No data available for visualization"
      />
    );
  }

  // Limit data to maxBars for mobile readability
  const limitedData = data.slice(0, maxBars);

  // Prepare Chart.js data
  const chartData = {
    labels: limitedData.map((item) => item.name || item.label),
    datasets: [
      {
        label: metricLabel,
        data: limitedData.map((item) => item.value),
        backgroundColor: limitedData.map(
          (_, index) => COLORS[index % COLORS.length],
        ),
        borderColor: limitedData.map(
          (_, index) => COLORS[index % COLORS.length],
        ),
        borderWidth: 0,
        borderRadius: 4,
        barThickness: horizontal ? 24 : "flex",
        maxBarThickness: horizontal ? 32 : 60,
      },
    ],
  };

  // Chart options
  const options = {
    indexAxis: horizontal ? "y" : "x",
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "nearest", // Keeps hover behavior usable on touch and mouse input.
      intersect: false,
      axis: horizontal ? "y" : "x",
    },
    onClick: (event, elements) => {
      if (elements.length > 0 && onBarClick) {
        const index = elements[0].index;
        const clickedData = limitedData[index];
        onBarClick({ ...clickedData, fullData: clickedData });
      }
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        enabled: true,
        padding: 12, // Extra padding improves touch readability.
        titleFont: {
          size: 14, // Maintain readable tooltip text on small screens.
        },
        bodyFont: {
          size: 14, // Maintain readable tooltip text on small screens.
        },
        callbacks: {
          label: (context) => {
            const value = context.parsed.y || context.parsed.x;
            return `${metricLabel}: ${formatValue(value, metricLabel)}`;
          },
          afterLabel: (context) => {
            const item = limitedData[context.dataIndex];
            if (item.language) {
              return `Language: ${item.language}`;
            }
            return "";
          },
        },
      },
    },
    scales: horizontal
      ? {
          x: {
            beginAtZero: true,
            grid: {
              display: true,
              color: "#ddd9d0",
            },
            ticks: {
              callback: (value) => formatValue(value, metricLabel),
            },
          },
          y: {
            grid: {
              display: false,
            },
            ticks: {
              font: {
                size: 11,
              },
              autoSkip: false,
            },
          },
        }
      : {
          x: {
            grid: {
              display: false,
            },
            ticks: {
              maxRotation: 45,
              minRotation: 0,
              font: {
                size: 11,
              },
            },
          },
          y: {
            beginAtZero: true,
            grid: {
              display: true,
              color: "#ddd9d0",
            },
            ticks: {
              callback: (value) => formatValue(value, metricLabel),
            },
          },
        },
  };

  return (
    <ChartWrapper
      type="bar"
      data={chartData}
      options={options}
      title={`${metricLabel} by Repository`}
      enableHorizontalScroll={!horizontal && data.length > maxBars}
      maxDataPoints={maxBars}
    />
  );
}

BarChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string,
      label: PropTypes.string,
      value: PropTypes.number,
      language: PropTypes.string,
    }),
  ).isRequired,
  metricLabel: PropTypes.string,
  onBarClick: PropTypes.func,
  horizontal: PropTypes.bool,
  maxBars: PropTypes.number,
};

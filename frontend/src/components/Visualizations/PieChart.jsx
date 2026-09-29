/**
 * PieChart Component
 *
 * Renders a pie/doughnut chart visualization using Chart.js with touch interactions.
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
 * PieChart Component
 *
 * @param {Object} props
 * @param {Array} props.data - Chart data array with {name, value} objects
 * @param {string} props.title - Chart title
 * @param {Function} props.onSegmentClick - Handler for segment click events
 * @param {boolean} props.doughnut - Display as doughnut chart (default: false)
 * @param {number} props.cutout - Doughnut cutout percentage (default: 50)
 */
export default function PieChart({
  data,
  title = "Distribution",
  onSegmentClick,
  doughnut = false,
  cutout = 50,
}) {
  if (!data || data.length === 0) {
    return (
      <ChartWrapper
        type="pie"
        data={{ labels: [], datasets: [] }}
        emptyMessage="No data available for visualization"
      />
    );
  }

  // Prepare Chart.js data
  const chartData = {
    labels: data.map((item) => item.name || item.label),
    datasets: [
      {
        data: data.map((item) => item.value),
        backgroundColor: data.map((_, index) => COLORS[index % COLORS.length]),
        borderColor: "#ffffff", // white card background (surface-card)
        borderWidth: 2,
        hoverOffset: 4,
        hoverBorderWidth: 3,
      },
    ],
  };

  // Chart options
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: doughnut ? `${cutout}%` : 0,
    onClick: (event, elements) => {
      if (elements.length > 0 && onSegmentClick) {
        const index = elements[0].index;
        const clickedData = data[index];
        onSegmentClick({ ...clickedData, fullData: clickedData });
      }
    },
    plugins: {
      // FR-019: no chart legends — DashboardView renders its own swatch/legend row.
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.label || "";
            const value = context.parsed;
            const total = context.dataset.data.reduce(
              (sum, val) => sum + val,
              0,
            );
            const percentage = ((value / total) * 100).toFixed(1);

            return `${label}: ${value.toLocaleString()} (${percentage}%)`;
          },
        },
      },
    },
    // Touch interactions
    interaction: {
      mode: "nearest",
    },
  };

  return (
    <ChartWrapper
      type={doughnut ? "doughnut" : "pie"}
      data={chartData}
      options={options}
      title={title}
      enableHorizontalScroll={false}
    />
  );
}

PieChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string,
      label: PropTypes.string,
      value: PropTypes.number,
    }),
  ).isRequired,
  title: PropTypes.string,
  onSegmentClick: PropTypes.func,
  doughnut: PropTypes.bool,
  cutout: PropTypes.number,
};

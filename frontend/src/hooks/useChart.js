/**
 * useChart Hook - Chart.js Initialization and Configuration
 *
 * Custom hook for Chart.js initialization with mobile-optimized settings,
 * touch interactions, responsive behavior, and performance optimizations.
 *
 * @module hooks/useChart
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { Chart, registerables } from "chart.js";
import { debounce } from "@/utils/performance";

// Register Chart.js components
Chart.register(...registerables);

// Make Bold Solutions brand type for all charts (FR-019).
Chart.defaults.font.family =
  '"Inter Tight", system-ui, -apple-system, sans-serif';
Chart.defaults.color = "#56544f"; // --ink-600

/**
 * Default Chart.js configuration optimized for mobile
 */
const DEFAULT_CONFIG = {
  responsive: true,
  maintainAspectRatio: false,
  devicePixelRatio: window.devicePixelRatio || 1,
  interaction: {
    mode: "index",
    intersect: false,
  },
  plugins: {
    legend: {
      display: true,
      position: "bottom",
      labels: {
        padding: 16,
        font: {
          size: 14,
        },
        usePointStyle: true,
        boxWidth: 8,
        boxHeight: 8,
      },
    },
    tooltip: {
      enabled: true,
      mode: "index",
      intersect: false,
      backgroundColor: "rgba(0, 0, 0, 0.9)",
      titleColor: "#ffffff",
      bodyColor: "#ffffff",
      borderColor: "rgba(255, 255, 255, 0.2)",
      borderWidth: 1,
      cornerRadius: 8,
      padding: 12,
      displayColors: true,
      callbacks: {
        title: (context) => {
          return context[0]?.label || "";
        },
        label: (context) => {
          const label = context.dataset.label || "";
          const value =
            context.parsed.y !== null ? context.parsed.y : context.parsed;
          return `${label}: ${typeof value === "number" ? value.toLocaleString() : value}`;
        },
      },
      // Touch-optimized tooltip positioning
      position: "average",
      yAlign: "bottom", // Position above finger to avoid occlusion
      xAlign: "center",
    },
  },
  scales: {
    x: {
      grid: {
        display: false,
      },
      ticks: {
        font: {
          size: 12,
        },
        maxRotation: 45,
        minRotation: 0,
        autoSkip: true,
        maxTicksLimit: 10,
      },
    },
    y: {
      beginAtZero: true,
      grid: {
        color: "rgba(0, 0, 0, 0.05)",
        drawBorder: false,
      },
      ticks: {
        font: {
          size: 12,
        },
        callback: (value) => {
          if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + "M";
          } else if (value >= 1000) {
            return (value / 1000).toFixed(1) + "K";
          }
          return value;
        },
      },
    },
  },
  animation: {
    duration: 750,
    easing: "easeInOutQuart",
  },
};

/**
 * Touch-and-hold tooltip handler
 * Shows tooltip on long press to avoid finger occlusion
 */
class TouchAndHoldPlugin {
  constructor() {
    this.touchTimeout = null;
    this.touchStartTime = 0;
    this.touchPosition = null;
  }

  beforeEvent(chart, args) {
    const event = args.event;

    if (event.type === "touchstart") {
      this.touchStartTime = Date.now();
      this.touchPosition = { x: event.x, y: event.y };

      // Clear existing timeout
      if (this.touchTimeout) {
        clearTimeout(this.touchTimeout);
      }

      // Show tooltip after 300ms hold
      this.touchTimeout = setTimeout(() => {
        if (chart.tooltip) {
          const activeElements = chart.getElementsAtEventForMode(
            event,
            "nearest",
            { intersect: false },
            false,
          );

          if (activeElements.length > 0) {
            chart.tooltip.setActiveElements(activeElements);
            chart.update("none");
          }
        }
      }, 300);
    } else if (event.type === "touchmove") {
      // Cancel if finger moves too much
      if (this.touchPosition) {
        const distance = Math.sqrt(
          Math.pow(event.x - this.touchPosition.x, 2) +
            Math.pow(event.y - this.touchPosition.y, 2),
        );
        if (distance > 10) {
          clearTimeout(this.touchTimeout);
        }
      }
    } else if (event.type === "touchend" || event.type === "touchcancel") {
      clearTimeout(this.touchTimeout);
      this.touchPosition = null;
    }
  }
}

const touchAndHoldPlugin = new TouchAndHoldPlugin();

/**
 * Custom hook for Chart.js initialization
 *
 * @param {Object} chartConfig - Chart configuration object
 * @param {string} chartConfig.type - Chart type: 'bar' | 'line' | 'pie' | 'doughnut'
 * @param {Object} chartConfig.data - Chart data (labels, datasets)
 * @param {Object} [chartConfig.options] - Additional Chart.js options
 * @param {boolean} [chartConfig.enableTouchAndHold=true] - Enable touch-and-hold tooltips
 * @param {number} [chartConfig.debounceDelay=150] - Debounce delay for resize (ms)
 *
 * @returns {Object} - Chart instance and utility functions
 * @returns {React.RefObject} returns.canvasRef - Canvas ref to attach
 * @returns {Chart|null} returns.chartInstance - Chart.js instance
 * @returns {Function} returns.updateChart - Function to update chart data
 * @returns {Function} returns.destroyChart - Function to destroy chart
 *
 * @example
 * const { canvasRef, updateChart } = useChart({
 *   type: 'bar',
 *   data: { labels: [...], datasets: [...] },
 *   options: { scales: { y: { beginAtZero: true } } }
 * });
 *
 * return <canvas ref={canvasRef} />;
 */
export const useChart = (chartConfig) => {
  const canvasRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const [isReady, setIsReady] = useState(false);

  const {
    type,
    data,
    options = {},
    enableTouchAndHold = true,
    debounceDelay = 150,
  } = chartConfig;

  /**
   * Merge default config with user options
   */
  const mergedOptions = useCallback(() => {
    const merged = {
      ...DEFAULT_CONFIG,
      ...options,
      plugins: {
        ...DEFAULT_CONFIG.plugins,
        ...options.plugins,
        tooltip: {
          ...DEFAULT_CONFIG.plugins.tooltip,
          ...options.plugins?.tooltip,
        },
        legend: {
          ...DEFAULT_CONFIG.plugins.legend,
          ...options.plugins?.legend,
        },
      },
      scales: {
        ...DEFAULT_CONFIG.scales,
        ...options.scales,
      },
    };

    // Remove scales for pie/doughnut charts
    if (type === "pie" || type === "doughnut") {
      delete merged.scales;
    }

    return merged;
  }, [type, options]);

  /**
   * Initialize chart
   */
  const initChart = useCallback(() => {
    if (!canvasRef.current || !data) return;

    // Destroy existing chart
    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
    }

    try {
      const ctx = canvasRef.current.getContext("2d");

      const config = {
        type,
        data,
        options: mergedOptions(),
        plugins: enableTouchAndHold ? [touchAndHoldPlugin] : [],
      };

      chartInstanceRef.current = new Chart(ctx, config);
      setIsReady(true);
    } catch (error) {
      console.error("Error initializing chart:", error);
    }
  }, [type, data, mergedOptions, enableTouchAndHold]);

  /**
   * Update chart data
   */
  const updateChart = useCallback((newData) => {
    if (!chartInstanceRef.current) return;

    try {
      chartInstanceRef.current.data = newData;
      chartInstanceRef.current.update("active");
    } catch (error) {
      console.error("Error updating chart:", error);
    }
  }, []);

  /**
   * Destroy chart
   */
  const destroyChart = useCallback(() => {
    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
      chartInstanceRef.current = null;
      setIsReady(false);
    }
  }, []);

  /**
   * Handle window resize with debouncing
   */
  useEffect(() => {
    const handleResize = debounce(() => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.resize();
      }
    }, debounceDelay);

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [debounceDelay]);

  /**
   * Initialize chart on mount or when config changes
   */
  useEffect(() => {
    // Defer chart initialization until next tick
    const timer = setTimeout(() => {
      initChart();
    }, 0);

    return () => {
      clearTimeout(timer);
      destroyChart();
    };
  }, [initChart, destroyChart]);

  /**
   * Update chart when data changes
   */
  useEffect(() => {
    if (isReady && data) {
      updateChart(data);
    }
  }, [data, isReady, updateChart]);

  return {
    canvasRef,
    updateChart,
    destroyChart,
    isReady,
  };
};

/**
 * Hook for responsive chart sizing based on viewport
 *
 * @param {Object} options - Sizing options
 * @param {number} [options.minHeight=300] - Minimum chart height (px)
 * @param {number} [options.maxHeight=600] - Maximum chart height (px)
 * @param {number} [options.mobileAspectRatio=1.5] - Aspect ratio for mobile (width/height)
 * @param {number} [options.desktopAspectRatio=2] - Aspect ratio for desktop
 * @param {number} [options.breakpoint=768] - Mobile breakpoint (px)
 *
 * @returns {Object} - Chart dimensions
 * @returns {number} returns.width - Chart width
 * @returns {number} returns.height - Chart height
 *
 * @example
 * const { width, height } = useResponsiveChartSize();
 * return <canvas width={width} height={height} />;
 */
export const useResponsiveChartSize = (options = {}) => {
  const {
    minHeight = 300,
    maxHeight = 600,
    mobileAspectRatio = 1.5,
    desktopAspectRatio = 2,
    breakpoint = 768,
  } = options;

  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: minHeight,
  });

  useEffect(() => {
    const calculateDimensions = () => {
      const isMobile = window.innerWidth < breakpoint;
      const containerWidth = Math.min(window.innerWidth - 32, 1200); // 16px padding each side
      const aspectRatio = isMobile ? mobileAspectRatio : desktopAspectRatio;

      let height = containerWidth / aspectRatio;
      height = Math.max(minHeight, Math.min(maxHeight, height));

      setDimensions({
        width: containerWidth,
        height,
      });
    };

    const debouncedCalculate = debounce(calculateDimensions, 150);

    calculateDimensions();
    window.addEventListener("resize", debouncedCalculate);

    return () => {
      window.removeEventListener("resize", debouncedCalculate);
    };
  }, [minHeight, maxHeight, mobileAspectRatio, desktopAspectRatio, breakpoint]);

  return dimensions;
};

export default useChart;

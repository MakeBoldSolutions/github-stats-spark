import React, { useState, useMemo, Suspense, lazy, useEffect } from "react";
import { ViewportProvider } from "@/contexts/ViewportContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import useRepositoryData from "@/hooks/useRepositoryData";
import LoadingState from "@/components/Common/LoadingState";
import FilterControls from "@/components/Common/FilterControls";
import ThemeToggle from "@/components/Common/ThemeToggle";
import ContributionHeatmap from "@/components/Visualizations/ContributionHeatmap";
const ActivityTimeline = lazy(
  () => import("@/components/Visualizations/ActivityTimeline"),
);
import ProfileHero from "@/components/ProfileHero/ProfileHero";
import RepositoryGrid from "@/components/RepositoryGrid/RepositoryGrid";
import { useTableSort } from "@/hooks/useTableSort";
import {
  extractLanguages,
  setupBackgroundSync,
  clearCache,
} from "@/services/dataService";
import { deferExecution, getConnectionType } from "@/utils/performance";
import TabBar from "@/components/Mobile/TabBar/TabBar";
import { ToastContainer } from "@/components/Mobile/Toast/Toast";

// SIZE JUSTIFICATION (Constitution I — ~530 LOC as of 2026-05-12):
// App composes routing/state orchestration for all major dashboard views
// (table, visualizations, attention, and drill-down) with shared URL sync,
// filtering, and loading/error flows. This keeps cross-view navigation logic
// centralized while feature components remain split into dedicated modules.

const DashboardView = lazy(
  () => import("@/components/Visualizations/DashboardView"),
);
const AttentionView = lazy(
  () => import("@/components/Attention/AttentionView"),
);
const RepositoryDetail = lazy(
  () => import("@/components/DrillDown/RepositoryDetail"),
);

/**
 * GitHub Stats Spark Dashboard - Root App Component
 *
 * This is the main application component that orchestrates the dashboard layout,
 * state management, and routing between dashboard, visualizations, and attention views.
 *
 * Features:
 * - Data fetching via useRepositoryData custom hook
 * - View state management: Dashboard (table) and Visualizations
 * - URL hash routing for navigation
 * - Modal state for repository drill-down details
 * - Loading and error state handling
 *
 * @component
 */
function App() {
  // Data fetching with custom hook
  const { data, loading, error, refetch } = useRepositoryData();

  // Toast notifications state
  const [toasts, setToasts] = useState([]);

  /**
   * Add a toast notification
   */
  const addToast = (message, variant = "info", duration = 3000) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, variant, duration }]);
  };

  /**
   * Remove a toast notification
   */
  const removeToast = (id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  // Performance optimization on mount
  useEffect(() => {
    // Check connection type for adaptive loading
    const connectionType = getConnectionType();

    // Log connection info in development
    if (import.meta.env.DEV) {
      console.log("[Performance] Connection type:", connectionType);
    }

    // Defer non-critical operations based on connection quality
    if (connectionType !== "2g" && connectionType !== "slow-2g") {
      deferExecution(() => {
        // Preload visualization components for faster navigation
      }, 3000);
    }
  }, []);

  // Setup background sync for offline/online transitions
  useEffect(() => {
    const cleanup = setupBackgroundSync(() => {
      console.log("[App] Data refreshed after coming online");
      addToast("Data refreshed successfully", "success", 3000);
    });

    return cleanup;
  }, []);

  // Listen for service worker update notifications
  useEffect(() => {
    const handleSwUpdate = (event) => {
      const worker = event.detail?.worker;
      addToast(
        "A new version is available. Click to update.",
        "info",
        0, // 0 = persistent until dismissed
      );
      // Store the worker so the user can trigger the update on demand
      window.__pendingSwWorker = worker;
    };

    window.addEventListener("sw-update-available", handleSwUpdate);
    return () =>
      window.removeEventListener("sw-update-available", handleSwUpdate);
  }, []);

  // View state management - initialize from URL hash or default to table
  const getInitialView = () => {
    const hash = window.location.hash.slice(1); // Remove the # character
    if (hash === "visualizations") return "visualizations";
    if (hash === "attention") return "attention";
    return "table"; // Default to table/dashboard view
  };

  const [currentView, setCurrentView] = useState(getInitialView());
  const [detailModalRepo, setDetailModalRepo] = useState(null); // For drill-down

  // Sync view with URL hash
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      if (hash === "visualizations") {
        setCurrentView("visualizations");
      } else if (hash === "attention") {
        setCurrentView("attention");
      } else if (hash === "table" || hash === "dashboard" || hash === "") {
        setCurrentView("table");
      }
      // Ignore other hashes like #main-content (skip links)
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Update URL hash when view changes
  const handleViewChange = (view) => {
    setCurrentView(view);
    if (view === "visualizations") {
      window.location.hash = "visualizations";
      return;
    }
    if (view === "attention") {
      window.location.hash = "attention";
      return;
    }
    window.location.hash = "";
  };

  // Table sorting and filtering using useTableSort hook
  const {
    sortedData: processedRepositories,
    filterLanguage,
    handleFilterChange,
    clearFilter,
  } = useTableSort(data?.repositories || [], "stars", "desc");

  /**
   * Handle repository drill-down
   * @param {Object} repository - Repository object to display details for
   */
  const handleRepoClick = (repository) => {
    setDetailModalRepo(repository);
  };

  /**
   * Close detail modal
   */
  const closeDetailModal = () => {
    setDetailModalRepo(null);
  };

  /**
   * Get available languages for filter dropdown
   */
  const availableLanguages = useMemo(() => {
    if (!data?.repositories) return [];
    return extractLanguages(data.repositories);
  }, [data]);

  /**
   * Navigate to next repository in detail view
   */
  const handleNextRepo = () => {
    if (!detailModalRepo || !processedRepositories) return;
    const currentIndex = processedRepositories.findIndex(
      (r) => r.name === detailModalRepo.name,
    );
    if (currentIndex < processedRepositories.length - 1) {
      setDetailModalRepo(processedRepositories[currentIndex + 1]);
    }
  };

  /**
   * Navigate to previous repository in detail view
   */
  const handlePreviousRepo = () => {
    if (!detailModalRepo || !processedRepositories) return;
    const currentIndex = processedRepositories.findIndex(
      (r) => r.name === detailModalRepo.name,
    );
    if (currentIndex > 0) {
      setDetailModalRepo(processedRepositories[currentIndex - 1]);
    }
  };

  const formatGeneratedAt = (timestamp) => {
    if (!timestamp) return "Unknown";
    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) return "Unknown";
    return parsed.toLocaleString();
  };

  const handleForceRefresh = async () => {
    try {
      await clearCache();
      await refetch({ forceRefresh: true, cacheBust: true });
      addToast("Data refreshed and cache cleared", "success", 3000);
    } catch {
      addToast("Refresh failed. Check the console for details.", "error", 4000);
    }
  };

  return (
    <ThemeProvider>
      <ViewportProvider>
        <div className="app">
          {/* Header */}
          <header className="header" role="banner">
            <div className="container">
              <div
                className="flex items-center justify-between"
                style={{ height: "var(--header-height)" }}
              >
                <a
                  href="/"
                  className="header-brand"
                  aria-label="GitHubSpark — home"
                >
                  <div className="header-logo" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.42-1.305.763-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.49 11.49 0 013.006-.404c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.91 1.235 3.22 0 4.61-2.807 5.625-5.479 5.92.43.372.824 1.102.824 2.222 0 1.606-.015 2.898-.015 3.293 0 .322.216.694.825.576C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                  </div>
                  <div className="header-title-group">
                    <span className="header-title-main">GitHubSpark</span>
                    <span className="header-title-sub">
                      {data?.profile?.username || "MakeBoldSolutions"}
                    </span>
                  </div>
                </a>

                {/* Navigation Menu */}
                <nav
                  className="nav-menu"
                  id="navigation"
                  aria-label="Main navigation"
                >
                  <button
                    className={`nav-menu-item ${currentView === "table" ? "nav-menu-item--active" : ""}`}
                    onClick={() => handleViewChange("table")}
                    aria-current={currentView === "table" ? "page" : undefined}
                    aria-label="Switch to repository overview"
                  >
                    Overview
                  </button>
                  <button
                    className={`nav-menu-item ${currentView === "visualizations" ? "nav-menu-item--active" : ""}`}
                    onClick={() => handleViewChange("visualizations")}
                    aria-current={
                      currentView === "visualizations" ? "page" : undefined
                    }
                    aria-label="Insights — switch to visualizations view"
                  >
                    Insights
                  </button>
                  <button
                    className={`nav-menu-item ${currentView === "attention" ? "nav-menu-item--active" : ""}`}
                    onClick={() => handleViewChange("attention")}
                    aria-current={
                      currentView === "attention" ? "page" : undefined
                    }
                    aria-label="Health — repositories needing attention"
                  >
                    Health
                  </button>
                  <ThemeToggle />
                </nav>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main
            className="main"
            id="main-content"
            role="main"
            aria-label="Main content"
          >
            <div className="container">
              <div className="mt-xl mb-xl">
                {/* Loading State */}
                {loading && (
                  <LoadingState
                    message="Loading repository data..."
                    size="large"
                  />
                )}

                {/* Error State */}
                {error && !loading && (
                  <div
                    className="card"
                    style={{
                      backgroundColor: "var(--color-error)",
                      color: "white",
                    }}
                  >
                    <h3>Error Loading Data</h3>
                    <p>{error.message || "Failed to load repository data"}</p>
                    <p className="text-sm">
                      {navigator.onLine
                        ? "Please check your network connection and try again."
                        : "You are offline. Cached data may be available when you reconnect."}
                    </p>
                    <button
                      className="btn btn-primary mt-md"
                      onClick={() => window.location.reload()}
                    >
                      Retry
                    </button>
                  </div>
                )}

                {/* Data Loaded - Render Current View */}
                {!loading && !error && data && (
                  <>
                    {currentView === "table" && (
                      <section aria-labelledby="repository-overview-heading">
                        {/* Profile Hero */}
                        <ProfileHero profile={data?.profile} />

                        {/* Contribution heatmap for trailing 365-day activity */}
                        {data?.profile?.activity_calendar && (
                          <div className="mb-lg">
                            <h2
                              className="text-sm text-muted"
                              style={{ marginBottom: "0.5rem" }}
                            >
                              Contribution Activity (trailing 365 days)
                            </h2>
                            <ContributionHeatmap
                              activityCalendar={data.profile.activity_calendar}
                            />
                          </div>
                        )}

                        {/* Repository Grid */}
                        <RepositoryGrid
                          repositories={data.repositories || []}
                          onRepoClick={handleRepoClick}
                        />
                      </section>
                    )}

                    {currentView === "visualizations" && (
                      <section
                        className="view-transition"
                        aria-labelledby="visualizations-heading"
                      >
                        <div className="mb-lg">
                          <h2 id="visualizations-heading">
                            Repository Insights
                          </h2>
                          <p
                            className="text-muted"
                            role="status"
                            aria-live="polite"
                          >
                            Showing {processedRepositories.length} repositories
                            {filterLanguage && ` filtered by ${filterLanguage}`}
                          </p>
                        </div>

                        {availableLanguages.length > 0 && (
                          <FilterControls
                            languages={availableLanguages}
                            selectedLanguage={filterLanguage}
                            onFilterChange={handleFilterChange}
                            onClearFilter={clearFilter}
                          />
                        )}

                        <Suspense
                          fallback={
                            <LoadingState message="Loading visualizations..." />
                          }
                        >
                          <DashboardView
                            repositories={processedRepositories}
                            profile={data?.profile}
                            onRepoClick={handleRepoClick}
                          />
                        </Suspense>

                        {/* Weekly activity timeline visualization */}
                        {data?.profile?.weekly_activity?.length > 0 && (
                          <div className="card mt-lg">
                            <h3 style={{ marginBottom: "0.75rem" }}>
                              Weekly Activity Timeline
                            </h3>
                            <Suspense
                              fallback={
                                <LoadingState message="Loading timeline..." />
                              }
                            >
                              <ActivityTimeline
                                weeklyActivity={data.profile.weekly_activity}
                              />
                            </Suspense>
                          </div>
                        )}
                      </section>
                    )}

                    {currentView === "attention" && (
                      <section
                        className="view-transition"
                        aria-labelledby="attention-heading"
                      >
                        <div className="mb-lg">
                          <h2 id="attention-heading">
                            Repositories Needing Attention
                          </h2>
                          <p
                            className="text-muted"
                            role="status"
                            aria-live="polite"
                          >
                            Ranked by pull request pressure, security findings,
                            staleness, and dependency health
                          </p>
                        </div>

                        {availableLanguages.length > 0 && (
                          <FilterControls
                            languages={availableLanguages}
                            selectedLanguage={filterLanguage}
                            onFilterChange={handleFilterChange}
                            onClearFilter={clearFilter}
                          />
                        )}

                        <Suspense
                          fallback={
                            <LoadingState message="Loading attention view..." />
                          }
                        >
                          <AttentionView
                            repositories={processedRepositories}
                            onRepoClick={handleRepoClick}
                          />
                        </Suspense>
                      </section>
                    )}
                  </>
                )}
              </div>
            </div>
          </main>

          {/* Mobile TabBar Navigation */}
          <TabBar activeTab={currentView} onTabChange={handleViewChange} />

          {/* Footer */}
          <footer className="footer" role="contentinfo">
            <div className="container">
              <div className="footer-inner">
                <div className="footer-left">
                  <div className="footer-brand">
                    <span className="footer-brand-name">GitHubSpark</span>
                    <span className="footer-brand-sep">·</span>
                    <a
                      href="https://github-stats.makeboldspark.com"
                      className="footer-brand-url"
                    >
                      github-stats.makeboldspark.com
                    </a>
                  </div>
                  <p className="footer-copy">
                    Built by{" "}
                    <a
                      href="https://markhazleton.com"
                      rel="author"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Mark Hazleton
                    </a>
                    {" · "}
                    <a
                      href="https://makeboldsolutions.com"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Make Bold Solutions
                    </a>
                    {" · "}
                    <a
                      href="https://makeboldspark.com"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Make Bold Spark
                    </a>
                  </p>
                </div>
                <div className="footer-right">
                  {data?.metadata && (
                    <p className="footer-meta">
                      Data: {formatGeneratedAt(data.metadata.generated_at)}
                    </p>
                  )}
                  <button
                    className="btn btn-secondary footer-refresh-btn"
                    onClick={handleForceRefresh}
                    disabled={loading}
                    aria-label="Force refresh repositories data"
                  >
                    {loading ? "Refreshing…" : "↻ Refresh"}
                  </button>
                </div>
              </div>
            </div>
          </footer>

          {/* Detail Modal (for drill-down) */}
          {detailModalRepo && (
            <Suspense fallback={<LoadingState message="Loading details..." />}>
              <RepositoryDetail
                repository={detailModalRepo}
                onClose={closeDetailModal}
                onNext={handleNextRepo}
                onPrevious={handlePreviousRepo}
              />
            </Suspense>
          )}

          {/* Toast Notifications */}
          <ToastContainer toasts={toasts} onRemove={removeToast} />
        </div>
      </ViewportProvider>
    </ThemeProvider>
  );
}

export default App;

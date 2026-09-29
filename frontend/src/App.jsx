import React, { Suspense, lazy } from "react";
import { ViewportProvider } from "@/contexts/ViewportContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import useRepositoryData from "@/hooks/useRepositoryData";
import { useDashboardShell } from "@/hooks/useDashboardShell";
import LoadingState from "@/components/Common/LoadingState";
import FilterControls from "@/components/Common/FilterControls";
import ContributionHeatmap from "@/components/Visualizations/ContributionHeatmap";
import ProfileHero from "@/components/ProfileHero/ProfileHero";
import { Eyebrow, Card, Button } from "@/components/Brand";
import { RefreshCw } from "lucide-react";
import RepositoryGrid from "@/components/RepositoryGrid/RepositoryGrid";
import TabBar from "@/components/Mobile/TabBar/TabBar";
import { OfflineIndicator } from "@/components/Mobile/OfflineIndicator/OfflineIndicator";
import { ToastContainer } from "@/components/Mobile/Toast/Toast";

// SIZE JUSTIFICATION (Constitution I): App composes routing/layout for the
// three primary views and delegates all cross-cutting state (toasts, view
// routing, active result list, refresh) to useDashboardShell.

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
 * Composes the dashboard shell (header/nav, main content, footer, drawer,
 * toasts) around the three primary views. All cross-cutting state lives in
 * useDashboardShell so this component stays presentational.
 *
 * @component
 */
function App() {
  const { data, loading, error, refetch } = useRepositoryData();

  const {
    toasts,
    addToast,
    removeToast,
    currentView,
    handleViewChange,
    processedRepositories,
    filterLanguage,
    handleFilterChange,
    clearFilter,
    availableLanguages,
    selectedRepo,
    activeResultList,
    handleRepoClick,
    closeDetail,
    handleNextRepo,
    handlePreviousRepo,
    formatGeneratedAt,
    handleForceRefresh,
  } = useDashboardShell({ data, refetch });

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
                    <img src="/logo-mark.svg" alt="" width="28" height="28" />
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
                </nav>
              </div>
            </div>
            <OfflineIndicator onRetry={() => refetch({ cacheBust: false })} />
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
                  <Card accent padding="lg">
                    <h3>Error loading data</h3>
                    <p>{error.message || "Failed to load repository data"}</p>
                    <p className="text-sm text-muted">
                      {navigator.onLine
                        ? "Please check your network connection and try again."
                        : "You are offline. Cached data may be available when you reconnect."}
                    </p>
                    <Button
                      variant="primary"
                      size="md"
                      className="mt-md"
                      onClick={() => window.location.reload()}
                    >
                      Retry
                    </Button>
                  </Card>
                )}

                {/* Data Loaded - Render Current View */}
                {!loading && !error && data && (
                  <>
                    {currentView === "table" && (
                      <section aria-labelledby="repository-overview-heading">
                        {/* Profile Hero */}
                        <ProfileHero
                          profile={data?.profile}
                          generatedAt={data?.metadata?.generated_at}
                        />

                        {/* Contribution heatmap for trailing 365-day activity */}
                        {data?.profile?.activity_calendar && (
                          <div className="mb-lg">
                            <ContributionHeatmap
                              activityCalendar={data.profile.activity_calendar}
                              generatedAt={data?.metadata?.generated_at}
                            />
                          </div>
                        )}

                        {/* Repository Grid */}
                        <RepositoryGrid
                          repositories={data.repositories || []}
                          onRepoClick={handleRepoClick}
                          onToast={addToast}
                        />
                      </section>
                    )}

                    {currentView === "visualizations" && (
                      <section
                        className="view-transition"
                        aria-labelledby="visualizations-heading"
                      >
                        <div className="mb-lg">
                          <Eyebrow>Insights</Eyebrow>
                          <h2 id="visualizations-heading">
                            Repository insights
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
                            onRepoClick={(repo) =>
                              handleRepoClick(repo, processedRepositories)
                            }
                          />
                        </Suspense>
                      </section>
                    )}

                    {currentView === "attention" && (
                      <section
                        className="view-transition"
                        aria-labelledby="attention-heading"
                      >
                        <div className="mb-lg">
                          <Eyebrow>Health</Eyebrow>
                          <h2 id="attention-heading">
                            Repositories needing attention
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
                            onToast={addToast}
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
                    <RefreshCw
                      size={14}
                      aria-hidden="true"
                      className={loading ? "spin" : undefined}
                    />
                    {loading ? "Refreshing…" : "Refresh"}
                  </button>
                </div>
              </div>
            </div>
          </footer>

          {/* Detail Drawer (drill-down) */}
          {selectedRepo && (
            <Suspense fallback={<LoadingState message="Loading details..." />}>
              <RepositoryDetail
                repository={selectedRepo}
                onClose={closeDetail}
                onNext={handleNextRepo}
                onPrevious={handlePreviousRepo}
                resultIndex={activeResultList.findIndex(
                  (r) => r.name === selectedRepo.name,
                )}
                resultTotal={activeResultList.length}
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

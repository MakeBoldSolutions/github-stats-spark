import React, { Suspense, lazy, useCallback, useMemo } from "react";
import { ViewportProvider } from "@/contexts/ViewportContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import useRepositoryData from "@/hooks/useRepositoryData";
import { sameRepo, useDashboardShell } from "@/hooks/useDashboardShell";
import usePortfolio from "@/hooks/usePortfolio";
import useScope from "@/hooks/useScope";
import useAdminAvailable from "@/hooks/useAdminAvailable";
import useDependabot from "@/hooks/useDependabot";
import LoadingState from "@/components/Common/LoadingState";
import FilterControls from "@/components/Common/FilterControls";
import PageHeader from "@/components/Common/PageHeader";
import ContributionHeatmap from "@/components/Visualizations/ContributionHeatmap";
import ProfileHero from "@/components/ProfileHero/ProfileHero";
import { Card, Button } from "@/components/Brand";
import RepositoryGrid from "@/components/RepositoryGrid/RepositoryGrid";
import TabBar from "@/components/Mobile/TabBar/TabBar";
import EmptyState from "@/components/Mobile/EmptyState/EmptyState";
import AppHeader from "@/components/Shell/AppHeader";
import AppFooter from "@/components/Shell/AppFooter";
import { ToastContainer } from "@/components/Mobile/Toast/Toast";
import { visibleSections } from "@/config/sections";
import {
  EMPTY_SCOPE,
  fullNameOf,
  isWholePortfolio,
  repoKey,
  scopeLabel,
  scopedRepoKeys,
} from "@/utils/scope";
import {
  alertsForRepository,
  scopeAlertFile,
  storedCoverage,
  withStoredAlerts,
} from "@/utils/storedAlerts";

// Composes the shell (header, sections, footer, drawer, toasts). Data
// loading lives in the hooks and utils above; cross-cutting view state in
// useDashboardShell, so this file stays compositional.

const DashboardView = lazy(
  () => import("@/components/Visualizations/DashboardView"),
);
const AttentionView = lazy(
  () => import("@/components/Attention/AttentionView"),
);
const SourcesView = lazy(() => import("@/components/Admin/SourcesView"));
const SecurityView = lazy(() => import("@/components/Security/SecurityView"));
const RepositoryDetail = lazy(
  () => import("@/components/DrillDown/RepositoryDetail"),
);

/**
 * GitHub Stats Spark Dashboard - Root App Component
 *
 * Public (GitHub Pages): one profile, Overview, Insights and Health.
 * Self-hosted (a portfolio.json exists): a scope selector that every
 * section follows, alert counts from the stored Dependabot alerts, and the
 * Security and Admin sections when their data is available.
 *
 * @component
 */
function App() {
  const { loading: portfolioLoading, portfolio } = usePortfolio();
  const [scope, setScope] = useScope();
  const selfHosted = Boolean(portfolio);
  const {
    data: collected,
    loading: dataLoading,
    error: dataError,
    refetch,
  } = useRepositoryData({
    portfolio,
    portfolioLoading,
    scope: selfHosted ? scope : null,
  });
  const adminAvailable = useAdminAvailable();
  const alertFile = useDependabot();

  // One source per number: stored alerts replace the collected summary.
  const data = useMemo(() => {
    if (!collected || !alertFile) return collected;
    const coverage = storedCoverage(alertFile);
    return {
      ...collected,
      repositories: collected.repositories.map((repo) =>
        withStoredAlerts(repo, coverage),
      ),
    };
  }, [collected, alertFile]);

  const scopeKeys = useMemo(
    () =>
      selfHosted && !isWholePortfolio(scope)
        ? scopedRepoKeys(portfolio, scope)
        : null,
    [selfHosted, portfolio, scope],
  );
  const scopedAlerts = useMemo(
    () => scopeAlertFile(alertFile, scopeKeys),
    [alertFile, scopeKeys],
  );

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

  const sections = visibleSections({
    security: Boolean(alertFile),
    admin: adminAvailable,
  });
  const header = selfHosted
    ? {
        scope: scopeLabel(scope, portfolio),
        freshness: [
          { label: "Repository data", at: data?.metadata?.generated_at },
          ...(alertFile
            ? [{ label: "Security", at: alertFile.generated_at }]
            : []),
        ],
      }
    : {};

  const openRepository = useCallback(
    (fullName) => {
      const key = repoKey(fullName);
      const list = data?.repositories || [];
      const found = list.find((repo) => repoKey(fullNameOf(repo)) === key);
      if (found) {
        handleRepoClick(found, list);
        return;
      }
      const entry = alertFile?.repositories.find(
        (repo) => repoKey(repo.full_name) === key,
      );
      handleRepoClick(
        {
          name: fullName.split("/").pop(),
          full_name: fullName,
          url: entry?.html_url,
        },
        [],
      );
    },
    [data, alertFile, handleRepoClick],
  );

  // Admin and Security do not depend on dashboard data, so a data failure must not hide them.
  const onAdminView = adminAvailable && currentView === "admin";
  const onSecurityView = currentView === "security";
  const standaloneView = onAdminView || onSecurityView;
  const loading = (dataLoading || portfolioLoading) && !standaloneView;
  const error = standaloneView ? null : dataError;
  const emptyScope =
    selfHosted && data && (data.repositories || []).length === 0;

  return (
    <ThemeProvider>
      <ViewportProvider>
        <div className="app">
          <AppHeader
            sections={sections}
            currentView={currentView}
            onViewChange={handleViewChange}
            subtitle={
              selfHosted ? null : data?.profile?.username || "MakeBoldSolutions"
            }
            portfolio={portfolio}
            scope={scope}
            onScopeChange={setScope}
            onRetry={() => refetch({ cacheBust: false })}
          />

          <main
            className="main"
            id="main-content"
            role="main"
            aria-label="Main content"
          >
            <div className="container">
              <div className="mt-xl mb-xl">
                {onAdminView && (
                  <Suspense
                    fallback={<LoadingState message="Loading admin..." />}
                  >
                    <SourcesView onToast={addToast} />
                  </Suspense>
                )}

                {onSecurityView && (
                  <section aria-labelledby="security-heading">
                    <PageHeader
                      eyebrow="Security"
                      title="Dependabot alerts"
                      titleId="security-heading"
                      {...header}
                    />
                    {scopedAlerts ? (
                      <Suspense
                        fallback={
                          <LoadingState message="Loading security view..." />
                        }
                      >
                        <SecurityView
                          file={scopedAlerts}
                          onToast={addToast}
                          onOpenRepository={openRepository}
                        />
                      </Suspense>
                    ) : (
                      <p className="text-muted" role="status">
                        Dependabot data is not available in this deployment yet.
                      </p>
                    )}
                  </section>
                )}

                {loading && !standaloneView && (
                  <LoadingState
                    message="Loading repository data..."
                    size="large"
                  />
                )}

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

                {!loading &&
                  !error &&
                  data &&
                  !standaloneView &&
                  emptyScope && (
                    <EmptyState
                      title="No repositories in this scope"
                      description="Nothing collected matches the client, source, repository and filters chosen above."
                      actionLabel="Show the whole portfolio"
                      onAction={() => setScope(EMPTY_SCOPE)}
                    />
                  )}

                {!loading &&
                  !error &&
                  data &&
                  !standaloneView &&
                  !emptyScope && (
                    <>
                      {currentView === "table" && (
                        <section aria-labelledby="repository-overview-heading">
                          {selfHosted && !data.profile && (
                            <PageHeader
                              eyebrow="Overview"
                              title="Portfolio"
                              titleId="repository-overview-heading"
                              {...header}
                            />
                          )}
                          <ProfileHero
                            profile={data?.profile}
                            generatedAt={data?.metadata?.generated_at}
                          />

                          {data?.profile?.activity_calendar && (
                            <div className="mb-lg">
                              <ContributionHeatmap
                                activityCalendar={
                                  data.profile.activity_calendar
                                }
                                generatedAt={data?.metadata?.generated_at}
                              />
                            </div>
                          )}

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
                          <PageHeader
                            eyebrow="Insights"
                            title="Repository insights"
                            titleId="visualizations-heading"
                            description={
                              <>
                                Showing {processedRepositories.length}{" "}
                                repositories
                                {filterLanguage &&
                                  ` filtered by ${filterLanguage}`}
                              </>
                            }
                            {...header}
                          />

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
                          <PageHeader
                            eyebrow="Health"
                            title="Repositories needing attention"
                            titleId="attention-heading"
                            description="Ranked by pull request pressure, security findings, staleness, and dependency health"
                            {...header}
                          />

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

          <TabBar
            activeTab={currentView}
            onTabChange={handleViewChange}
            sections={sections}
          />

          <AppFooter
            generatedAt={
              data?.metadata
                ? formatGeneratedAt(data.metadata.generated_at)
                : null
            }
            loading={loading}
            onReload={handleForceRefresh}
          />

          {selectedRepo && (
            <Suspense fallback={<LoadingState message="Loading details..." />}>
              <RepositoryDetail
                repository={selectedRepo}
                onClose={closeDetail}
                onNext={handleNextRepo}
                onPrevious={handlePreviousRepo}
                resultIndex={activeResultList.findIndex((r) =>
                  sameRepo(r, selectedRepo),
                )}
                resultTotal={activeResultList.length}
                security={alertsForRepository(
                  alertFile,
                  fullNameOf(selectedRepo),
                )}
              />
            </Suspense>
          )}

          <ToastContainer toasts={toasts} onRemove={removeToast} />
        </div>
      </ViewportProvider>
    </ThemeProvider>
  );
}

export default App;

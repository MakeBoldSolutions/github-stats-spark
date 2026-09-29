import { useState, useMemo, useEffect, useCallback } from "react";
import { useTableSort } from "@/hooks/useTableSort";
import {
  extractLanguages,
  setupBackgroundSync,
  clearCache,
} from "@/services/dataService";
import { deferExecution, getConnectionType } from "@/utils/performance";

/**
 * Maps a URL hash fragment to the app's internal view identifier.
 * Preserves the original `table`/`visualizations`/`attention` hashes while
 * also accepting the newer `insights`/`health` aliases (FR-008).
 */
function resolveViewFromHash(hash) {
  const value = hash.slice(1);
  if (value === "visualizations" || value === "insights") {
    return "visualizations";
  }
  if (value === "attention" || value === "health") {
    return "attention";
  }
  return "table";
}

const VIEW_HASH = {
  table: "",
  visualizations: "visualizations",
  attention: "attention",
};

/**
 * Owns the dashboard-shell state that previously lived directly in App.jsx:
 * hash-derived view routing, toast notifications, background-sync and
 * service-worker update listeners, the active repository result list that
 * feeds drawer navigation, and the force-refresh flow. Keeping this state in
 * one hook lets App.jsx stay compositional (Constitution size gate).
 */
export function useDashboardShell({ data, refetch }) {
  // ---- Toast notifications ----
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback(
    (message, variant = "info", duration = 3000, action = null) => {
      const id = Date.now();
      setToasts((prev) => [
        ...prev,
        { id, message, variant, duration, action },
      ]);
      return id;
    },
    [],
  );

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  // ---- Performance: defer non-critical work on fast connections ----
  useEffect(() => {
    const connectionType = getConnectionType();
    if (import.meta.env.DEV) {
      console.log("[Performance] Connection type:", connectionType);
    }
    if (connectionType !== "2g" && connectionType !== "slow-2g") {
      deferExecution(() => {
        // Preload visualization components for faster navigation
      }, 3000);
    }
  }, []);

  // ---- Background sync (offline -> online refresh) ----
  useEffect(() => {
    const cleanup = setupBackgroundSync(() => {
      console.log("[App] Data refreshed after coming online");
      addToast("Data refreshed successfully", "success", 3000);
    });
    return cleanup;
  }, [addToast]);

  // ---- Service worker update notifications ----
  useEffect(() => {
    const handleSwUpdate = (event) => {
      const worker = event.detail?.worker;
      addToast("A new version is available.", "info", 0, {
        label: "Update",
        onClick: () => worker?.postMessage({ type: "SKIP_WAITING" }),
      });
      window.__pendingSwWorker = worker;
    };

    window.addEventListener("sw-update-available", handleSwUpdate);
    return () =>
      window.removeEventListener("sw-update-available", handleSwUpdate);
  }, [addToast]);

  // ---- View routing (hash-synced) ----
  const [currentView, setCurrentView] = useState(() =>
    resolveViewFromHash(window.location.hash),
  );

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentView(resolveViewFromHash(window.location.hash));
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleViewChange = useCallback((view) => {
    setCurrentView(view);
    window.location.hash = VIEW_HASH[view] ?? "";
  }, []);

  // ---- Catalog filter/sort (shared by Insights and Health until their own
  // dedicated controls land in later phases) ----
  const {
    sortedData: processedRepositories,
    filterLanguage,
    handleFilterChange,
    clearFilter,
  } = useTableSort(data?.repositories || [], "stars", "desc");

  const availableLanguages = useMemo(() => {
    if (!data?.repositories) return [];
    return extractLanguages(data.repositories);
  }, [data]);

  // ---- Selected repository + active result list (drawer navigation) ----
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [activeResultList, setActiveResultList] = useState([]);

  /**
   * Opens the drawer for `repository`. `resultList`, when provided, is the
   * ordered, currently-visible list from the view that initiated the click
   * (e.g. the filtered Overview catalog or the sorted Health ranking) so
   * Previous/Next always follows what the visitor was looking at.
   */
  const handleRepoClick = useCallback(
    (repository, resultList) => {
      setSelectedRepo(repository);
      setActiveResultList(resultList || processedRepositories || []);
    },
    [processedRepositories],
  );

  const closeDetail = useCallback(() => {
    setSelectedRepo(null);
  }, []);

  const handleNextRepo = useCallback(() => {
    if (!selectedRepo || !activeResultList.length) return;
    const index = activeResultList.findIndex(
      (r) => r.name === selectedRepo.name,
    );
    if (index >= 0 && index < activeResultList.length - 1) {
      setSelectedRepo(activeResultList[index + 1]);
    }
  }, [selectedRepo, activeResultList]);

  const handlePreviousRepo = useCallback(() => {
    if (!selectedRepo || !activeResultList.length) return;
    const index = activeResultList.findIndex(
      (r) => r.name === selectedRepo.name,
    );
    if (index > 0) {
      setSelectedRepo(activeResultList[index - 1]);
    }
  }, [selectedRepo, activeResultList]);

  // ---- Footer refresh ----
  const formatGeneratedAt = useCallback((timestamp) => {
    if (!timestamp) return "Unknown";
    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) return "Unknown";
    return parsed.toLocaleString();
  }, []);

  const handleForceRefresh = useCallback(async () => {
    try {
      await clearCache();
      await refetch({ forceRefresh: true, cacheBust: true });
      addToast("Data refreshed and cache cleared", "success", 3000);
    } catch {
      addToast("Refresh failed. Check the console for details.", "error", 4000);
    }
  }, [refetch, addToast]);

  return {
    // toasts
    toasts,
    addToast,
    removeToast,
    // routing
    currentView,
    handleViewChange,
    // catalog filter/sort (legacy shared filter, superseded per-view in later phases)
    processedRepositories,
    filterLanguage,
    handleFilterChange,
    clearFilter,
    availableLanguages,
    // drawer / active result list
    selectedRepo,
    activeResultList,
    handleRepoClick,
    closeDetail,
    handleNextRepo,
    handlePreviousRepo,
    // footer
    formatGeneratedAt,
    handleForceRefresh,
  };
}

export default useDashboardShell;

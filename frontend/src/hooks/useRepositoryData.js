import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDashboardData } from "@/services/dataService";
import { sourcesForScope } from "@/utils/scope";
import { mergeDashboards } from "@/utils/scopedData";

/**
 * Loads the dashboard data for the current scope.
 *
 * - Without a portfolio (GitHub Pages, or a single-profile deployment) it
 *   loads the one profile named by `?user=` or the default, exactly as
 *   before.
 * - With a self-hosted portfolio it loads the dashboard file of each
 *   collected source the scope needs and merges them (see
 *   mergeDashboards), reloading whenever the scope changes.
 *
 * Waits while `portfolioLoading` is true so the mode is known first.
 *
 * @returns {{data: object|null, loading: boolean, error: Error|null, refetch: Function}}
 */
export default function useRepositoryData({
  portfolio = null,
  portfolioLoading = false,
  scope = null,
} = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const request = useRef(0);

  const fetchData = useCallback(
    async (options = {}) => {
      const id = ++request.current;
      const fetchOptions = {
        useCache: options.useCache ?? false,
        forceRefresh: options.forceRefresh ?? true,
        cacheBust: options.cacheBust ?? true,
      };
      try {
        setLoading(true);
        setError(null);
        let result;
        if (!portfolio || !scope) {
          result = await fetchDashboardData(fetchOptions);
        } else {
          const ready = portfolio.sources
            .filter((s) => s.ready)
            .map((s) => s.slug);
          const slugs = sourcesForScope(portfolio, scope, ready);
          const dashboards = await Promise.all(
            slugs.map((user) => fetchDashboardData({ ...fetchOptions, user })),
          );
          result = mergeDashboards(dashboards, portfolio, scope);
        }
        if (id === request.current) setData(result);
        return result;
      } catch (err) {
        console.error("Error in useRepositoryData:", err);
        if (id === request.current) setError(err);
        // Do not re-throw: callers read the error state.
        return undefined;
      } finally {
        if (id === request.current) setLoading(false);
      }
    },
    [portfolio, scope],
  );

  useEffect(() => {
    if (portfolioLoading) return;
    fetchData({ cacheBust: false });
  }, [portfolioLoading, fetchData]);

  return { data, loading, error, refetch: fetchData };
}

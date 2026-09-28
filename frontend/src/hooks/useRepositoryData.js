import { useState, useEffect } from "react";
import { fetchDashboardData } from "@/services/dataService";

/**
 * Custom hook for fetching and managing repository dashboard data
 *
 * This hook handles the data fetching lifecycle including loading states,
 * error handling, and automatic refetching on mount.
 *
 * @returns {Object} Hook state object containing:
 *   - data: Dashboard data object (null if not loaded)
 *   - loading: Boolean indicating if data is currently being fetched
 *   - error: Error object if fetch failed (null otherwise)
 *   - refetch: Function to manually trigger data refetch
 *
 * @example
 * function MyComponent() {
 *   const { data, loading, error, refetch } = useRepositoryData()
 *
 *   if (loading) return <LoadingState />
 *   if (error) return <ErrorState error={error} />
 *
 *   return <RepositoryTable repositories={data.repositories} />
 * }
 */
export default function useRepositoryData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Fetch dashboard data and update state
   */
  const fetchData = async (options = {}) => {
    try {
      setLoading(true);
      setError(null);

      const dashboardData = await fetchDashboardData({
        useCache: options.useCache ?? false,
        forceRefresh: options.forceRefresh ?? true,
        cacheBust: options.cacheBust ?? true,
      });

      setData(dashboardData);
      return dashboardData;
    } catch (err) {
      console.error("Error in useRepositoryData:", err);
      setError(err);
      // Do not re-throw: error state is set above; callers check the error return value
    } finally {
      setLoading(false);
    }
  };

  /**
   * Effect to fetch data on component mount
   */
  useEffect(() => {
    fetchData({ cacheBust: false });
  }, []); // Empty dependency array = run once on mount

  /**
   * Manual refetch function
   */
  const refetch = (options = {}) => {
    return fetchData(options);
  };

  return {
    data,
    loading,
    error,
    refetch,
  };
}

/**
 * GitHub Stats Spark Dashboard - Data Service
 *
 * This service handles fetching dashboard JSON data from the generated data files.
 * In production (GitHub Pages), it fetches from the /docs/data/ directory.
 * In development, it uses the configured base path.
 *
 * Implements offline-first strategy with IndexedDB caching for improved performance
 * and offline functionality.
 *
 * @module dataService
 */

import { offlineStorage } from "./offlineStorage";

// Cache keys
const CACHE_KEY_REPOSITORIES = "repositories-data";

// Default user when no ?user= query param is provided.
// Must match the 'user' key in config/spark.yml.
const DEFAULT_USER = "makeboldsolutions";

const getSelectedUser = (explicitUser) => {
  if (explicitUser) {
    return explicitUser.trim().toLowerCase();
  }

  const params = new URLSearchParams(window.location.search);
  return params.get("user")?.trim().toLowerCase() || DEFAULT_USER;
};

const getRepositoriesPath = (user) => {
  return `users/${user}/repositories.json`;
};

const getRepositoriesCacheKey = (user) => {
  return `${CACHE_KEY_REPOSITORIES}:${user}`;
};

/**
 * Get the base URL for data fetching based on environment
 * @returns {string} Base URL for data files
 */
const getDataBaseUrl = () => {
  // In development, use relative path
  if (import.meta.env.DEV) {
    return "/data";
  }

  // In production (GitHub Pages), use the configured base path
  return `${import.meta.env.BASE_URL}data`;
};

/**
 * Fetch dashboard data from repositories.json with offline cache support
 *
 * Strategy: Cache-first with network fallback
 * - Checks offline cache first
 * - If online and cache is stale/missing, fetches from network
 * - Caches fresh data for offline use
 * - Falls back to cached data if network fails
 *
 * @param {object} options
 * @param {boolean} [options.useCache=true] - Whether to use offline cache
 * @param {boolean} [options.forceRefresh=false] - Force network fetch ignoring cache
 * @param {number} [options.maxRetries=3] - Maximum number of retry attempts
 * @param {number} [options.retryDelay=2000] - Delay between retries in ms
 * @returns {Promise<Object>} Dashboard data object containing:
 *   - repositories: Array of repository objects with metrics
 *   - profile: User profile information
 *   - metadata: Generation metadata and schema version
 *   - _fromCache: Boolean indicating if data came from cache
 *
 * @throws {Error} If fetch fails after all retries and no cache available
 *
 * @example
 * const data = await fetchDashboardData({ useCache: true })
 * console.log(`Loaded ${data.repositories.length} repositories`)
 * if (data._fromCache) console.log('Using cached data')
 */
export async function fetchDashboardData({
  useCache = true,
  forceRefresh = false,
  maxRetries = 3,
  retryDelay = 2000,
  cacheBust = true,
  user,
} = {}) {
  const baseUrl = getDataBaseUrl();
  const selectedUser = getSelectedUser(user);
  const cacheKey = getRepositoriesCacheKey(selectedUser);
  const cacheToken = cacheBust ? `?v=${Date.now()}` : "";
  const url = `${baseUrl}/${getRepositoriesPath(selectedUser)}${cacheToken}`;
  const isOnline = navigator.onLine;

  // Try cache first if enabled and not forcing refresh
  if (useCache && !forceRefresh) {
    try {
      const cachedData = await offlineStorage.get(cacheKey);
      if (cachedData) {
        console.log("[DataService] Using cached dashboard data", selectedUser);
        return { ...cachedData, _fromCache: true };
      }
    } catch (error) {
      console.warn("[DataService] Failed to read cache:", error);
    }
  }

  // If offline and no cache, throw error
  if (!isOnline) {
    throw new Error("No internet connection and no cached data available");
  }

  // Fetch from network
  const FETCH_TIMEOUT_MS = 30_000; // 30 second timeout per attempt
  let lastError = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        cache: cacheBust ? "no-store" : "default",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(
          `Failed to fetch dashboard data: ${response.status} ${response.statusText}`,
        );
      }

      const data = await response.json();

      // Validate data structure
      if (!data || typeof data !== "object") {
        throw new Error("Invalid dashboard data: expected object");
      }

      if (!Array.isArray(data.repositories)) {
        throw new Error(
          "Invalid dashboard data: repositories must be an array",
        );
      }

      // Cache the fresh data
      if (useCache) {
        try {
          await offlineStorage.set(cacheKey, data, "2.3.0");
          console.log("[DataService] Cached fresh dashboard data");
        } catch (error) {
          console.warn("[DataService] Failed to cache data:", error);
        }
      }

      // Success - log if retried
      if (attempt > 0) {
        console.log(
          `Successfully fetched data after ${attempt} ${attempt === 1 ? "retry" : "retries"}`,
        );
      }

      return { ...data, _fromCache: false };
    } catch (error) {
      clearTimeout(timeoutId);
      lastError =
        error.name === "AbortError"
          ? new Error(`Fetch timed out after ${FETCH_TIMEOUT_MS / 1000}s`)
          : error;
      console.error(
        `Error fetching dashboard data (attempt ${attempt + 1}/${maxRetries + 1}):`,
        lastError,
      );

      // Don't retry on the last attempt
      if (attempt < maxRetries) {
        console.log(`Retrying in ${retryDelay / 1000} seconds...`);
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
      }
    }
  }

  // All retries exhausted - try cache as last resort
  if (useCache) {
    try {
      const cachedData = await offlineStorage.get(cacheKey);
      if (cachedData) {
        console.warn("[DataService] Network failed, using stale cached data");
        return { ...cachedData, _fromCache: true, _stale: true };
      }
    } catch (error) {
      console.error(
        "[DataService] Failed to read cache after network error:",
        error,
      );
    }
  }

  // No cache and network failed
  console.error("Failed to fetch dashboard data after all retry attempts");
  throw lastError;
}

/**
 * Fetch user profile data (if stored separately)
 *
 * @returns {Promise<Object>} User profile object
 * @throws {Error} If fetch fails
 */
export async function fetchUserProfile() {
  const baseUrl = getDataBaseUrl();
  const url = `${baseUrl}/profile.json`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      // Profile data might not exist as separate file
      console.warn("Profile data not found, using data from repositories.json");
      return null;
    }

    return await response.json();
  } catch (error) {
    console.warn("Error fetching profile data:", error);
    return null;
  }
}

/**
 * Extract unique programming languages from repositories
 *
 * @param {Array} repositories - Array of repository objects
 * @returns {Array<string>} Sorted array of unique language names
 *
 * @example
 * const languages = extractLanguages(data.repositories)
 * // Returns: ['JavaScript', 'Python', 'TypeScript', ...]
 */
export function extractLanguages(repositories) {
  if (!Array.isArray(repositories)) {
    return [];
  }

  const languageSet = new Set();

  repositories.forEach((repo) => {
    if (repo.language && repo.language !== "Unknown") {
      languageSet.add(repo.language);
    }
  });

  return Array.from(languageSet).sort();
}

/**
 * Filter repositories by programming language
 *
 * @param {Array} repositories - Array of repository objects
 * @param {string} language - Language to filter by (or null for all)
 * @returns {Array} Filtered repository array
 *
 * @example
 * const pythonRepos = filterByLanguage(data.repositories, 'Python')
 */
export function filterByLanguage(repositories, language) {
  if (!language || language === "all") {
    return repositories;
  }

  return repositories.filter((repo) => repo.language === language);
}

/**
 * Sort repositories by a specific field
 *
 * @param {Array} repositories - Array of repository objects
 * @param {string} field - Field name to sort by (e.g., 'stars', 'commit_count')
 * @param {string} direction - Sort direction ('asc' or 'desc')
 * @returns {Array} Sorted repository array (new array, does not mutate original)
 *
 * @example
 * const sorted = sortRepositories(data.repositories, 'stars', 'desc')
 */
export function sortRepositories(repositories, field, direction = "desc") {
  if (!Array.isArray(repositories)) {
    return [];
  }

  // Create a copy to avoid mutating original array
  const sorted = [...repositories];

  sorted.sort((a, b) => {
    let aValue = a[field];
    let bValue = b[field];

    // Handle date fields
    if (field.includes("date") || field.includes("Date")) {
      aValue = new Date(aValue).getTime();
      bValue = new Date(bValue).getTime();
    }

    // Handle null/undefined values
    if (aValue == null) return 1;
    if (bValue == null) return -1;

    // Numeric or string comparison
    if (direction === "asc") {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    } else {
      return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
    }
  });

  return sorted;
}

/**
 * Search repositories by name or description
 *
 * @param {Array} repositories - Array of repository objects
 * @param {string} query - Search query string
 * @returns {Array} Filtered repositories matching query
 *
 * @example
 * const results = searchRepositories(data.repositories, 'react')
 */
export function searchRepositories(repositories, query) {
  if (!query || query.trim() === "") {
    return repositories;
  }

  const lowerQuery = query.toLowerCase().trim();

  return repositories.filter((repo) => {
    const nameMatch = repo.name?.toLowerCase().includes(lowerQuery);
    const descMatch = repo.description?.toLowerCase().includes(lowerQuery);
    const langMatch = repo.language?.toLowerCase().includes(lowerQuery);

    return nameMatch || descMatch || langMatch;
  });
}

/**
 * Calculate aggregate statistics from repository data
 *
 * @param {Array} repositories - Array of repository objects
 * @returns {Object} Aggregate statistics
 *
 * @example
 * const stats = calculateStats(data.repositories)
 * // Returns: { totalCommits: 1234, totalStars: 567, avgCommitSize: 42.5, ... }
 */
export function calculateStats(repositories) {
  if (!Array.isArray(repositories) || repositories.length === 0) {
    return {
      totalCommits: 0,
      totalStars: 0,
      totalForks: 0,
      avgCommitSize: 0,
      languageCount: 0,
    };
  }

  const totalCommits = repositories.reduce(
    (sum, repo) =>
      sum + (repo.commit_history?.total_commits || repo.total_commits || 0),
    0,
  );
  const totalStars = repositories.reduce(
    (sum, repo) => sum + (repo.stars || 0),
    0,
  );
  const totalForks = repositories.reduce(
    (sum, repo) => sum + (repo.forks || 0),
    0,
  );

  const avgCommitSize =
    repositories.reduce(
      (sum, repo) => sum + (repo.commit_metrics?.avg_size || 0),
      0,
    ) / repositories.length;

  const languages = extractLanguages(repositories);

  return {
    totalCommits,
    totalStars,
    totalForks,
    avgCommitSize: Math.round(avgCommitSize * 100) / 100, // Round to 2 decimals
    languageCount: languages.length,
  };
}

/**
 * Setup background sync when connectivity returns
 * Automatically refreshes data when coming online
 *
 * @param {Function} onSyncComplete - Callback when sync completes
 * @returns {Function} Cleanup function to remove listener
 *
 * @example
 * const cleanup = setupBackgroundSync(() => {
 *   console.log('Data refreshed after coming online')
 * })
 * // Later: cleanup()
 */
export function setupBackgroundSync(onSyncComplete) {
  const handleOnline = async () => {
    console.log("[DataService] Network restored, refreshing data...");
    try {
      const data = await fetchDashboardData({
        useCache: true,
        forceRefresh: true,
      });
      if (onSyncComplete) {
        onSyncComplete(data);
      }
    } catch (error) {
      console.error("[DataService] Background sync failed:", error);
    }
  };

  window.addEventListener("online", handleOnline);

  // Return cleanup function
  return () => {
    window.removeEventListener("online", handleOnline);
  };
}

/**
 * Clear all cached data
 * @returns {Promise<void>}
 */
export async function clearCache() {
  try {
    await offlineStorage.clear();
    console.log("[DataService] Cache cleared");
  } catch (error) {
    console.error("[DataService] Failed to clear cache:", error);
    throw error;
  }
}

export default {
  fetchDashboardData,
  fetchUserProfile,
  extractLanguages,
  filterByLanguage,
  sortRepositories,
  searchRepositories,
  calculateStats,
  setupBackgroundSync,
  clearCache,
};

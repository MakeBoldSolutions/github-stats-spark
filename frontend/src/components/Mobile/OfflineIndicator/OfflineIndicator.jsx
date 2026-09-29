/**
 * OfflineIndicator Component
 * Header banner shown when navigator.onLine is false. Reuses the existing
 * cached-data, relative-sync-time, and retry (refetch) behavior.
 */

import { WifiOff } from "lucide-react";
import { useOfflineCacheContext } from "@/contexts/OfflineCacheContext";
import "./OfflineIndicator.css";

export function OfflineIndicator({ onRetry }) {
  const { isOnline, lastSync } = useOfflineCacheContext();

  if (isOnline) {
    return null;
  }

  const formatLastSync = () => {
    if (!lastSync) return "Never synced";
    const diff = Date.now() - lastSync;
    if (diff < 60 * 1000) return "Just now";
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}m ago`;
    if (diff < 24 * 60 * 60 * 1000)
      return `${Math.floor(diff / (60 * 60 * 1000))}h ago`;
    return `${Math.floor(diff / (24 * 60 * 60 * 1000))}d ago`;
  };

  return (
    <div className="offline-indicator" role="status" aria-live="polite">
      <WifiOff
        size={16}
        className="offline-indicator__icon"
        aria-hidden="true"
      />
      <span className="offline-indicator__status">Offline mode</span>
      <span className="offline-indicator__sync">
        Showing cached data · Last synced {formatLastSync()}
      </span>
      {onRetry && (
        <button
          type="button"
          className="offline-indicator__retry"
          onClick={onRetry}
        >
          Try again
        </button>
      )}
    </div>
  );
}

export default OfflineIndicator;

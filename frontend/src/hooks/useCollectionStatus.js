import { useEffect, useState } from "react";

const POLL_MS = 60_000;

const statusUrl = () => {
  const base = import.meta.env.DEV ? "/" : import.meta.env.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/status.json`;
};

/**
 * Reads the worker's status.json (self-hosted deployment only).
 * Returns null while loading and whenever the file is absent or invalid
 * (for example on GitHub Pages), so callers render nothing.
 */
export default function useCollectionStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(`${statusUrl()}?v=${Date.now()}`, {
          cache: "no-store",
        });
        const type = response.headers?.get?.("content-type") || "";
        if (!response.ok || !type.includes("json")) {
          if (!cancelled) setStatus(null);
          return;
        }
        const payload = await response.json();
        if (!cancelled) {
          setStatus(payload?.schema_version === 1 ? payload : null);
        }
      } catch {
        if (!cancelled) setStatus(null);
      }
    };

    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return status;
}

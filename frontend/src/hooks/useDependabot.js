import { useEffect, useState } from "react";
import { isDependabotPayload } from "@/utils/dependabot";

const POLL_MS = 5 * 60_000;

const fileUrl = () => {
  const base = import.meta.env.DEV ? "/" : import.meta.env.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/security/dependabot.json`;
};

/**
 * Reads the worker's Dependabot export (self-hosted deployment only).
 * Returns null while loading and whenever the file is absent or invalid
 * (for example on GitHub Pages), so no Security navigation is shown.
 */
export default function useDependabot() {
  const [file, setFile] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(`${fileUrl()}?v=${Date.now()}`, {
          cache: "no-store",
        });
        const type = response.headers?.get?.("content-type") || "";
        if (!response.ok || !type.includes("json")) {
          if (!cancelled) setFile(null);
          return;
        }
        const payload = await response.json();
        if (!cancelled) setFile(isDependabotPayload(payload) ? payload : null);
      } catch {
        if (!cancelled) setFile(null);
      }
    };

    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return file;
}

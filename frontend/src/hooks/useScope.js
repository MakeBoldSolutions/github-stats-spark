import { useCallback, useEffect, useState } from "react";
import { readScope, scopeUrl } from "@/utils/scope";

const sameScope = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/**
 * The current dashboard scope, held in the URL. Changing it pushes a
 * history entry without reloading the page, so Back and Forward step
 * through scopes and a shared link restores one.
 *
 * The scope object keeps its identity until its value changes, so a
 * section change (which only touches the hash) does not reload data.
 */
export default function useScope() {
  const [scope, setScopeState] = useState(() =>
    readScope(window.location.search),
  );

  const sync = useCallback(() => {
    const next = readScope(window.location.search);
    setScopeState((previous) => (sameScope(previous, next) ? previous : next));
  }, []);

  useEffect(() => {
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [sync]);

  const setScope = useCallback(
    (next) => {
      const url = scopeUrl(next, window.location.href);
      if (url !== window.location.href) window.history.pushState(null, "", url);
      sync();
    },
    [sync],
  );

  return [scope, setScope];
}

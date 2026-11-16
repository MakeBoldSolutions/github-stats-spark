import { useCallback, useEffect, useState } from "react";

/**
 * Loads an admin API resource and exposes reload. A 401 is reported through
 * `onUnauthorized` so the view can return to the sign-in form.
 */
export default function useAdminResource(loader, onUnauthorized, refreshKey) {
  const [state, setState] = useState({
    data: null,
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    try {
      const data = await loader();
      setState({ data, loading: false, error: null });
    } catch (error) {
      if (error.status === 401) onUnauthorized?.();
      setState((previous) => ({ ...previous, loading: false, error }));
    }
  }, [loader, onUnauthorized]);

  useEffect(() => {
    reload();
  }, [reload, refreshKey]);

  return { ...state, reload };
}

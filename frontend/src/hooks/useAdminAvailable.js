import { useEffect, useState } from "react";
import { adminApi } from "@/services/adminApi";

/**
 * True only when the self-hosted admin API answers. Static deployments
 * (GitHub Pages) get false, so no admin navigation is shown.
 */
export default function useAdminAvailable() {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    adminApi.available().then((ok) => {
      if (!cancelled) setAvailable(ok);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return available;
}

import { useEffect, useState } from "react";

const dataUrl = (path) => {
  const base = import.meta.env.DEV ? "/" : import.meta.env.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/${path}`;
};

const isJson = (response) =>
  response.ok &&
  (response.headers?.get?.("content-type") || "").includes("json");

/** Dashboard data folders are the lower-cased login, as the data service expects. */
export const toSlug = (login) => String(login).trim().toLowerCase();

/**
 * Users that can be shown in the dashboard: the enabled `user` sources in
 * data/portfolio.json (written by the self-hosted worker). Each is marked
 * `ready` only once its dashboard data has actually been collected.
 *
 * Returns an empty list on static hosts (GitHub Pages), where there is no
 * portfolio.json, so no picker is offered there.
 */
export default function useUserOptions() {
  const [options, setOptions] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(dataUrl("portfolio.json"), {
          cache: "no-store",
        });
        if (!isJson(response)) return;
        const portfolio = await response.json();
        const logins = (portfolio?.sources || [])
          .filter((source) => source.type === "user" && source.enabled)
          .map((source) => source.identifier);

        const resolved = await Promise.all(
          logins.map(async (login) => {
            try {
              const check = await fetch(
                dataUrl(`users/${toSlug(login)}/repositories.json`),
                { method: "HEAD", cache: "no-store" },
              );
              return { login, slug: toSlug(login), ready: isJson(check) };
            } catch {
              return { login, slug: toSlug(login), ready: false };
            }
          }),
        );
        if (!cancelled) setOptions(resolved);
      } catch {
        if (!cancelled) setOptions([]);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return options;
}

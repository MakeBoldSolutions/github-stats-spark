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

const SOURCE_TYPES = ["user", "org", "repo"];

/**
 * Folder for a source's dashboard. The worker writes the slug into
 * portfolio.json; this fallback matches its scheme (a repository is
 * `<owner>--<name>`) for older files.
 */
const slugFor = (source) => {
  if (source.slug) return source.slug;
  const id = String(source.identifier);
  if (source.type === "repo" && id.includes("/")) {
    const [owner, name] = id.split("/", 2);
    return `${toSlug(owner)}--${toSlug(name)}`;
  }
  return toSlug(id);
};

/**
 * Sources that can be shown in the dashboard: the enabled user, organization
 * and repository sources in data/portfolio.json (written by the self-hosted
 * worker). Each is marked `ready` only once its dashboard data has actually
 * been collected.
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
        const sources = (portfolio?.sources || [])
          .filter(
            (source) => SOURCE_TYPES.includes(source.type) && source.enabled,
          )
          .map((source) => ({
            login: source.identifier,
            type: source.type,
            slug: slugFor(source),
          }))
          .sort(
            (a, b) =>
              SOURCE_TYPES.indexOf(a.type) - SOURCE_TYPES.indexOf(b.type),
          );

        const resolved = await Promise.all(
          sources.map(async (source) => {
            try {
              const check = await fetch(
                dataUrl(`users/${source.slug}/repositories.json`),
                { method: "HEAD", cache: "no-store" },
              );
              return { ...source, ready: isJson(check) };
            } catch {
              return { ...source, ready: false };
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

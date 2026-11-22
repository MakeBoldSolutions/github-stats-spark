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

async function hasDashboard(slug) {
  try {
    const check = await fetch(dataUrl(`users/${slug}/repositories.json`), {
      method: "HEAD",
      cache: "no-store",
    });
    return isJson(check);
  } catch {
    return false;
  }
}

/**
 * The self-hosted portfolio index (data/portfolio.json): de-duplicated
 * repositories with their client, project, application and
 * classifications; the domain catalog; and the enabled user, organization
 * and repository sources, each marked `ready` once its dashboard data has
 * been collected.
 *
 * `portfolio` is null on static hosts (GitHub Pages), where the file does
 * not exist; the dashboard then behaves as a single public profile.
 */
export default function usePortfolio() {
  const [state, setState] = useState({ loading: true, portfolio: null });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(dataUrl("portfolio.json"), {
          cache: "no-store",
        });
        if (!isJson(response)) {
          if (!cancelled) setState({ loading: false, portfolio: null });
          return;
        }
        const portfolio = await response.json();
        const enabled = (portfolio?.sources || [])
          .filter((s) => SOURCE_TYPES.includes(s.type) && s.enabled)
          .map((s) => ({ ...s, slug: slugFor(s) }))
          .sort(
            (a, b) =>
              SOURCE_TYPES.indexOf(a.type) - SOURCE_TYPES.indexOf(b.type),
          );
        const sources = await Promise.all(
          enabled.map(async (s) => ({
            ...s,
            ready: await hasDashboard(s.slug),
          })),
        );
        if (!cancelled) {
          setState({
            loading: false,
            portfolio: {
              ...portfolio,
              repositories: portfolio?.repositories || [],
              domains: portfolio?.domains || [],
              sources,
            },
          });
        }
      } catch {
        if (!cancelled) setState({ loading: false, portfolio: null });
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

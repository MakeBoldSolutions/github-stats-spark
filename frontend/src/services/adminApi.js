// Client for the self-hosted admin API. On GitHub Pages (or any static host)
// the API does not exist; `available()` then resolves false and the admin
// pages are never offered.

const base = () => {
  const root = import.meta.env.DEV ? "/" : import.meta.env.BASE_URL || "/";
  return root.endsWith("/") ? root : `${root}/`;
};

let csrfToken = null;

export class ApiError extends Error {
  constructor(status, detail) {
    const message =
      detail?.message ||
      (typeof detail === "string" ? detail : `Request failed (${status})`);
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = detail?.code || null;
  }
}

async function request(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(`${base()}api${path}`, {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  const type = response.headers?.get?.("content-type") || "";
  const payload = type.includes("json") ? await response.json() : null;
  if (!response.ok) throw new ApiError(response.status, payload?.detail);
  return payload;
}

export const adminApi = {
  async available() {
    try {
      const response = await fetch(`${base()}api/health`, {
        cache: "no-store",
      });
      const type = response.headers?.get?.("content-type") || "";
      if (!response.ok || !type.includes("json")) return false;
      return (await response.json())?.ok === true;
    } catch {
      return false;
    }
  },

  async session() {
    const info = await request("GET", "/session");
    csrfToken = info.csrf_token;
    return info;
  },
  async signIn(username, password) {
    const info = await request("POST", "/session", { username, password });
    csrfToken = info.csrf_token;
    return info;
  },
  async signOut() {
    try {
      await request("DELETE", "/session");
    } finally {
      csrfToken = null;
    }
  },

  sources: () => request("GET", "/sources"),
  addSource: (source) => request("POST", "/sources", source),
  editSource: (id, changes) => request("PATCH", `/sources/${id}`, changes),
  removeSource: (id) => request("DELETE", `/sources/${id}`),

  repositories: () => request("GET", "/repositories"),
  editRepository: (changes) => request("PATCH", "/repositories", changes),
  portfolio: () => request("GET", "/portfolio"),

  connections: () => request("GET", "/connections"),
  addConnection: (connection) => request("POST", "/connections", connection),
  removeConnection: (id) => request("DELETE", `/connections/${id}`),

  refresh: () => request("POST", "/refresh"),
};

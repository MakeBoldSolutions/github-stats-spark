import { useCallback, useEffect, useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import PageHeader from "@/components/Common/PageHeader";
import { adminApi } from "@/services/adminApi";
import LoginForm from "./LoginForm";
import SourcesPanel from "./SourcesPanel";
import RepositoriesPanel from "./RepositoriesPanel";
import ConnectionsPanel from "./ConnectionsPanel";
import ListsPanel from "./ListsPanel";
import DomainsPanel from "./DomainsPanel";
import styles from "./Admin.module.css";

const TABS = [
  { id: "sources", label: "Sources" },
  { id: "repositories", label: "Repositories" },
  { id: "lists", label: "Lists" },
  { id: "domains", label: "Domains" },
  { id: "tokens", label: "Tokens" },
];

/**
 * Administration: sign-in, then manage sources, repositories, the managed
 * lists and domains they are classified with, and tokens.
 * Only offered when the self-hosted admin API is present.
 */
export default function SourcesView({ onToast }) {
  const [auth, setAuth] = useState({ state: "checking" });
  const [tab, setTab] = useState("sources");
  const [changeCount, setChangeCount] = useState(0);
  const [refreshNote, setRefreshNote] = useState("");

  useEffect(() => {
    let cancelled = false;
    adminApi
      .session()
      .then((info) => !cancelled && setAuth({ state: "in", info }))
      .catch(() => !cancelled && setAuth({ state: "out" }));
    return () => {
      cancelled = true;
    };
  }, []);

  const signedOut = useCallback(() => setAuth({ state: "out" }), []);
  const changed = useCallback(() => setChangeCount((count) => count + 1), []);
  const openLists = useCallback(() => setTab("lists"), []);

  const collectNow = async () => {
    try {
      await adminApi.refresh();
      setRefreshNote(
        "Collection requested. The worker starts within seconds; watch the status line in the header.",
      );
      onToast?.("Collection requested", "info");
    } catch (error) {
      if (error.status === 401) signedOut();
      setRefreshNote(error.message);
    }
  };

  const signOut = async () => {
    await adminApi.signOut().catch(() => {});
    signedOut();
  };

  return (
    <section
      className="view-transition"
      aria-labelledby="admin-heading"
      data-testid="admin-view"
    >
      <PageHeader
        eyebrow="Admin"
        title="Manage sources"
        titleId="admin-heading"
      />

      {auth.state === "checking" && <p>Checking sign-in…</p>}

      {auth.state === "out" && (
        <LoginForm onSignedIn={(info) => setAuth({ state: "in", info })} />
      )}

      {auth.state === "in" && (
        <div className={styles.panel}>
          <div className={styles.toolbar}>
            <span className={styles.muted}>
              Signed in as {auth.info.username}
            </span>
            <div className={styles.actions}>
              <Button size="sm" variant="secondary" onClick={collectNow}>
                Collect now
              </Button>
              <Button size="sm" variant="ghost" onClick={signOut}>
                Sign out
              </Button>
            </div>
          </div>
          <div role="status" aria-live="polite">
            {refreshNote && <p className={styles.notice}>{refreshNote}</p>}
          </div>

          <div className={styles.tabs} role="tablist" aria-label="Admin">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                id={`admin-tab-${id}`}
                type="button"
                role="tab"
                className={styles.tab}
                aria-selected={tab === id}
                aria-controls={`admin-panel-${id}`}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          <div
            id={`admin-panel-${tab}`}
            role="tabpanel"
            aria-labelledby={`admin-tab-${tab}`}
          >
            {tab === "sources" && (
              <SourcesPanel
                onUnauthorized={signedOut}
                onChanged={changed}
                onEditLists={openLists}
              />
            )}
            {tab === "repositories" && (
              <RepositoriesPanel
                onUnauthorized={signedOut}
                refreshKey={changeCount}
                onEditLists={openLists}
              />
            )}
            {tab === "lists" && (
              <ListsPanel onUnauthorized={signedOut} onChanged={changed} />
            )}
            {tab === "domains" && (
              <DomainsPanel onUnauthorized={signedOut} onChanged={changed} />
            )}
            {tab === "tokens" && (
              <ConnectionsPanel
                onUnauthorized={signedOut}
                encryptionAvailable={auth.info.encryption_available}
              />
            )}
          </div>
        </div>
      )}
    </section>
  );
}

SourcesView.propTypes = { onToast: PropTypes.func };

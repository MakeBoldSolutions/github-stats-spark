import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import styles from "./Admin.module.css";

const SOON_DAYS = 14;

export function expiryLabel(connection, now = Date.now()) {
  if (!connection.expires_at) return { text: "No expiry set", tone: "" };
  const when = new Date(connection.expires_at).getTime();
  if (Number.isNaN(when)) return { text: "Unknown expiry", tone: "" };
  const days = Math.ceil((when - now) / 86_400_000);
  const date = new Date(when).toLocaleDateString();
  if (days <= 0) return { text: `Expired ${date}`, tone: "error" };
  if (days <= SOON_DAYS)
    return { text: `Expires ${date} (${days}d left)`, tone: "warn" };
  return { text: `Expires ${date}`, tone: "" };
}

export default function ConnectionsPanel({
  onUnauthorized,
  encryptionAvailable,
}) {
  const connections = useAdminResource(adminApi.connections, onUnauthorized);
  const [form, setForm] = useState({
    name: "",
    owner: "",
    token: "",
    expires_at: "",
  });
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [busy, setBusy] = useState(false);

  const update = (field) => (event) =>
    setForm((previous) => ({ ...previous, [field]: event.target.value }));

  const run = async (action, success) => {
    setBusy(true);
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await connections.reload();
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const add = (event) => {
    event.preventDefault();
    run(async () => {
      await adminApi.addConnection({
        name: form.name,
        owner: form.owner || null,
        token: form.token,
        expires_at: form.expires_at || null,
      });
      // The token is never kept in the page once it has been sent.
      setForm({ name: "", owner: "", token: "", expires_at: "" });
    }, `Saved ${form.name}. The token is encrypted and cannot be shown again.`);
  };

  return (
    <section className={styles.panel} aria-labelledby="connections-heading">
      <h2 id="connections-heading">GitHub tokens</h2>
      <p className={styles.muted}>
        Use a fine-grained personal access token with read-only access. A token
        covers one user or organization, so add one per owner. Set its expiry so
        you are warned before collection stops.
      </p>

      {!encryptionAvailable && (
        <p className={`${styles.notice} ${styles.noticeWarn}`} role="note">
          Saving tokens is disabled: no encryption key is configured on the
          server (SPARK_SECRET_KEY).
        </p>
      )}

      <form
        className={styles.form}
        onSubmit={add}
        aria-label="Add a GitHub token"
      >
        <div className={styles.field}>
          <label htmlFor="conn-name">Name</label>
          <input
            id="conn-name"
            className={styles.input}
            value={form.name}
            onChange={update("name")}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="conn-owner">Owner (optional)</label>
          <input
            id="conn-owner"
            className={styles.input}
            value={form.owner}
            onChange={update("owner")}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="conn-token">Token</label>
          <input
            id="conn-token"
            type="password"
            autoComplete="off"
            className={styles.input}
            value={form.token}
            onChange={update("token")}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="conn-expiry">Expires (optional)</label>
          <input
            id="conn-expiry"
            type="date"
            className={styles.input}
            value={form.expires_at}
            onChange={update("expires_at")}
          />
        </div>
        <Button type="submit" disabled={busy || !encryptionAvailable}>
          {busy ? "Checking…" : "Save token"}
        </Button>
      </form>

      <div role="status" aria-live="polite">
        {message.text && (
          <p
            className={`${styles.notice} ${message.kind === "error" ? styles.noticeError : ""}`}
          >
            {message.text}
          </p>
        )}
      </div>

      {!connections.loading && (connections.data || []).length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption>Saved tokens</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Owner</th>
                <th scope="col">Expiry</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {connections.data.map((connection) => {
                const expiry = expiryLabel(connection);
                return (
                  <tr key={connection.id}>
                    <td>{connection.name}</td>
                    <td>{connection.owner || "—"}</td>
                    <td>
                      <span
                        className={
                          expiry.tone === "error"
                            ? `${styles.state} ${styles.stateError}`
                            : ""
                        }
                      >
                        {expiry.tone === "warn" ? "⚠ " : ""}
                        {expiry.text}
                      </span>
                    </td>
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        aria-label={`Delete token ${connection.name}`}
                        onClick={() =>
                          run(
                            () => adminApi.removeConnection(connection.id),
                            `Deleted ${connection.name}. Sources that used it now use the default token.`,
                          )
                        }
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

ConnectionsPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  encryptionAvailable: PropTypes.bool,
};

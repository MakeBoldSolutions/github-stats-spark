import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import styles from "./Admin.module.css";

const TYPE_LABEL = { org: "Organization", user: "User", repo: "Repository" };
const PLACEHOLDER = {
  org: "organization login",
  user: "user login",
  repo: "owner/repository",
};

export default function SourcesPanel({ onUnauthorized, onChanged }) {
  const sources = useAdminResource(adminApi.sources, onUnauthorized);
  const connections = useAdminResource(adminApi.connections, onUnauthorized);
  const [form, setForm] = useState({
    type: "org",
    identifier: "",
    client: "",
    connection_id: "",
  });
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [confirmId, setConfirmId] = useState(null);
  const [busy, setBusy] = useState(false);

  const update = (field) => (event) =>
    setForm((previous) => ({ ...previous, [field]: event.target.value }));

  const run = async (action, success) => {
    setBusy(true);
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await sources.reload();
      onChanged?.();
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const add = (event) => {
    event.preventDefault();
    const payload = {
      type: form.type,
      identifier: form.identifier,
      client: form.client || null,
      connection_id: form.connection_id ? Number(form.connection_id) : null,
    };
    run(async () => {
      await adminApi.addSource(payload);
      setForm((previous) => ({ ...previous, identifier: "" }));
    }, `Added ${payload.identifier}. Its repositories were discovered now and are collected on the next run.`);
  };

  return (
    <section className={styles.panel} aria-labelledby="sources-heading">
      <h2 id="sources-heading">Sources</h2>
      <p className={styles.muted}>
        Organizations, users and individual repositories to collect. Access is
        checked before anything is saved.
      </p>

      <form className={styles.form} onSubmit={add} aria-label="Add a source">
        <div className={styles.field}>
          <label htmlFor="source-type">Type</label>
          <select
            id="source-type"
            className={styles.input}
            value={form.type}
            onChange={update("type")}
          >
            {Object.entries(TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor="source-identifier">Name</label>
          <input
            id="source-identifier"
            className={styles.input}
            placeholder={PLACEHOLDER[form.type]}
            value={form.identifier}
            onChange={update("identifier")}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="source-client">Client (optional)</label>
          <input
            id="source-client"
            className={styles.input}
            value={form.client}
            onChange={update("client")}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="source-connection">Token</label>
          <select
            id="source-connection"
            className={styles.input}
            value={form.connection_id}
            onChange={update("connection_id")}
          >
            <option value="">Default token</option>
            {(connections.data || []).map((connection) => (
              <option key={connection.id} value={connection.id}>
                {connection.name}
                {connection.expired ? " (expired)" : ""}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? "Checking…" : "Add source"}
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

      {sources.loading ? (
        <p>Loading sources…</p>
      ) : (sources.data || []).length === 0 ? (
        <p className={styles.notice}>No sources registered yet.</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption>Registered sources</caption>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col">Repositories</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((source) => (
                <tr key={source.id}>
                  <td>
                    {source.identifier}
                    <div className={styles.muted}>
                      {TYPE_LABEL[source.type]}
                      {source.client ? ` · ${source.client}` : ""}
                      {source.enabled ? "" : " · disabled"}
                    </div>
                  </td>
                  <td>
                    {source.state === "error" ? (
                      <>
                        <span
                          className={`${styles.state} ${styles.stateError}`}
                        >
                          {source.error_code}
                        </span>
                        <div className={styles.muted}>
                          {source.error_message}
                        </div>
                      </>
                    ) : (
                      <span className={`${styles.state} ${styles.stateOk}`}>
                        {source.state === "ok" ? "OK" : "Pending"}
                      </span>
                    )}
                  </td>
                  <td>{source.repository_count}</td>
                  <td>
                    <div className={styles.actions}>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(
                            () =>
                              adminApi.editSource(source.id, {
                                enabled: !source.enabled,
                              }),
                            `${source.identifier} ${source.enabled ? "disabled" : "enabled"}.`,
                          )
                        }
                      >
                        {source.enabled ? "Disable" : "Enable"}
                      </Button>
                      {confirmId === source.id ? (
                        <>
                          <Button
                            size="sm"
                            variant="dark"
                            disabled={busy}
                            onClick={() => {
                              setConfirmId(null);
                              run(
                                () => adminApi.removeSource(source.id),
                                `Removed ${source.identifier}. Collected repositories were kept.`,
                              );
                            }}
                          >
                            Confirm remove
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setConfirmId(null)}
                          >
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Remove ${source.identifier}`}
                          onClick={() => setConfirmId(source.id)}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

SourcesPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  onChanged: PropTypes.func,
};

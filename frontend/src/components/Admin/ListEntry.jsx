import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import styles from "./Admin.module.css";

/**
 * One client, project or application: its name and usage, with rename,
 * retire/restore, and merge into another entry of the same scope.
 */
export default function ListEntry({ kind, entry, mergeTargets, onChange }) {
  const [mode, setMode] = useState("view");
  const [name, setName] = useState(entry.name);
  const [target, setTarget] = useState("");
  const fieldId = `${kind}-${entry.id}`;
  const usage = `${entry.repository_count} ${entry.repository_count === 1 ? "repository" : "repositories"}${
    entry.source_count ? `, ${entry.source_count} source(s)` : ""
  }`;

  const finish = async (action) => {
    if (await onChange(action)) setMode("view");
  };

  if (mode === "rename") {
    return (
      <form
        className={styles.inlineForm}
        onSubmit={(event) => {
          event.preventDefault();
          finish({ type: "edit", id: entry.id, changes: { name } });
        }}
      >
        <label htmlFor={`${fieldId}-name`} className={styles.srOnly}>
          New name for {entry.name}
        </label>
        <input
          id={`${fieldId}-name`}
          className={styles.input}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={120}
          required
        />
        <Button type="submit" size="sm">
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode("view")}>
          Cancel
        </Button>
      </form>
    );
  }

  if (mode === "merge") {
    return (
      <form
        className={styles.inlineForm}
        onSubmit={(event) => {
          event.preventDefault();
          if (target)
            finish({ type: "merge", id: entry.id, intoId: Number(target) });
        }}
      >
        <label htmlFor={`${fieldId}-merge`}>Merge {entry.name} into</label>
        <select
          id={`${fieldId}-merge`}
          className={styles.input}
          value={target}
          onChange={(event) => setTarget(event.target.value)}
        >
          <option value="">Choose…</option>
          {mergeTargets.map((other) => (
            <option key={other.id} value={other.id}>
              {other.name}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm" disabled={!target}>
          Confirm merge
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode("view")}>
          Cancel
        </Button>
      </form>
    );
  }

  return (
    <div className={styles.entry}>
      <span>
        <strong>{entry.name}</strong>
        {entry.retired && <span className={styles.state}> Retired</span>}
        <span className={styles.muted}> · {usage}</span>
      </span>
      <span className={styles.actions}>
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Rename ${entry.name}`}
          onClick={() => {
            setName(entry.name);
            setMode("rename");
          }}
        >
          Rename
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={`${entry.retired ? "Restore" : "Retire"} ${entry.name}`}
          onClick={() =>
            onChange({
              type: "edit",
              id: entry.id,
              changes: { retired: !entry.retired },
            })
          }
        >
          {entry.retired ? "Restore" : "Retire"}
        </Button>
        {!entry.retired && mergeTargets.length > 0 && (
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Merge ${entry.name}`}
            onClick={() => setMode("merge")}
          >
            Merge
          </Button>
        )}
      </span>
    </div>
  );
}

ListEntry.propTypes = {
  kind: PropTypes.oneOf(["client", "project", "application"]).isRequired,
  entry: PropTypes.shape({
    id: PropTypes.number.isRequired,
    name: PropTypes.string.isRequired,
    retired: PropTypes.bool,
    repository_count: PropTypes.number,
    source_count: PropTypes.number,
  }).isRequired,
  mergeTargets: PropTypes.arrayOf(PropTypes.object).isRequired,
  onChange: PropTypes.func.isRequired,
};

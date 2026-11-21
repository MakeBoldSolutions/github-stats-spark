import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { domainChoices } from "./portfolioOptions";
import styles from "./Admin.module.css";

/**
 * Classify every selected repository in one domain at once. A single-choice
 * domain sets (or clears) the value; a multi-choice domain can add or remove
 * values without touching the others each repository holds.
 */
export default function BulkClassify({ count, domains, onApply, onClear }) {
  const choices = domainChoices(domains);
  const [domainKey, setDomainKey] = useState(choices[0]?.key || "");
  const [value, setValue] = useState("");
  const [mode, setMode] = useState("add");
  const domain = choices.find((d) => d.key === domainKey);

  const apply = (event) => {
    event.preventDefault();
    if (!domain) return;
    if (domain.multi) {
      if (value) onApply({ domain: domain.key, values: [value], mode });
    } else {
      onApply({
        domain: domain.key,
        values: value ? [value] : [],
        mode: "set",
      });
    }
  };

  return (
    <form
      className={`${styles.form} ${styles.bulk}`}
      onSubmit={apply}
      aria-label="Classify selected repositories"
    >
      <p className={styles.muted} role="status" aria-live="polite">
        {count} selected
      </p>
      <div className={styles.field}>
        <label htmlFor="bulk-domain">Domain</label>
        <select
          id="bulk-domain"
          className={styles.input}
          value={domainKey}
          onChange={(event) => {
            setDomainKey(event.target.value);
            setValue("");
          }}
        >
          {choices.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
        </select>
      </div>
      {domain?.multi && (
        <div className={styles.field}>
          <label htmlFor="bulk-mode">Change</label>
          <select
            id="bulk-mode"
            className={styles.input}
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            <option value="add">Add value</option>
            <option value="remove">Remove value</option>
          </select>
        </div>
      )}
      <div className={styles.field}>
        <label htmlFor="bulk-value">Value</label>
        <select
          id="bulk-value"
          className={styles.input}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        >
          <option value="">
            {domain?.multi ? "Choose a value" : "Not set"}
          </option>
          {(domain?.values || []).map((v) => (
            <option key={v.key} value={v.key}>
              {v.label}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.actions}>
        <Button type="submit" size="sm" disabled={domain?.multi && !value}>
          Apply to {count}
        </Button>
        <Button size="sm" variant="ghost" onClick={onClear}>
          Clear selection
        </Button>
      </div>
    </form>
  );
}

BulkClassify.propTypes = {
  count: PropTypes.number.isRequired,
  domains: PropTypes.arrayOf(PropTypes.object),
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};

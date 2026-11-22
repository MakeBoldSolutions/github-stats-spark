import PropTypes from "prop-types";
import styles from "./DataViews.module.css";

/**
 * A row of labelled select filters. Each field offers "all" (empty value)
 * first unless `allLabel` is null. Extra controls (an export menu, a reset
 * button) go in `children`, after the fields.
 */
export default function FilterBar({ label, fields, children }) {
  return (
    <form
      className={styles.filters}
      aria-label={label}
      onSubmit={(event) => event.preventDefault()}
    >
      {fields.map((field) => (
        <label key={field.id} className={styles.field} htmlFor={field.id}>
          {field.label}
          <select
            id={field.id}
            value={field.value}
            onChange={(event) => field.onChange(event.target.value)}
          >
            {field.allLabel !== null && (
              <option value="">{field.allLabel ?? "All"}</option>
            )}
            {field.options.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            ))}
          </select>
        </label>
      ))}
      {children}
    </form>
  );
}

FilterBar.propTypes = {
  label: PropTypes.string.isRequired,
  fields: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      value: PropTypes.string.isRequired,
      onChange: PropTypes.func.isRequired,
      options: PropTypes.arrayOf(
        PropTypes.shape({
          value: PropTypes.string.isRequired,
          label: PropTypes.string.isRequired,
          disabled: PropTypes.bool,
        }),
      ).isRequired,
      allLabel: PropTypes.string,
    }),
  ).isRequired,
  children: PropTypes.node,
};

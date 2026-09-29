import "./EmptyState.css";

/**
 * EmptyState - Display when list or view has no content
 *
 * Features:
 * - Center-aligned layout
 * - Icon/illustration support
 * - Descriptive message
 * - Optional action button
 * - Responsive sizing
 *
 * @param {Object} props
 * @param {React.ReactNode} [props.icon] - Optional outline icon (lucide-react)
 * @param {string} props.title - Primary message
 * @param {string} props.description - Optional secondary description
 * @param {string} props.actionLabel - Button text
 * @param {Function} props.onAction - Button click handler
 */
const EmptyState = ({
  icon = null,
  title = "No items found",
  description = "",
  actionLabel = "",
  onAction = null,
}) => {
  return (
    <div className="empty-state">
      {icon && (
        <div className="empty-state__icon" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="empty-state__title">{title}</h3>
      {description && <p className="empty-state__description">{description}</p>}
      {actionLabel && onAction && (
        <button
          className="empty-state__action"
          onClick={onAction}
          type="button"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

export default EmptyState;

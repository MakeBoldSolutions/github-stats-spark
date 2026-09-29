/**
 * LoadingState Component
 *
 * Displays a loading indicator with optional message. The `large` size is
 * used for the primary full-page loading state and shows the approved peak
 * mark instead of a spinner; other sizes keep the compact inline spinner
 * used inside cards and lazy-loaded chart panels.
 *
 * @component
 * @param {Object} props - Component props
 * @param {string} [props.message='Loading...'] - Custom loading message
 * @param {string} [props.size='medium'] - Spinner size ('small', 'medium', 'large')
 *
 * @example
 * <LoadingState message="Loading repository data..." size="large" />
 */
export default function LoadingState({
  message = "Loading...",
  size = "medium",
}) {
  if (size === "large") {
    return (
      <div
        className="loading-state loading-state--page flex flex-col items-center justify-center"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <img
          src="/logo-mark.svg"
          alt=""
          width={44}
          height={44}
          className="loading-state__mark"
        />
        {message && <p className="text-muted mt-md">{message}</p>}
      </div>
    );
  }

  const sizes = {
    small: { width: "20px", height: "20px", borderWidth: "2px" },
    medium: { width: "32px", height: "32px", borderWidth: "3px" },
  };
  const spinnerStyle = sizes[size] || sizes.medium;

  return (
    <div
      className="loading-state flex flex-col items-center justify-center"
      style={{ padding: "var(--spacing-xl)", minHeight: "200px" }}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="loading" style={spinnerStyle} aria-label="Loading"></div>
      {message && (
        <p
          className="text-muted mt-md"
          style={{ marginTop: "var(--spacing-md)" }}
        >
          {message}
        </p>
      )}
      <span className="sr-only">{message}</span>
    </div>
  );
}

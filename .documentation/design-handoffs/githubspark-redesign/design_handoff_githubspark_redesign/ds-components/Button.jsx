import React from "react";

/**
 * Make Bold Solutions — Button
 * Confident, geometric button with modest radius and no-bounce interactions.
 */
export function Button({
  children,
  variant = "primary",
  size = "md",
  iconLeft = null,
  iconRight = null,
  fullWidth = false,
  disabled = false,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: { padding: "8px 14px", fontSize: "14px", gap: "6px" },
    md: { padding: "11px 20px", fontSize: "15px", gap: "8px" },
    lg: { padding: "15px 28px", fontSize: "17px", gap: "10px" },
  };

  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: sizes[size].gap,
    fontFamily: "var(--font-body)",
    fontWeight: "var(--fw-semibold)",
    fontSize: sizes[size].fontSize,
    lineHeight: 1,
    letterSpacing: "0.01em",
    padding: sizes[size].padding,
    borderRadius: "var(--radius-md)",
    border: "1px solid transparent",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1,
    width: fullWidth ? "100%" : "auto",
    transition:
      "background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard)",
    textDecoration: "none",
    whiteSpace: "nowrap",
    ...style,
  };

  const variants = {
    primary: { background: "var(--brand)", color: "var(--text-on-brand)" },
    accent: { background: "var(--accent)", color: "var(--white)" },
    secondary: {
      background: "transparent",
      color: "var(--brand-strong)",
      borderColor: "var(--brand)",
    },
    ghost: { background: "transparent", color: "var(--text-strong)" },
    dark: { background: "var(--surface-dark)", color: "var(--cream)" },
  };

  const hovers = {
    primary: { background: "var(--brand-strong)" },
    accent: { background: "var(--accent-strong)" },
    secondary: { background: "var(--brand-soft)" },
    ghost: { background: "var(--ink-100)" },
    dark: { background: "var(--ink-800)" },
  };

  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);

  const composed = {
    ...base,
    ...variants[variant],
    ...(hover && !disabled ? hovers[variant] : {}),
    ...(active && !disabled ? { transform: "translateY(1px)" } : {}),
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={composed}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setActive(false); }}
      onMouseDown={() => setActive(true)}
      onMouseUp={() => setActive(false)}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}

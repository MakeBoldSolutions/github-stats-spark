import React from "react";

/**
 * Make Bold Solutions — Eyebrow
 * Signature letter-spaced uppercase label, in ember. Sits above headings.
 */
export function Eyebrow({ children, as: Tag = "div", color = "accent", style = {}, ...rest }) {
  const colors = {
    accent: "var(--accent-strong)",
    brand: "var(--brand)",
    muted: "var(--text-muted)",
    onDark: "var(--ember-300)",
  };
  return (
    <Tag
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: "var(--fw-semibold)",
        fontSize: "var(--fs-sm)",
        letterSpacing: "var(--ls-eyebrow)",
        textTransform: "uppercase",
        color: colors[color],
        ...style,
      }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

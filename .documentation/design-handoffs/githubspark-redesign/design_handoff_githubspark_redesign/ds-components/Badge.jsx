import React from "react";

/**
 * Make Bold Solutions — Badge
 * Compact status / category label. Muted, finance-grade tones.
 */
export function Badge({ children, tone = "neutral", style = {}, ...rest }) {
  const tones = {
    neutral: { background: "var(--ink-100)", color: "var(--ink-700)" },
    brand: { background: "var(--rust-50)", color: "var(--rust-600)" },
    accent: { background: "var(--ember-50)", color: "var(--ember-700)" },
    positive: { background: "var(--positive-soft)", color: "var(--positive)" },
    caution: { background: "var(--caution-soft)", color: "var(--caution)" },
    critical: { background: "var(--critical-soft)", color: "var(--critical)" },
    info: { background: "var(--info-soft)", color: "var(--info)" },
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontFamily: "var(--font-body)",
        fontWeight: "var(--fw-semibold)",
        fontSize: "12px",
        letterSpacing: "0.02em",
        lineHeight: 1,
        padding: "5px 10px",
        borderRadius: "var(--radius-sm)",
        ...tones[tone],
        ...style,
      }}
      {...rest}
    >
      {children}
    </span>
  );
}

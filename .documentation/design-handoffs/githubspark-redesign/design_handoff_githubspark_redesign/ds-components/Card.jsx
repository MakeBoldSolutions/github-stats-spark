import React from "react";

/**
 * Make Bold Solutions — Card
 * White surface on cream page; hairline warm border, restrained shadow.
 */
export function Card({
  children,
  as: Tag = "div",
  padding = "lg",
  interactive = false,
  accent = false,
  style = {},
  ...rest
}) {
  const pads = { none: 0, sm: "16px", md: "20px", lg: "28px", xl: "36px" };
  const [hover, setHover] = React.useState(false);

  const base = {
    background: "var(--surface-card)",
    border: "1px solid var(--border-default)",
    borderRadius: "var(--radius-lg)",
    padding: pads[padding],
    boxShadow: hover && interactive ? "var(--shadow-md)" : "var(--shadow-sm)",
    transition:
      "box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard), border-color var(--dur-base) var(--ease-standard)",
    transform: hover && interactive ? "translateY(-2px)" : "none",
    cursor: interactive ? "pointer" : "default",
    ...(accent ? { borderTop: "3px solid var(--brand)" } : {}),
    ...style,
  };

  return (
    <Tag
      style={base}
      onMouseEnter={() => interactive && setHover(true)}
      onMouseLeave={() => interactive && setHover(false)}
      {...rest}
    >
      {children}
    </Tag>
  );
}

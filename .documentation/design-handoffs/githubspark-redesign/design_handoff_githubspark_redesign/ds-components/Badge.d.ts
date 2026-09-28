import * as React from "react";

/** Compact status / category label in muted, finance-grade tones. */
export interface BadgeProps {
  children: React.ReactNode;
  /** @default "neutral" */
  tone?: "neutral" | "brand" | "accent" | "positive" | "caution" | "critical" | "info";
  style?: React.CSSProperties;
}

export function Badge(props: BadgeProps): JSX.Element;

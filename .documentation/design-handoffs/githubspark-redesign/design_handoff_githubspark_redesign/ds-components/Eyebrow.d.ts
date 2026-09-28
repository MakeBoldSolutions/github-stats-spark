import * as React from "react";

/** Signature letter-spaced uppercase label (ember). Sits above headings. */
export interface EyebrowProps {
  children: React.ReactNode;
  /** @default "div" */
  as?: keyof JSX.IntrinsicElements;
  /** @default "accent" */
  color?: "accent" | "brand" | "muted" | "onDark";
  style?: React.CSSProperties;
}

export function Eyebrow(props: EyebrowProps): JSX.Element;

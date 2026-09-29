import * as React from "react";

/** Surface container — white card on cream, hairline border, restrained shadow. */
export interface CardProps {
  children: React.ReactNode;
  /** Element/tag to render. @default "div" */
  as?: keyof JSX.IntrinsicElements;
  /** @default "lg" */
  padding?: "none" | "sm" | "md" | "lg" | "xl";
  /** Lift + deepen shadow on hover. @default false */
  interactive?: boolean;
  /** Add a 3px rust top rule. @default false */
  accent?: boolean;
  style?: React.CSSProperties;
}

export function Card(props: CardProps): JSX.Element;

import PropTypes from "prop-types";
import styles from "./Badge.module.css";

const TONE_CLASS = {
  neutral: styles.neutral,
  brand: styles.brand,
  accent: styles.accent,
  positive: styles.positive,
  caution: styles.caution,
  critical: styles.critical,
  info: styles.info,
};

export function Badge({ children, tone = "neutral", className = "", ...rest }) {
  const classes = [
    styles.badge,
    TONE_CLASS[tone] || TONE_CLASS.neutral,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  );
}

Badge.propTypes = {
  children: PropTypes.node,
  tone: PropTypes.oneOf([
    "neutral",
    "brand",
    "accent",
    "positive",
    "caution",
    "critical",
    "info",
  ]),
  className: PropTypes.string,
};

export default Badge;

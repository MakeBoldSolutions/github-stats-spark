import PropTypes from "prop-types";
import styles from "./Card.module.css";

const PADDING_CLASS = {
  none: styles.paddingNone,
  sm: styles.paddingSm,
  md: styles.paddingMd,
  lg: styles.paddingLg,
  xl: styles.paddingXl,
};

export function Card({
  children,
  as: Tag = "div",
  padding = "lg",
  interactive = false,
  accent = false,
  className = "",
  ...rest
}) {
  const classes = [
    styles.card,
    PADDING_CLASS[padding] || PADDING_CLASS.lg,
    interactive ? styles.interactive : "",
    accent ? styles.accent : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}

Card.propTypes = {
  children: PropTypes.node,
  as: PropTypes.elementType,
  padding: PropTypes.oneOf(["none", "sm", "md", "lg", "xl"]),
  interactive: PropTypes.bool,
  accent: PropTypes.bool,
  className: PropTypes.string,
};

export default Card;

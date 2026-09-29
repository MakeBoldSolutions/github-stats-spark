import PropTypes from "prop-types";
import styles from "./Eyebrow.module.css";

const COLOR_CLASS = {
  accent: styles.accent,
  brand: styles.brand,
  muted: styles.muted,
  onDark: styles.onDark,
};

export function Eyebrow({
  children,
  as: Tag = "div",
  color = "accent",
  className = "",
  ...rest
}) {
  const classes = [
    styles.eyebrow,
    COLOR_CLASS[color] || COLOR_CLASS.accent,
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

Eyebrow.propTypes = {
  children: PropTypes.node,
  as: PropTypes.elementType,
  color: PropTypes.oneOf(["accent", "brand", "muted", "onDark"]),
  className: PropTypes.string,
};

export default Eyebrow;

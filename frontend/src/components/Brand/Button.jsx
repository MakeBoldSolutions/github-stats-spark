import PropTypes from "prop-types";
import styles from "./Button.module.css";

const VARIANT_CLASS = {
  primary: styles.primary,
  accent: styles.accent,
  secondary: styles.secondary,
  ghost: styles.ghost,
  dark: styles.dark,
};

const SIZE_CLASS = {
  sm: styles.sm,
  md: styles.md,
  lg: styles.lg,
};

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
  className = "",
  ...rest
}) {
  const classes = [
    styles.button,
    VARIANT_CLASS[variant] || VARIANT_CLASS.primary,
    SIZE_CLASS[size] || SIZE_CLASS.md,
    fullWidth ? styles.fullWidth : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={classes}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}

Button.propTypes = {
  children: PropTypes.node,
  variant: PropTypes.oneOf(["primary", "accent", "secondary", "ghost", "dark"]),
  size: PropTypes.oneOf(["sm", "md", "lg"]),
  iconLeft: PropTypes.node,
  iconRight: PropTypes.node,
  fullWidth: PropTypes.bool,
  disabled: PropTypes.bool,
  type: PropTypes.string,
  onClick: PropTypes.func,
  className: PropTypes.string,
};

export default Button;

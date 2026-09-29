/**
 * Toast Component
 * Branded transient feedback notification, fixed and centered above the
 * mobile tab bar. Supports success, error, warning, and info variants.
 */

import { useEffect, useState, useCallback } from "react";
import { Check, X, AlertTriangle, Info } from "lucide-react";
import "./Toast.css";

const VARIANT_ICON = {
  success: Check,
  error: X,
  warning: AlertTriangle,
  info: Info,
};

export function Toast({
  message,
  variant = "info",
  duration = 3000,
  onClose,
  action = null,
}) {
  const [isVisible, setIsVisible] = useState(true);
  const [isLeaving, setIsLeaving] = useState(false);

  const handleClose = useCallback(() => {
    setIsLeaving(true);
    setTimeout(() => {
      setIsVisible(false);
      if (onClose) onClose();
    }, 300);
  }, [onClose]);

  useEffect(() => {
    if (duration <= 0) return;
    const timer = setTimeout(() => handleClose(), duration);
    return () => clearTimeout(timer);
  }, [duration, handleClose]);

  if (!isVisible) return null;

  const Icon = VARIANT_ICON[variant] || VARIANT_ICON.info;

  return (
    <div
      className={`toast toast--${variant} ${isLeaving ? "toast--leaving" : ""}`}
      role="alert"
      aria-live="polite"
    >
      <span className="toast__icon" aria-hidden="true">
        <Icon size={15} strokeWidth={2.5} />
      </span>

      <span className="toast__message">{message}</span>

      {action && (
        <button
          className="toast__action"
          onClick={() => {
            action.onClick?.();
            handleClose();
          }}
          type="button"
        >
          {action.label}
        </button>
      )}

      <button
        className="toast__close"
        onClick={handleClose}
        aria-label="Dismiss notification"
        type="button"
      >
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

/**
 * ToastContainer - Manages multiple toast notifications
 */
export function ToastContainer({ toasts = [], onRemove }) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-live="polite" aria-atomic="false">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          variant={toast.variant}
          duration={toast.duration}
          action={toast.action}
          onClose={() => onRemove(toast.id)}
        />
      ))}
    </div>
  );
}

export default Toast;

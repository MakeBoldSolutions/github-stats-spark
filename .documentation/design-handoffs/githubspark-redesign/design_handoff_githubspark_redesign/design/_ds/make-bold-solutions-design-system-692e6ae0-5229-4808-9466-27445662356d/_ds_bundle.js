/* @ds-bundle: {"format":4,"namespace":"MakeBoldSolutionsDesignSystem_692e6a","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Eyebrow","sourcePath":"components/core/Eyebrow.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"014d6d6ddbfe","components/core/Button.jsx":"c8908c298b66","components/core/Card.jsx":"eceb85977e60","components/core/Eyebrow.jsx":"ad76996cd14c","components/forms/Input.jsx":"30ff2a70d41c","ui_kits/website/ContactCTA.jsx":"a0321e1e1812","ui_kits/website/Hero.jsx":"e8a3b4ccab8d","ui_kits/website/Services.jsx":"f34933a2ec5c","ui_kits/website/SiteHeader.jsx":"066d6f72bd16","ui_kits/website/ValueStrip.jsx":"fdb8301529b0"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.MakeBoldSolutionsDesignSystem_692e6a = window.MakeBoldSolutionsDesignSystem_692e6a || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Make Bold Solutions — Badge
 * Compact status / category label. Muted, finance-grade tones.
 */
function Badge({
  children,
  tone = "neutral",
  style = {},
  ...rest
}) {
  const tones = {
    neutral: {
      background: "var(--ink-100)",
      color: "var(--ink-700)"
    },
    brand: {
      background: "var(--rust-50)",
      color: "var(--rust-600)"
    },
    accent: {
      background: "var(--ember-50)",
      color: "var(--ember-700)"
    },
    positive: {
      background: "var(--positive-soft)",
      color: "var(--positive)"
    },
    caution: {
      background: "var(--caution-soft)",
      color: "var(--caution)"
    },
    critical: {
      background: "var(--critical-soft)",
      color: "var(--critical)"
    },
    info: {
      background: "var(--info-soft)",
      color: "var(--info)"
    }
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
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
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Make Bold Solutions — Button
 * Confident, geometric button with modest radius and no-bounce interactions.
 */
function Button({
  children,
  variant = "primary",
  size = "md",
  iconLeft = null,
  iconRight = null,
  fullWidth = false,
  disabled = false,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: {
      padding: "8px 14px",
      fontSize: "14px",
      gap: "6px"
    },
    md: {
      padding: "11px 20px",
      fontSize: "15px",
      gap: "8px"
    },
    lg: {
      padding: "15px 28px",
      fontSize: "17px",
      gap: "10px"
    }
  };
  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: sizes[size].gap,
    fontFamily: "var(--font-body)",
    fontWeight: "var(--fw-semibold)",
    fontSize: sizes[size].fontSize,
    lineHeight: 1,
    letterSpacing: "0.01em",
    padding: sizes[size].padding,
    borderRadius: "var(--radius-md)",
    border: "1px solid transparent",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1,
    width: fullWidth ? "100%" : "auto",
    transition: "background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard)",
    textDecoration: "none",
    whiteSpace: "nowrap",
    ...style
  };
  const variants = {
    primary: {
      background: "var(--brand)",
      color: "var(--text-on-brand)"
    },
    accent: {
      background: "var(--accent)",
      color: "var(--white)"
    },
    secondary: {
      background: "transparent",
      color: "var(--brand-strong)",
      borderColor: "var(--brand)"
    },
    ghost: {
      background: "transparent",
      color: "var(--text-strong)"
    },
    dark: {
      background: "var(--surface-dark)",
      color: "var(--cream)"
    }
  };
  const hovers = {
    primary: {
      background: "var(--brand-strong)"
    },
    accent: {
      background: "var(--accent-strong)"
    },
    secondary: {
      background: "var(--brand-soft)"
    },
    ghost: {
      background: "var(--ink-100)"
    },
    dark: {
      background: "var(--ink-800)"
    }
  };
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const composed = {
    ...base,
    ...variants[variant],
    ...(hover && !disabled ? hovers[variant] : {}),
    ...(active && !disabled ? {
      transform: "translateY(1px)"
    } : {})
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    style: composed,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false)
  }, rest), iconLeft, children, iconRight);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Make Bold Solutions — Card
 * White surface on cream page; hairline warm border, restrained shadow.
 */
function Card({
  children,
  as: Tag = "div",
  padding = "lg",
  interactive = false,
  accent = false,
  style = {},
  ...rest
}) {
  const pads = {
    none: 0,
    sm: "16px",
    md: "20px",
    lg: "28px",
    xl: "36px"
  };
  const [hover, setHover] = React.useState(false);
  const base = {
    background: "var(--surface-card)",
    border: "1px solid var(--border-default)",
    borderRadius: "var(--radius-lg)",
    padding: pads[padding],
    boxShadow: hover && interactive ? "var(--shadow-md)" : "var(--shadow-sm)",
    transition: "box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard), border-color var(--dur-base) var(--ease-standard)",
    transform: hover && interactive ? "translateY(-2px)" : "none",
    cursor: interactive ? "pointer" : "default",
    ...(accent ? {
      borderTop: "3px solid var(--brand)"
    } : {}),
    ...style
  };
  return /*#__PURE__*/React.createElement(Tag, _extends({
    style: base,
    onMouseEnter: () => interactive && setHover(true),
    onMouseLeave: () => interactive && setHover(false)
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Eyebrow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Make Bold Solutions — Eyebrow
 * Signature letter-spaced uppercase label, in ember. Sits above headings.
 */
function Eyebrow({
  children,
  as: Tag = "div",
  color = "accent",
  style = {},
  ...rest
}) {
  const colors = {
    accent: "var(--accent-strong)",
    brand: "var(--brand)",
    muted: "var(--text-muted)",
    onDark: "var(--ember-300)"
  };
  return /*#__PURE__*/React.createElement(Tag, _extends({
    style: {
      fontFamily: "var(--font-body)",
      fontWeight: "var(--fw-semibold)",
      fontSize: "var(--fs-sm)",
      letterSpacing: "var(--ls-eyebrow)",
      textTransform: "uppercase",
      color: colors[color],
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Eyebrow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Eyebrow.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Make Bold Solutions — Input
 * Text field with label, hint and error. Calm, structured, ember focus.
 */
function Input({
  label,
  hint,
  error,
  id,
  type = "text",
  as = "input",
  style = {},
  ...rest
}) {
  const reactId = React.useId();
  const fieldId = id || reactId;
  const [focus, setFocus] = React.useState(false);
  const Tag = as;
  const field = {
    width: "100%",
    fontFamily: "var(--font-body)",
    fontSize: "var(--fs-base)",
    color: "var(--text-strong)",
    background: "var(--surface-card)",
    border: `1px solid ${error ? "var(--critical)" : focus ? "var(--accent)" : "var(--border-default)"}`,
    borderRadius: "var(--radius-md)",
    padding: as === "textarea" ? "12px 14px" : "11px 14px",
    outline: "none",
    boxShadow: focus ? "var(--ring-focus)" : "none",
    transition: "border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
    boxSizing: "border-box",
    minHeight: as === "textarea" ? "96px" : "auto",
    resize: as === "textarea" ? "vertical" : "none",
    ...style
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: "6px"
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      fontSize: "var(--fs-sm)",
      fontWeight: "var(--fw-semibold)",
      color: "var(--text-body)"
    }
  }, label), /*#__PURE__*/React.createElement(Tag, _extends({
    id: fieldId,
    type: as === "input" ? type : undefined,
    style: field,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false)
  }, rest)), (error || hint) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "var(--fs-sm)",
      color: error ? "var(--critical)" : "var(--text-muted)"
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/ContactCTA.jsx
try { (() => {
/* Make Bold Solutions — contact section with working form + footer */
function ContactCTA() {
  const {
    Card,
    Eyebrow,
    Input,
    Button
  } = window.MBS;
  const [sent, setSent] = React.useState(false);
  return /*#__PURE__*/React.createElement("section", {
    id: "contact",
    style: {
      background: "var(--surface-page)",
      padding: "var(--section-y) 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "0 var(--gutter)",
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: "clamp(2rem,5vw,5rem)",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Eyebrow, null, "Get in touch"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontSize: "clamp(2rem,3.5vw,3rem)",
      margin: "14px 0 0",
      letterSpacing: "-0.02em"
    }
  }, "Ready to take the next step?"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: "var(--fs-lg)",
      color: "var(--text-muted)",
      marginTop: 16,
      maxWidth: "44ch"
    }
  }, "Whether you're a growing business, a sole proprietor, or a nonprofit \u2014 let's have a conversation about how we can help. No obligation, no pressure."), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 28,
      display: "flex",
      flexDirection: "column",
      gap: 10,
      fontSize: 15
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "mailto:lesley.hazleton@makeboldsolutions.com",
    style: {
      color: "var(--text-link)",
      fontWeight: 500
    }
  }, "lesley.hazleton@makeboldsolutions.com"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-body)"
    }
  }, "Wichita, Kansas \u2014 serving businesses across the region"), /*#__PURE__*/React.createElement("a", {
    href: "https://www.linkedin.com/in/lesleyhazleton",
    style: {
      color: "var(--text-muted)"
    }
  }, "linkedin.com/in/lesleyhazleton"))), /*#__PURE__*/React.createElement(Card, {
    padding: "xl",
    style: {
      boxShadow: "var(--shadow-lg)"
    }
  }, sent ? /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      padding: "28px 8px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: 24,
      color: "var(--brand)"
    }
  }, "Thank you."), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-muted)",
      marginTop: 8
    }
  }, "We've received your note and will be in touch shortly."), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 18
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    onClick: () => setSent(false)
  }, "Send another"))) : /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      setSent(true);
    },
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Name",
    placeholder: "Jane Founder",
    required: true
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Company",
    placeholder: "Acme Inc."
  })), /*#__PURE__*/React.createElement(Input, {
    label: "Work email",
    type: "email",
    placeholder: "you@company.com",
    required: true
  }), /*#__PURE__*/React.createElement(Input, {
    label: "How can we help?",
    as: "textarea",
    placeholder: "A sentence or two about your situation."
  }), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    variant: "primary",
    size: "lg",
    fullWidth: true
  }, "Send message")))));
}
window.ContactCTA = ContactCTA;
function SiteFooter() {
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      background: "var(--surface-dark-2)",
      color: "var(--ink-300)",
      padding: "48px 0 40px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "0 var(--gutter)",
      display: "grid",
      gridTemplateColumns: "1.4fr 1fr",
      gap: 32,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 412 208",
    style: {
      width: 34
    }
  }, /*#__PURE__*/React.createElement("path", {
    fill: "var(--ember-400)",
    d: "M287.64,207.95H0L236.35,24.05l51.3,183.9Z"
  }), /*#__PURE__*/React.createElement("path", {
    fill: "var(--cream)",
    d: "M412,207.95H103.29L368.03,0l43.97,207.95Z"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: 18,
      color: "var(--cream)"
    }
  }, "Make", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ember-400)"
    }
  }, "Bold"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 8,
      fontFamily: "var(--font-body)",
      fontWeight: 600,
      fontSize: 11,
      letterSpacing: "0.4em",
      textTransform: "uppercase",
      color: "var(--ink-400)"
    }
  }, "Solutions"))), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--ink-300)",
      fontSize: 14,
      maxWidth: "40ch",
      marginTop: 16,
      lineHeight: 1.6
    }
  }, "Strategic financial leadership for small and midsize businesses, sole proprietors, and nonprofits. Wichita, Kansas.")), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "right"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: "0.16em",
      textTransform: "uppercase",
      color: "var(--ink-400)"
    }
  }, "Our technical division"), /*#__PURE__*/React.createElement("a", {
    href: "https://makeboldspark.com",
    style: {
      display: "inline-block",
      marginTop: 8,
      fontFamily: "var(--font-display)",
      fontWeight: 700,
      fontSize: 18,
      color: "var(--ember-300)"
    }
  }, "Make Bold Spark \u2197"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--ink-400)",
      marginTop: 20
    }
  }, "\xA9 2026 Make Bold Solutions. All rights reserved."))));
}
window.SiteFooter = SiteFooter;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/ContactCTA.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Hero.jsx
try { (() => {
/* Make Bold Solutions — homepage hero ("Big Firm Expertise. Small Firm Heart.") */
function Hero({
  onNav
}) {
  const {
    Eyebrow,
    Button
  } = window.MBS;
  const stats = [["30+", "Years Experience"], ["CPA", "Licensed & Certified"], ["2023", "CFO of the Year"], ["PwC", "Alumni"]];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--surface-page)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "clamp(3.5rem,7vw,6rem) var(--gutter)",
      display: "grid",
      gridTemplateColumns: "1.05fr 0.95fr",
      gap: "clamp(2rem,5vw,4.5rem)",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Eyebrow, null, "Fractional CFO & Financial Leadership"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: "clamp(2.6rem,4.6vw,4rem)",
      lineHeight: 1.04,
      letterSpacing: "-0.03em",
      margin: "18px 0 0"
    }
  }, "Big firm expertise.", /*#__PURE__*/React.createElement("br", null), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--brand)"
    }
  }, "Small firm heart.")), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: "var(--fs-xl)",
      color: "var(--text-muted)",
      maxWidth: "48ch",
      margin: "22px 0 0",
      lineHeight: 1.55
    }
  }, "Make Bold Solutions delivers senior-level financial leadership to growing businesses, sole proprietors, and nonprofits. Fractional by design \u2014 experienced CFO guidance and hands-on partnership, engaged at the scope and pace your organization needs."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 15,
      color: "var(--text-body)",
      margin: "20px 0 0",
      fontWeight: 500
    }
  }, "Lesley Hazleton, CPA \u2014 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--accent-strong)"
    }
  }, "Wichita Business Journal CFO of the Year, 2023")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 14,
      marginTop: 30,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    variant: "primary",
    onClick: () => onNav("Contact")
  }, "Get in touch"), /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    variant: "secondary",
    onClick: () => onNav("Services")
  }, "Get a cash flow snapshot"))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      borderRadius: "var(--radius-xl)",
      overflow: "hidden",
      boxShadow: "var(--shadow-xl)",
      aspectRatio: "4 / 5",
      background: "var(--ink-100)"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "https://images.unsplash.com/photo-1553877522-43269d4ea984?ixlib=rb-4.0.3&auto=format&fit=crop&w=1100&q=80",
    alt: "Small business financial consultation",
    style: {
      width: "100%",
      height: "100%",
      objectFit: "cover"
    }
  })), /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 412 208",
    style: {
      position: "absolute",
      left: -30,
      bottom: -28,
      width: 110,
      zIndex: -1
    }
  }, /*#__PURE__*/React.createElement("path", {
    fill: "var(--rust-100)",
    d: "M287.64,207.95H0L236.35,24.05l51.3,183.9Z"
  }), /*#__PURE__*/React.createElement("path", {
    fill: "var(--ink-100)",
    d: "M412,207.95H103.29L368.03,0l43.97,207.95Z"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: "1px solid var(--border-subtle)",
      background: "var(--surface-card)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "28px var(--gutter)",
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 24
    }
  }, stats.map(([n, l]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: 32,
      color: "var(--brand)",
      lineHeight: 1
    }
  }, n), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--text-muted)",
      marginTop: 6,
      letterSpacing: "0.04em"
    }
  }, l))))));
}
window.Hero = Hero;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Hero.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Services.jsx
try { (() => {
/* Make Bold Solutions — "How We Help" services grid (real services) */
function Services() {
  const {
    Card,
    Eyebrow,
    Badge
  } = window.MBS;
  const services = [["Fractional CFO", "Cash flow clarity, budgeting and forecasting you can act on, audit preparation, and strategic financial planning — senior-level leadership at the scope and pace your business requires.", ["Cash Flow Management", "Budgeting & Forecasting", "Audit Preparation", "Financial Reporting"]], ["Business Optimization", "From bookkeeping cleanup to building a close rhythm to getting your financial systems right — we help you build a foundation for confident decision-making.", ["Books Cleanup & Close Rhythm", "Process Improvement", "ERP & Systems Support", "Growth Planning"]], ["Nonprofit Governance", "Board treasurer services, financial governance, and compliance support — the same rigor we bring to every client, applied to organizations doing important community work.", ["Board Treasurer Services", "Financial Governance", "Grant & Fund Management", "Compliance Support"]], ["Fractional Corporate Controller", "Full-cycle accounting oversight, month-end close, reporting, and financial controls — the discipline of a dedicated controller, scaled to your engagement.", ["Month-End Close Management", "Financial Controls & Compliance", "Accounting Oversight", "Internal Reporting"]], ["Strategic Tax Planning", "Proactive tax strategy to minimize your liability and position your business for long-term financial health — not just at filing season.", ["Tax Strategy & Planning", "Entity Structure Optimization", "Deduction & Credit Maximization", "Year-Round Tax Advisory"]], ["Tax Preparation", "Accurate, thorough tax preparation for businesses, sole proprietors, and nonprofits — filed correctly and on time.", ["Business Tax Returns", "Sole Proprietor Filing", "Nonprofit Tax Compliance", "Multi-State Filing"]]];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--surface-sunken)",
      padding: "var(--section-y) 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "0 var(--gutter)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "60ch"
    }
  }, /*#__PURE__*/React.createElement(Eyebrow, null, "How we help"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontSize: "clamp(2rem,3.5vw,3rem)",
      margin: "14px 0 0",
      letterSpacing: "-0.02em"
    }
  }, "Expertise and partnership, on your terms."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: "var(--fs-lg)",
      color: "var(--text-muted)",
      marginTop: 16
    }
  }, "Whether you need cash flow clarity, a budget you can actually use, or someone to sit on your nonprofit board \u2014 we bring the expertise and do the work alongside you.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 20,
      marginTop: 44
    }
  }, services.map(([title, body, items]) => /*#__PURE__*/React.createElement(Card, {
    key: title,
    interactive: true,
    accent: true,
    style: {
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 20,
      margin: "0 0 8px"
    }
  }, title), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-muted)",
      fontSize: 14.5,
      lineHeight: 1.55,
      margin: 0
    }
  }, body), /*#__PURE__*/React.createElement("ul", {
    style: {
      listStyle: "none",
      padding: 0,
      margin: "16px 0 0",
      display: "flex",
      flexWrap: "wrap",
      gap: 6
    }
  }, items.map(it => /*#__PURE__*/React.createElement("li", {
    key: it
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "neutral"
  }, it)))), /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => e.preventDefault(),
    style: {
      marginTop: 16,
      fontSize: 14,
      fontWeight: 600,
      color: "var(--text-link)"
    }
  }, "Explore service \u2192"))))));
}
window.Services = Services;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Services.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SiteHeader.jsx
try { (() => {
/* Make Bold Solutions — site header / nav */
function SiteHeader({
  onNav,
  active
}) {
  const links = ["Services", "Fractional CFO", "Our Firm"];
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: "sticky",
      top: 0,
      zIndex: 20,
      background: "color-mix(in srgb, var(--surface-page) 88%, transparent)",
      backdropFilter: "blur(10px)",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "0 var(--gutter)",
      height: 72,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => {
      e.preventDefault();
      onNav("Home");
    },
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      textDecoration: "none"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 412 208",
    style: {
      width: 38,
      height: "auto"
    }
  }, /*#__PURE__*/React.createElement("path", {
    fill: "#982407",
    d: "M287.64,207.95H0L236.35,24.05l51.3,183.9Z"
  }), /*#__PURE__*/React.createElement("path", {
    fill: "#1E1E1E",
    d: "M412,207.95H103.29L368.03,0l43.97,207.95Z"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: 20,
      color: "var(--ink-900)",
      letterSpacing: "-0.02em"
    }
  }, "Make", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--brand)"
    }
  }, "Bold"))), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 4
    }
  }, links.map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    onClick: e => {
      e.preventDefault();
      onNav(l);
    },
    style: {
      padding: "8px 14px",
      fontSize: 15,
      fontWeight: 500,
      color: active === l ? "var(--brand)" : "var(--text-body)",
      textDecoration: "none",
      borderRadius: "var(--radius-sm)"
    }
  }, l)), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 8
    }
  }, /*#__PURE__*/React.createElement(window.MBS.Button, {
    size: "sm",
    variant: "primary",
    onClick: () => onNav("Contact")
  }, "Get in touch \u2192")))));
}
window.SiteHeader = SiteHeader;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SiteHeader.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/ValueStrip.jsx
try { (() => {
/* Make Bold Solutions — "Why Choose Us" dark strip + signature quote */
function ValueStrip() {
  const {
    Eyebrow
  } = window.MBS;
  const reasons = [["Direct senior-level access", "No junior associates, no hand-offs. You get direct access to a seasoned, award-winning CPA who personally handles your finances and knows your business."], ["Built for businesses others overlook", "Most firms pass over small businesses and sole proprietors. We exist specifically to serve you — the same expertise Fortune 500s get, on your terms and budget."], ["Outcomes, not billable hours", "We focus on results you can see: cash flow clarity, a budget you can use, books you can trust, and a financial plan that actually helps you decide."]];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--surface-dark)",
      color: "var(--cream)",
      padding: "var(--section-y) 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      padding: "0 var(--gutter)"
    }
  }, /*#__PURE__*/React.createElement(Eyebrow, {
    color: "onDark"
  }, "Why choose us"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 40,
      marginTop: 36
    }
  }, reasons.map(([t, b], i) => /*#__PURE__*/React.createElement("div", {
    key: t
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: 38,
      color: "var(--ember-400)",
      lineHeight: 1
    }
  }, "0", i + 1), /*#__PURE__*/React.createElement("h3", {
    style: {
      color: "var(--cream)",
      fontSize: 20,
      margin: "16px 0 8px"
    }
  }, t), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--ink-300)",
      fontSize: 15,
      lineHeight: 1.6
    }
  }, b)))), /*#__PURE__*/React.createElement("blockquote", {
    style: {
      margin: "56px 0 0",
      paddingTop: 40,
      borderTop: "1px solid var(--ink-700)",
      fontFamily: "var(--font-display)",
      fontWeight: 800,
      fontSize: "clamp(1.75rem,3.2vw,2.75rem)",
      letterSpacing: "-0.02em",
      color: "var(--cream)",
      textAlign: "center",
      lineHeight: 1.2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ember-400)"
    }
  }, "\u201C"), "Every business deserves a great CFO.", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ember-400)"
    }
  }, "\u201D"))));
}
window.ValueStrip = ValueStrip;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/ValueStrip.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Eyebrow = __ds_scope.Eyebrow;

__ds_ns.Input = __ds_scope.Input;

})();

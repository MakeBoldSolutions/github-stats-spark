import {
  AlertTriangle,
  BarChart3,
  Globe,
  LayoutGrid,
  Rocket,
  Search,
  Settings,
  ShieldAlert,
} from "lucide-react";

/**
 * The dashboard's sections, in display order. A later capability adds its
 * content to an existing section instead of adding a top-level tab. A
 * section with `requires` is shown only when that capability has data
 * (see visibleSections), so Sites, Delivery and Presence stay hidden until
 * they have something to show.
 *
 * `hash` is the canonical URL fragment; `aliases` keep older links working.
 * `mobileRank` orders the mobile tab bar, which shows the first few and
 * puts the rest behind "More".
 */
export const SECTIONS = [
  {
    id: "table",
    hash: "",
    label: "Overview",
    navLabel: "Switch to repository overview",
    Icon: LayoutGrid,
    mobileRank: 1,
  },
  {
    id: "visualizations",
    hash: "visualizations",
    aliases: ["insights"],
    label: "Insights",
    navLabel: "Insights — switch to visualizations view",
    Icon: BarChart3,
    mobileRank: 4,
  },
  {
    id: "attention",
    hash: "attention",
    aliases: ["health"],
    label: "Health",
    navLabel: "Health — repositories needing attention",
    Icon: AlertTriangle,
    mobileRank: 2,
  },
  {
    id: "security",
    hash: "security",
    label: "Security",
    navLabel: "Security — Dependabot alerts",
    Icon: ShieldAlert,
    requires: "security",
    mobileRank: 3,
  },
  {
    id: "sites",
    hash: "sites",
    label: "Sites",
    navLabel: "Sites — website health",
    Icon: Globe,
    requires: "sites",
    mobileRank: 5,
  },
  {
    id: "delivery",
    hash: "delivery",
    label: "Delivery",
    navLabel: "Delivery — releases and deployments",
    Icon: Rocket,
    requires: "delivery",
    mobileRank: 6,
  },
  {
    id: "presence",
    hash: "presence",
    label: "Presence",
    navLabel: "Presence — search and traffic",
    Icon: Search,
    requires: "presence",
    mobileRank: 7,
  },
  {
    id: "admin",
    hash: "admin",
    aliases: ["sources"],
    label: "Admin",
    navLabel: "Admin — sources, lists and domains",
    Icon: Settings,
    requires: "admin",
    mobileRank: 8,
  },
];

/** Sections whose capability is available, e.g. `{security: true}`. */
export function visibleSections(available = {}) {
  return SECTIONS.filter(
    (section) => !section.requires || available[section.requires],
  );
}

/** The section id for a URL hash; unknown hashes show the Overview. */
export function sectionFromHash(hash) {
  const value = String(hash || "").replace(/^#/, "");
  const match = SECTIONS.find(
    (section) =>
      section.hash === value || (section.aliases || []).includes(value),
  );
  return match ? match.id : "table";
}

/** The URL hash for a section id. */
export function hashForSection(id) {
  return SECTIONS.find((section) => section.id === id)?.hash ?? "";
}

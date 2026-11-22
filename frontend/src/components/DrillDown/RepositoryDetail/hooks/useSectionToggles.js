import { useState } from "react";

const INITIAL_SECTIONS = {
  summary: true,
  website: true,
  info: true,
  signals: true,
  remediation: true,
  security: true,
  commits: false,
  languages: false,
  tech: false,
  quality: false,
};

export function useSectionToggles() {
  const [expandedSections, setExpandedSections] = useState(INITIAL_SECTIONS);

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  return { expandedSections, toggleSection };
}

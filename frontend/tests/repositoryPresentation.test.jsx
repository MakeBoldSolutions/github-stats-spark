import { describe, it, expect } from "vitest";
import {
  getLanguageColor,
  getTierTone,
  getTierLabel,
  sanitizeSummaryText,
  getRepositorySummaryExcerpt,
  getRelativePushLabel,
  formatSourceDate,
  getRepositoryHealthPresentation,
} from "../src/utils/repositoryPresentation";

describe("getLanguageColor", () => {
  it("returns the approved color for a known language", () => {
    expect(getLanguageColor("Python")).toBe("#2f6f4c");
  });

  it("falls back to the neutral color for an unknown language", () => {
    expect(getLanguageColor("COBOL")).toBe("#9b988f");
    expect(getLanguageColor(undefined)).toBe("#9b988f");
  });
});

describe("getTierTone / getTierLabel", () => {
  it("maps every known tier to its approved badge tone", () => {
    expect(getTierTone("critical")).toBe("critical");
    expect(getTierTone("elevated")).toBe("caution");
    expect(getTierTone("watch")).toBe("accent");
    expect(getTierTone("healthy")).toBe("positive");
  });

  it("falls back to a neutral tone/label for an unknown tier", () => {
    expect(getTierTone("mystery")).toBe("neutral");
    expect(getTierTone(undefined)).toBe("neutral");
    expect(getTierLabel(undefined)).toBe("Unknown");
  });
});

describe("sanitizeSummaryText", () => {
  it("strips markdown links but keeps their visible text", () => {
    expect(sanitizeSummaryText("See [docs](https://example.com/docs)")).toBe(
      "See docs",
    );
  });

  it("strips markdown images/badges entirely", () => {
    expect(
      sanitizeSummaryText("![build](https://img.shields.io/badge.svg) passing"),
    ).toBe("passing");
  });

  it("strips bare URLs and leftover bracket fragments", () => {
    expect(sanitizeSummaryText("Visit https://example.com now [ref]")).toBe(
      "Visit now",
    );
  });

  it("strips markdown emphasis/heading punctuation", () => {
    expect(sanitizeSummaryText("**Bold** _italic_ `code` #Heading")).toBe(
      "Bold italic code Heading",
    );
  });

  it("returns an empty string for empty/non-string input", () => {
    expect(sanitizeSummaryText("")).toBe("");
    expect(sanitizeSummaryText(null)).toBe("");
    expect(sanitizeSummaryText(undefined)).toBe("");
  });
});

describe("getRepositorySummaryExcerpt", () => {
  it("prefers ai_summary.summary, then summary.text, then description", () => {
    expect(
      getRepositorySummaryExcerpt({
        ai_summary: { summary: "AI summary" },
        summary: { text: "Structured summary" },
        description: "Description",
      }),
    ).toBe("AI summary");

    expect(
      getRepositorySummaryExcerpt({
        summary: { text: "Structured summary" },
        description: "Description",
      }),
    ).toBe("Structured summary");

    expect(getRepositorySummaryExcerpt({ description: "Description" })).toBe(
      "Description",
    );
  });

  it("truncates long text to the requested excerpt length with an ellipsis", () => {
    const long = "a".repeat(200);
    const excerpt = getRepositorySummaryExcerpt({ description: long }, 140);
    expect(excerpt.length).toBe(140);
    expect(excerpt.endsWith("…")).toBe(true);
  });

  it("returns an empty string when no descriptive text is available", () => {
    expect(getRepositorySummaryExcerpt({})).toBe("");
  });
});

describe("getRelativePushLabel", () => {
  it("labels 0/1 days specially", () => {
    expect(getRelativePushLabel(0)).toBe("Today");
    expect(getRelativePushLabel(1)).toBe("Yesterday");
  });

  it("labels days/weeks/months/years", () => {
    expect(getRelativePushLabel(3)).toBe("3d ago");
    expect(getRelativePushLabel(14)).toBe("2w ago");
    expect(getRelativePushLabel(60)).toBe("2mo ago");
    expect(getRelativePushLabel(730)).toBe("2y ago");
  });

  it("returns a safe fallback for missing or invalid values", () => {
    expect(getRelativePushLabel(null)).toBe("Unknown");
    expect(getRelativePushLabel(undefined)).toBe("Unknown");
    expect(getRelativePushLabel(NaN)).toBe("Unknown");
    expect(getRelativePushLabel(-5)).toBe("Unknown");
  });
});

describe("formatSourceDate", () => {
  it("formats a valid ISO timestamp", () => {
    expect(formatSourceDate("2026-09-28T16:25:21.777778")).toContain("2026");
  });

  it("returns a safe fallback for missing or invalid timestamps", () => {
    expect(formatSourceDate(null)).toBe("Unknown");
    expect(formatSourceDate("not-a-date")).toBe("Unknown");
  });
});

describe("getRepositoryHealthPresentation", () => {
  it("uses source attention_score and attention_metrics.tier directly", () => {
    const presentation = getRepositoryHealthPresentation({
      attention_score: 28.5,
      attention_metrics: { tier: "watch" },
    });
    expect(presentation.score).toBe(28.5);
    expect(presentation.tier).toBe("watch");
    expect(presentation.tone).toBe("accent");
    expect(presentation.label).toBe("Watch");
  });

  it("falls back safely when attention metrics are absent", () => {
    const presentation = getRepositoryHealthPresentation({});
    expect(presentation.score).toBeNull();
    expect(presentation.tier).toBeNull();
    expect(presentation.tone).toBe("neutral");
    expect(presentation.label).toBe("Unknown");
  });
});

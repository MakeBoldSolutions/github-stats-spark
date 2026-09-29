# github-stats-spark Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-06

## Active Technologies
- Python 3.11+ backend, React 19 + Vite frontend + PyGithub (backend), Chart.js + react-chartjs-2 (frontend) — NOT Recharts (001-dashboard-visual-enhancements)
- JSON files (`data/repositories.json`), file-based cache (`.cache/`) (001-dashboard-visual-enhancements)
- JavaScript with React 19 + React, Vite, Chart.js, react-chartjs-2, react-markdown, Workbox, and new `lucide-react` (001-make-bold-solutions-redesign)
- Static `repositories.json` data plus existing browser cache (001-make-bold-solutions-redesign)

- Python 3.11+ backend, PowerShell 7 automation, Markdown documentation artifacts + PyGithub, PyYAML, svgwrite, tenacity, pytest/pytest-cov, existing theme helpers in `spark.visualizer` (001-remediate-high-issues)
- Filesystem-backed YAML, Markdown, SVG, JSON, and `.cache` content-addressed cache (001-remediate-high-issues)
- Python 3.11+ backend, JavaScript/React 19 frontend + PyGithub 2.1.1+, requests, tenacity, PyYAML, pytest, Vitest, Vite 7 (001-security-pr-api-upgrade)
- File-based outputs in `data/`, `output/`, `docs/`; content-addressed cache in `.cache/` (001-security-pr-api-upgrade)

- JavaScript ES2022, React 19.2.3, Node.js 18+ + Vite 7.3.0 (build tool), Chart.js 4.5.1 + react-chartjs-2 (visualizations), @use-gesture/react 10.3.1 (touch gestures), Dexie 4.2.1 (offline storage), react-modal-sheet 5.2.1 (mobile sheets) (001-mobile-first-ui)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

npm test; npm run lint

## Code Style

JavaScript ES2022, React 19.2.3, Node.js 18+: Follow standard conventions

## Recent Changes
- 001-make-bold-solutions-redesign: Added JavaScript with React 19 + React, Vite, Chart.js, react-chartjs-2, react-markdown, Workbox, and new `lucide-react`
- 001-dashboard-visual-enhancements: Added Python 3.11+ backend, React 19 + Vite frontend + PyGithub (backend), Chart.js + react-chartjs-2 (frontend) — NOT Recharts

- 001-security-pr-api-upgrade: Added Python 3.11+ backend, JavaScript/React 19 frontend + PyGithub 2.1.1+, requests, tenacity, PyYAML, pytest, Vitest, Vite 7


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

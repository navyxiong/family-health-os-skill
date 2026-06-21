# Changelog

All notable changes to **Family Health OS** skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] — 2026-06-14

### Added
- **7-skill auto-routing** — health-trend-analyzer, family-health-analyzer, medical-entity-extractor, pubmed-search, sleep-analyzer, nutrition-analyzer, fitness-analyzer
- **Report analyzer workflow** (`workflows/report-analyzer.md`) — 6-step pipeline: OCR → classify → extract → write → aggregate → summarize
- **Doctor handoff template** (`templates/doctor-handoff-summary.md`) — 8-section structured handover for transfers
- **Smoke test** (`scripts/smoke_test.py`) — 6 verification suites for CI
- **Reference docs** — `report-type-rules.md`, `zero-confirmation-workflow.md`, `image-cache-handling.md`, `vision-report-parsing.md`, `field-mapping.md`, `data-management.md`
- **Timeline support for 29 event types × 9 categories**

### Changed
- SKILL.md frontmatter updated to v1.3.0 with full skill index
- `aggregate_timeline.py` no longer silently wraps output — caller must redirect to file
- `generate_summary.py` now handles `itemName`/`name` dual field naming (regression fixed)

### Fixed
- `tool_layer._load()` now handles both `{"timeline": {...}}` and `[...]` formats
- `build_timeline.py` `key` view auto-applies ⚠️ on `severity="warning"` events
- Image cache path fallback: validates `image_url` with `os.path.exists()` before calling `vision_analyze`

## [1.2.0] — 2026-05-20

### Added
- `build_timeline.py` — multi-view renderer (patient / disease / time / hospitalization / consultation)
- `generate_summary.py` — 4 types of clinical summaries
- `events.json` — flat event query view generated from `timeline.json`

### Changed
- Unified CRUD through `memory_manager.py` with `fcntl` file locks
- `tool_layer.py` becomes the only public API for the agent

## [1.1.0] — 2026-04-10

### Added
- `aggregate_timeline.py` — auto-aggregates 8 data sources into `timeline.json`
- `workflows/memory-manager.md` — unified data management spec
- Cascade delete: removing a patient auto-cleans all linked records

## [1.0.0] — 2026-03-15

### Added
- Initial release
- 7 JSON Schema definitions: patients, diseases, exams, medications, hospitalizations, tasks, timeline
- `scripts/memory_manager.py` — basic CRUD with file locks
- `scripts/tool_layer.py` — semantic API for the agent
- 4 base workflows: member management, exam logging, hospitalization tracking, reminders

---

## Upcoming

### [1.4.0] — Planned
- `bulk_import` interface for Excel/CSV from hospital HIS systems
- Multi-language support (English schema documentation)
- Web UI for timeline visualization (separate sibling repo)
- Anomaly detection rules engine (configurable thresholds per lab)
- PDF report generation (currently Markdown only)

[Unreleased]: https://github.com/navyxiong/family-health-os-skill/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/navyxiong/family-health-os-skill/releases/tag/v1.3.0
[1.2.0]: https://github.com/navyxiong/family-health-os-skill/releases/tag/v1.2.0
[1.1.0]: https://github.com/navyxiong/family-health-os-skill/releases/tag/v1.1.0
[1.0.0]: https://github.com/navyxiong/family-health-os-skill/releases/tag/v1.0.0

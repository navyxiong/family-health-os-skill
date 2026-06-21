# Family Health OS — Hermes Agent Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-blueviolet)](https://hermes-agent.nousresearch.com/docs)
[![Version](https://img.shields.io/badge/version-1.3.0-green)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#)

> A **structured information hub** for managing a family's lifetime medical records inside [Hermes Agent](https://hermes-agent.nousresearch.com/docs). It does **not** diagnose or prescribe — it organizes data so humans and clinicians can decide.

[中文说明](README.zh-CN.md) · [Changelog](CHANGELOG.md) · [Quick Start](#quick-start) · [Architecture](#architecture)

---

## What it does

Turn your Hermes Agent into a **family medical record keeper** that:

- 🧬 **Tracks every family member** — profiles, allergies, family history
- 📋 **Ingests exam & lab reports** — auto-flags abnormal values (↑ ↓ ↑↑ ↓↓)
- 🏥 **Logs full hospitalization journeys** — admission → daily progress → surgery → discharge
- 💊 **Manages medications** — start / adjust / stop, with renewal reminders
- ⏱ **Auto-aggregates a unified timeline** — 29 event types × 9 categories
- 📝 **Generates 4 types of clinical summaries** — for handover, MDT, follow-up, transfer
- 🔬 **Routes 7 analysis skills** — trend / family / sleep / nutrition / fitness / literature / entity extraction
- 📷 **OCR medical report images** — PDFs / CT scans / lab sheets → structured JSON

All data lives in plain JSON files under your profile directory. **Zero external services. Zero vendor lock-in. 100% local.**

---

## Quick Start

### Option 1: One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/navyxiong/family-health-os-skill/main/install.sh | bash
```

### Option 2: Manual install

```bash
# 1. Install Hermes Agent (≥0.5)
#    See https://hermes-agent.nousresearch.com/docs

# 2. Clone this repo
git clone https://github.com/navyxiong/family-health-os-skill.git

# 3. Copy into your profile
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE="${1:-family-health-os}"
mkdir -p "$HERMES_HOME/profiles/$PROFILE/skills"
cp -R family-health-os-skill/skills/. "$HERMES_HOME/profiles/$PROFILE/skills/"

# 4. Create empty data directory
mkdir -p "$HERMES_HOME/profiles/$PROFILE/memory/data"

# 5. Activate the profile
hermes profile use $PROFILE
```

### 6. First command

Tell your agent:

> *"给奶奶建一份档案：姓名王建国，男，1948年5月30日出生，过敏青霉素。"*

The agent will create `memory/data/patients.json`, validate against the schema, and write a 1-line confirmation:

```
已录入。患者档案 | 王建国 | 1事件
```

---

## Architecture

Five-layer pipeline from raw input to clinical summary:

```
┌─────────────────────────────────────────────────────────┐
│ Layer 0: Schema        memory/schemas/*.json            │
│ Layer 0.5: Memory Mgr  scripts/memory_manager.py        │
│ Layer 1: Raw Data      memory/data/*.json               │
│ Layer 2: Aggregation   scripts/aggregate_timeline.py   │
│ Layer 3: Query/Render  scripts/build_timeline.py        │
│ Layer 4: Summarization scripts/generate_summary.py      │
└─────────────────────────────────────────────────────────┘
         ↑ Agent calls scripts/tool_layer.py
```

Every write auto-triggers aggregation. Every query reads the pre-built `timeline.json`.

---

## Repository layout

```
family-health-os-skill/
├── README.md              # this file (English facade)
├── README.zh-CN.md        # detailed Chinese guide
├── LICENSE                # MIT + medical disclaimer
├── CHANGELOG.md           # version history
├── CONTRIBUTING.md        # how to contribute
├── requirements.txt       # Python deps
├── install.sh             # one-line installer
├── skills/
│   └── productivity/
│       └── family-health-os/
│           ├── SKILL.md   # main entry — read this first
│           ├── scripts/   # 6 Python engines
│           ├── references/  # 8 deep-dive guides
│           ├── workflows/ # 4 procedural workflows
│           ├── templates/ # doctor-handoff template
│           └── docs/      # event schema spec
└── examples/
    ├── basic-usage.md     # 3 real-world scenarios
    └── sample-data/       # anonymized demo records
```

---

## Core philosophy

1. **Structured, not smart** — It organizes. It does not diagnose, prescribe, or interpret. Every output is a faithful reflection of source data + provenance.
2. **Zero confirmation** — When you ask the agent to "log this lab report", it logs it. No "are you sure?" pop-ups. You typed it; you meant it.
3. **Local-first** — All data stays on your machine as plain JSON. No cloud, no SaaS, no telemetry.
4. **Schemas before scripts** — Every field is defined in a JSON Schema (draft-07) before any code touches it. This makes data import/export, validation, and migration trivial.
5. **Provenance on every event** — Every timeline event records `sourceDoctor`, `sourceInstitution`, `sourceType`. The agent never injects its own judgment.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: family-health-os` | Skill not in `skills/productivity/` | Re-check path: must be 3 levels deep |
| `FileNotFoundError: memory/data/patients.json` | Data dir not created | `mkdir -p ~/.hermes/profiles/<name>/memory/data` |
| Writes go to wrong profile | Active profile mismatch | `hermes profile use <name>` |
| `JSONDecodeError` on timeline.json | Aggregate output corruption | `rm memory/data/timeline.json && python3 scripts/aggregate_timeline.py <patientId>` |
| OCR returns empty | Image too small / wrong format | Re-upload at ≥1080p JPG/PNG |

---

## Medical disclaimer

This software is **not a medical device**. It does not provide diagnosis, treatment, prognosis, or clinical decision support. All medical information stored here must be reviewed and acted upon by qualified healthcare professionals. See full disclaimer in [LICENSE](LICENSE).

---

## License

[MIT](LICENSE) © 2026 Family Health OS Contributors


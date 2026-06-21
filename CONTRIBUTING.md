# Contributing to Family Health OS

Thank you for considering a contribution! 🎉

This skill is **a structured information management tool** for family medical records. Contributions that improve schema completeness, workflow ergonomics, or analysis skill accuracy are all welcome.

## Code of conduct

- **No medical advice in code or docs.** This skill is an information hub, not a clinical decision support tool.
- **No real patient data in PRs, issues, or examples.** Use the `examples/sample-data/` anonymized fixtures.
- **Be precise about data provenance.** Every event in a timeline must cite `sourceDoctor` and `sourceInstitution`.

## How to contribute

### 1. Issues first

Before writing code, open an issue describing:
- The problem you want to solve
- A minimal repro (with sample data)
- Your proposed approach

Maintainers will review and suggest the right layer to modify (schema vs. workflow vs. script).

### 2. Fork & branch

```bash
git clone https://github.com/navyxiong/family-health-os-skill.git
cd family-health-os-skill
git checkout -b feat/your-feature-name
```

### 3. Make your change

Pick the right layer:

| You want to... | Edit |
|----------------|------|
| Add a new field to an entity | `skills/.../references/schema-guide.md` (docs) + JSON Schema in `memory/schemas/` |
| Add a new event type | `skills/.../docs/event-schema.md` (enum + category map) |
| Add a new workflow | `skills/.../workflows/<name>.md` + cross-link from SKILL.md |
| Fix a script bug | `skills/.../scripts/<file>.py` + add a test to `smoke_test.py` |
| Add a new analysis skill | `skills/.../SKILL.md` (routing table) + register in skill metadata |
| Improve OCR accuracy | `skills/.../references/report-type-rules.md` + `workflows/report-analyzer.md` |

### 4. Add a test

If you changed a script, extend `scripts/smoke_test.py`. Run locally:

```bash
cd skills/productivity/family-health-os
python3 scripts/smoke_test.py
```

### 5. Bump version

If your change is user-visible, bump the version in:
- `skills/.../SKILL.md` (frontmatter `version:` field)
- `CHANGELOG.md` (new section at top)
- A new git tag on merge

### 6. Open a PR

- Title: `feat: <short summary>` or `fix: <short summary>`
- Body: link the issue + describe what changed + show test output
- One logical change per PR

## Style guide

### Python

- Python 3.10+, standard library only for core scripts
- Type hints on all public functions
- Docstrings: short, imperative ("Aggregate timeline events", not "This function aggregates...")
- No `print` in library code — return values, let the caller log

### Markdown

- Reference docs in `references/` — concise, table-heavy, one concept per file
- Workflows in `workflows/` — numbered steps, exact command, expected output
- Templates in `templates/` — placeholder syntax `{{field_name}}`

### Schemas

- UUID v4 for all `id` fields
- ISO 8601 for all dates (`YYYY-MM-DD` for date, `YYYY-MM-DDTHH:MM:SSZ` for datetime)
- Foreign keys named after the source entity (`patientId`, `relatedDiseaseIds[]`, etc.)
- Enums defined in `docs/event-schema.md` and the entity's reference doc

## Pitfalls to avoid

These are real bugs we've already hit — please don't repeat them:

1. **Path depth** — Scripts compute `DATA_DIR` with 4 `..` levels from `scripts/` to `profile root`. If you add a new script, verify with `os.path.exists(DATA_DIR)`.
2. **timeline.json format** — It's a JSON array `[{...}, ...]`, one entry per patient. Don't wrap it in `{"timeline": [...]}`. If you read it, handle both formats.
3. **itemName vs name** — Exam items use `itemName`. The legacy `name` field exists in some old data. Always use `i.get('itemName', i.get('name', '?'))` defensively.
4. **Aggregate stdout** — `aggregate_timeline.py` writes to stdout, not to a file. The caller must `> timeline.json` redirect.
5. **No `dischargeDate` from a transfer recommendation** — A doctor's note "建议转上级医院" does not constitute a discharge. Only mark `dischargeDate` when there's an actual discharge summary.

## License

By contributing, you agree that your contributions will be licensed under [MIT](LICENSE).

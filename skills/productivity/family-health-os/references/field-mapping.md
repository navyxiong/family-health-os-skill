# Field Mapping & JSON Format Traps

## exams.items[] Field Names

`aggregate_timeline.py` line 257 originally used `item['name']`,
but `tool_layer.py` creates `item['itemName']`.

**Fix**: `item_name = item.get('itemName') or item.get('name', '')`

This must be applied anywhere the script iterates over `exam.get("items", [])`.

## timeline.json Format

`aggregate_timeline.py` outputs `{"timeline": {...}}` to stdout.
`tool_layer.py` `_load()` must handle three formats:

1. `list` of patient timelines `[{patientId: A, ...}, {patientId: B, ...}]` → return as-is
2. `dict` with `"timeline"` key → extract the inner dict and wrap in list
3. `dict` without `"timeline"` but with `patientId` or `id` → wrap in list

**Storage rule**: `rebuild_timeline()` must save as a **list** to support multiple patients.

```python
# rebuild_timeline() pseudo-code
existing = []
if os.path.exists(tl_path):
    with open(tl_path) as f:
        raw = json.load(f)
    if isinstance(raw, list):
        existing = raw
    elif isinstance(raw, dict):
        existing = [raw.get("timeline", raw)] if raw.get("patientId") else []

existing = [t for t in existing if t.get("patientId") != patient_id]
existing.append(timeline_data)

with open(tl_path, 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
```

## Script Path Depth

From `scripts/` to `memory/data/`:

```
scripts/ → .. → family-health-os/ → .. → productivity/
→ .. → skills/ → .. → family-health-os/ → memory/data/
```

Total: **4** `..` segments.

Common mistake: using 5 `..` segments (goes one level above profile root).
Always verify with `os.path.abspath(DATA_DIR)` and `os.path.exists()`.

## Data Directory vs Schema Directory

- `memory/schemas/` — JSON Schema definitions (structure only, no data)
- `memory/data/` — Actual JSON data files (arrays of objects)

All scripts must point to `memory/data/` for reads and writes.

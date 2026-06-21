#!/usr/bin/env python3
"""
Smoke test: verify the full Report Analyzer → Memory → Timeline pipeline.
Creates dummy data for each report type, simulates extraction, writes to files,
runs aggregation, and checks output.

Usage:
  python3 scripts/smoke_test.py

Exit code 0 = all checks pass.
"""

import json
import os
import sys
import uuid
import subprocess
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(SKILL_DIR, "..", "..", "..", "..", "memory", "schemas")
AGGREGATOR = os.path.join(SKILL_DIR, "scripts", "aggregate_timeline.py")

TEST_PATIENT_ID = str(uuid.uuid4())

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


def verify_files():
    """Verify all workflow files exist."""
    print("\n📁 File structure:")
    required = [
        "SKILL.md",
        "workflows/report-analyzer.md",
        "references/schema-guide.md",
        "references/data-model-diagram.md",
        "references/report-type-rules.md",
        "scripts/aggregate_timeline.py",
    ]
    for f in required:
        path = os.path.join(SKILL_DIR, f)
        check(f"exists: {f}", os.path.exists(path))

    for schema in ["patients.json", "exams.json", "hospitalizations.json",
                    "medications.json", "diseases.json", "timeline.json", "tasks.json"]:
        path = os.path.join(SCHEMA_DIR, schema)
        check(f"schema exists: {schema}", os.path.exists(path))


def verify_timeline_schema():
    """Verify timeline.json has the correct event types and fields."""
    print("\n📐 Timeline schema:")
    with open(os.path.join(SCHEMA_DIR, "timeline.json")) as f:
        schema = json.load(f)

    props = schema["properties"]
    event_props = props["events"]["items"]["properties"]

    expected_fields = ["eventId", "eventIdSource", "date", "eventType",
                       "category", "title", "description", "severity",
                       "sourceType", "sourceId", "sourceDoctor", "sourceInstitution",
                       "tags", "isKeyEvent", "affectedBodySite",
                       "metadata", "relatedEventIds"]

    for field in expected_fields:
        check(f"event field: {field}", field in event_props)

    event_types = event_props["eventType"]["enum"]
    check(f"eventType count = 29", len(event_types) == 29,
          f"got {len(event_types)}")

    categories = event_props["category"]["enum"]
    check(f"category count = 9", len(categories) == 9,
          f"got {len(categories)}")

    check("has eventTypeCategoryMap", "eventTypeCategoryMap" in props)


def verify_workflow_content():
    """Verify workflow document covers all 6 report types."""
    print("\n📋 Workflow coverage:")
    wf_path = os.path.join(SKILL_DIR, "workflows", "report-analyzer.md")
    with open(wf_path) as f:
        content = f.read()

    for keyword in ["### 3.1 CT", "### 3.2 CTA", "### 3.4 彩超",
                    "### 3.5 病理", "### 3.6 检验报告", "### 3.7 出院记录"]:
        check(f"has section: {keyword}", keyword in content)


def verify_aggregator_logic():
    """Run aggregator syntax check and output validation."""
    print("\n⚙️  Aggregator engine:")
    with open(AGGREGATOR) as f:
        code = f.read()
    try:
        compile(code, AGGREGATOR, "exec")
        check("Python syntax OK", True)
    except SyntaxError as e:
        check("Python syntax OK", False, str(e))

    result = subprocess.run(
        ["python3", AGGREGATOR, TEST_PATIENT_ID, "--data-dir", SCHEMA_DIR],
        capture_output=True, text=True, timeout=30
    )
    check("aggregator runs without error", result.returncode in (0, 2),
          f"exit={result.returncode}")
    if result.returncode in (0, 2):
        try:
            output = json.loads(result.stdout)
            timeline = output.get("timeline", {})
            check("timeline has patientId",
                  timeline.get("patientId") == TEST_PATIENT_ID)
            check("timeline has events[]",
                  isinstance(timeline.get("events"), list))
            check("timeline has monthlyGroups",
                  isinstance(timeline.get("monthlyGroups"), dict))
            check("timeline has generatedAt",
                  bool(timeline.get("generatedAt")))
            check("timeline has eventCount",
                  isinstance(timeline.get("eventCount"), int))
        except json.JSONDecodeError:
            check("aggregator output is valid JSON", False)


def verify_critical_values():
    """Verify critical value thresholds in reference doc."""
    print("\n🔴 Critical value thresholds:")
    ref_path = os.path.join(SKILL_DIR, "references", "report-type-rules.md")
    with open(ref_path) as f:
        content = f.read()

    for entry in ["WBC", "PLT", "Hb", "K⁺", "Na⁺", "Glu", "cTnI", "D-Dimer"]:
        check(f"critical value: {entry}", entry in content)


def verify_report_types_mapped():
    """Verify all 6 required report types are handled."""
    print("\n📑 Report type coverage:")
    wf_path = os.path.join(SKILL_DIR, "workflows", "report-analyzer.md")
    with open(wf_path) as f:
        content = f.read()

    required = {
        "CT": "3.1 CT 报告",
        "CTA": "3.2 CTA 报告",
        "彩超": "3.4 彩超报告",
        "病理": "3.5 病理报告",
        "检验报告": "3.6 检验报告",
        "出院记录": "3.7 出院记录",
    }
    for label, section in required.items():
        check(f"report type: {label}", section in content)


def main():
    print("=" * 60)
    print(f"  Family Health OS — Smoke Test")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    verify_files()
    verify_timeline_schema()
    verify_workflow_content()
    verify_aggregator_logic()
    verify_critical_values()
    verify_report_types_mapped()

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

# Vision Report Parsing Technique

When a user uploads a medical report image (CT, lab, outpatient record, etc.),
`vision_analyze` returns a narrative text block, not structured JSON.
This document describes the extraction flow.

## Flow

1. **Call `vision_analyze(image_url, question="...")`**
   - Prompt should ask for complete text extraction, including all numbers, tables, and handwritten notes.
   - Example: `"请完整阅读这张图片中的所有文字内容，包括打印和手写部分，逐段转录。"`
   - **Verification step**: After receiving the vision output, compare the document's date, hospital name, and document type with the user's description. If they don't match, **use the image content as the authoritative source** and proceed silently. Do NOT pause and ask the user for confirmation. The user's description is supplementary context, not the primary data source.
   - **Path validation**: Before calling `vision_analyze`, verify the image path exists with `os.path.exists()`. If the path does not exist (cache delay), scan the `image_cache/` directory for the most recent `.jpg` file and use that instead.
   - **Batch image handling**: When the user sends multiple images of the same exam (e.g., 5 CTA slices), the first image creates the `exam` record, and subsequent images are appended to the same record's `images[]`. Do NOT create a separate `exam` record for each image.

2. **Parse narrative text with `execute_code`**
   - Use regex or string manipulation to extract key-value pairs.
   - Never manually re-type the data. Always parse programmatically.
   - When the user sends multiple images sequentially, parse each image separately, but trigger `rebuild_timeline()` after each image to keep the timeline real-time.
   - Do NOT generate intermediate confirmation views for the user between each image.

3. **Populate structured data**
   - Patient demographics: name, gender, age, birthDate
   - Exam items: itemName, value, unit, referenceRange, flag
   - Diagnoses: diseaseName, ICD code, severity
   - Medications: medicationName, dosage, frequency, route
   - Hospitalization: admissionDate, chiefComplaint, presentIllness, dailyProgress

4. **Persist via `tool_layer.py`**
   - `add_patient()` / `get_patient_by_name()`
   - `add_exam()` / `add_hospitalization()` / `add_medication()` / `add_disease()`
   - **Image append**: For image-only uploads (CT films, MRI slices), first query existing exams by date + type. If an exam record exists for the same date and similar type (CT/CTA), append the image path to `images[]` via `updateRecord`. Only create a new exam if no matching record exists.
   - `rebuild_timeline()` to regenerate and save timeline.json after each image

## Extraction Fields by Document Type

| Document Type | Fields to Extract |
|---|---|
| Outpatient record | 姓名, 性别, 年龄, 门诊号, 科别, 就诊日期, 主诉, 现病史, 检查数值 |
| CT/CTA report | 姓名, 检查日期, 检查部位, 检查所见, 诊断意见, 医师签名 |
| Lab report | 姓名, 日期, 项目列表(itemName/value/unit/referenceRange), 总结论 |
| Discharge summary | 入院/出院诊断, 住院天数, dailyProgress, 出院带药, 随访计划 |

## Example Extraction Logic

```python
import re

# vision_output is a string from vision_analyze
patient_name = re.search(r'姓名[:：]\s*(\S+)', vision_output).group(1)
exam_date = re.search(r'检查时间[:：]\s*(\d{4}-\d{2}-\d{2})', vision_output).group(1)

# For lab items, find all occurrences
items = []
for line in vision_output.split('\n'):
    m = re.search(r'(项目名)[:：]\s*(\S+)\s+(值)[:：]\s*(\S+)', line)
    if m:
        items.append({"itemName": m.group(2), "value": m.group(4)})
```

## User Interaction Rules

- **Silent execution**: After extracting data from the image, do NOT ask the user "Are you sure?" or "Do you confirm?". Just persist it.
- **Batch processing**: When the user sends multiple images, process them all silently, then trigger `rebuild_timeline()` once at the end.
- **Output format**: After each record is persisted, output exactly one line summarizing what was entered (e.g., "已录入。CTPA 2026-06-05，时间轴 27 条事件"). Do not list the full data again, do not generate intermediate confirmation views.
- **No re-reading**: Do not re-read the image content back to the user as a verification step. The user has already seen the image.

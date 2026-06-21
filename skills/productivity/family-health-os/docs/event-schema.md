# Event Schema — 事件模型技术参考

> 本文档描述 Family Health OS 的事件模型设计，覆盖 timeline.json 的 schema 定义、事件类型枚举、分类体系、ID 生成规则及系统内数据流。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **事件溯源** | 所有事件必有来源（sourceType + sourceId），可追溯至原始数据记录 |
| **时间有序** | events[] 始终按 date 升序排列 |
| **月份索引** | monthlyGroups 以 YYYY-MM 为键，加速按月查询 |
| **类型分类** | eventType（精确类型） + category（粗粒度分类） 双维度描述 |
| **可扩展** | metadata 字段用于存储类型特有数据，不污染公共字段 |
| **不可变追加** | 事件一旦生成不修改，聚合时通过 version 标记版本 |

---

## 2. 顶层结构 (timeline.json)

```json
{
  "id": "uuid",
  "patientId": "uuid",
  "generatedAt": "2026-06-13T19:23:00",
  "generatedBy": "auto",
  "events": [ /* Event[] */ ],
  "monthlyGroups": {
    "2025-06": ["evt-xxx", "evt-yyy"],
    "2025-07": ["evt-zzz"]
  },
  "summary": "时间跨度：2025-01 ~ 2026-06，共 42 条事件 | ...",
  "eventCount": 42,
  "dateRange": {
    "earliest": "2025-01-15",
    "latest": "2026-06-13"
  },
  "version": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string (uuid) | ✓ | 时间轴记录唯一标识 |
| `patientId` | string (uuid) | ✓ | 关联的患者ID |
| `generatedAt` | date-time | | 生成/更新时间 |
| `generatedBy` | enum | | `auto` / `manual` |
| `events` | Event[] | ✓ | 所有事件列表（按时间升序） |
| `monthlyGroups` | object | | 月份索引，key=`YYYY-MM`, value=eventId[] |
| `summary` | string | | 病程摘要文本 |
| `eventCount` | integer | | 事件总数 |
| `dateRange` | object | | `{earliest, latest}` |
| `version` | integer | | 版本号，默认 1 |

---

## 3. 事件结构 (Event)

### 3.1 必填字段

```json
{
  "eventId": "evt-exam-20250613-a3f8",
  "date": "2025-06-13T09:30:00",
  "eventType": "exam_result",
  "title": "检查结果：血常规"
}
```

### 3.2 完整字段

```json
{
  "eventId": "evt-exam-20250613-a3f8",
  "eventIdSource": "auto",
  "date": "2025-06-13T09:30:00",
  "eventType": "exam_result",
  "category": "diagnostic",
  "title": "检查结果：血常规",
  "description": "白细胞计数：11.2×10⁹/L↑；结论：感染可能",
  "severity": "warning",
  "isKeyEvent": false,
  "sourceType": "exam",
  "sourceId": "550e8400-e29b-41d4-a716-446655440000",
  "sourceDoctor": "张医生",
  "sourceInstitution": "北京大学第三医院",
  "tags": ["abnormal"],
  "affectedBodySite": "右肺下叶",
  "metadata": {
    "value": "11.2",
    "unit": "10⁹/L",
    "flag": "↑"
  },
  "relatedEventIds": ["evt-exam-20250613-b4c2"]
}
```

### 3.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eventId` | string | ✓ | 事件唯一标识（见第 6 节） |
| `eventIdSource` | enum | | 生成方式：`auto` / `manual` |
| `date` | date-time | ✓ | 事件发生日期时间 |
| `eventType` | enum | ✓ | 事件类型（见第 4 节） |
| `category` | enum | | 事件分类（见第 5 节） |
| `title` | string | ✓ | 事件标题（简短描述） |
| `description` | string | | 详细描述 |
| `severity` | enum | | `info` / `warning` / `critical` / `normal` |
| `isKeyEvent` | boolean | | 是否里程碑节点 |
| `sourceType` | enum | | 来源数据类型：`hospitalization` / `exam` / `medication` / `disease` / `manual` / `task` |
| `sourceId` | string | | 来源数据记录 ID |
| `sourceDoctor` | string | | 信息来源医生 |
| `sourceInstitution` | string | | 信息来源机构 |
| `tags` | string[] | | 自定义标签 |
| `affectedBodySite` | string | | 涉及身体部位 |
| `metadata` | object | | 扩展元数据 |
| `relatedEventIds` | string[] | | 关联事件 ID 列表 |

### 3.4 metadata 字段

```json
{
  "value": "string | number",
  "unit": "string",
  "flag": "↑ | ↓ | normal",
  "location": "string",
  "duration": "string"
}
```

---

## 4. 事件类型枚举 (29种)

### 4.1 按 eventType 索引

| # | eventType | 分类 | 说明 | 来源 |
|---|-----------|------|------|------|
| 1 | `admission` | administrative | 入院 | hospitalization |
| 2 | `discharge` | administrative | 出院 | hospitalization |
| 3 | `transfer` | administrative | 转科/转院 | hospitalization |
| 4 | `surgery` | surgical | 手术 | hospitalization |
| 5 | `procedure` | surgical | 其他操作 | hospitalization |
| 6 | `exam` | diagnostic | 检查记录 | exam / task |
| 7 | `new_exam` | diagnostic | 新开检查 | exam |
| 8 | `exam_result` | diagnostic | 检查结果回报 | exam |
| 9 | `labResult` | diagnostic | 检验结果 | exam / task |
| 10 | `imaging` | diagnostic | 影像检查 | exam / task |
| 11 | `pathology` | diagnostic | 病理检查 | exam |
| 12 | `medicationStart` | medication | 开始用药 | medication |
| 13 | `medicationStop` | medication | 停药 | medication |
| 14 | `medicationChange` | medication | 用药调整 | medication / task |
| 15 | `diagnosis` | clinical | 确诊 | disease |
| 16 | `diagnosisChange` | clinical | 诊断变更 | disease |
| 17 | `symptom` | clinical | 症状记录 | disease / medication |
| 18 | `symptom_change` | clinical | 症状变化 | disease |
| 19 | `round` | clinical | 查房 | hospitalization |
| 20 | `doctor_round` | clinical | 医生查房 | hospitalization |
| 21 | `consultation` | clinical | 会诊 | hospitalization |
| 22 | `note` | clinical | 病程记录 | hospitalization |
| 23 | `vitalSigns` | monitoring | 生命体征 | hospitalization / task |
| 24 | `followUp` | monitoring | 随访 | hospitalization / task |
| 25 | `emergency` | emergency | 紧急事件 | hospitalization |
| 26 | `allergyReaction` | emergency | 过敏反应 | medication |
| 27 | `vaccination` | preventive | 疫苗接种 | task |
| 28 | `healthCheckup` | preventive | 体检 | task |
| 29 | `other` | other | 其他 | — |

### 4.2 按分类索引

| 分类 | 事件类型 | 图标 |
|------|---------|------|
| **clinical** (临床) | diagnosis, diagnosisChange, symptom, symptom_change, round, doctor_round, consultation, note | 🏥 |
| **diagnostic** (检查) | exam, new_exam, exam_result, labResult, imaging, pathology | 🔬 |
| **medication** (用药) | medicationStart, medicationStop, medicationChange | 💊 |
| **surgical** (手术) | surgery, procedure | 🔪 |
| **administrative** (行政) | admission, discharge, transfer | 📋 |
| **monitoring** (监测) | vitalSigns, followUp | 📊 |
| **emergency** (紧急) | emergency, allergyReaction | 🚨 |
| **preventive** (预防) | vaccination, healthCheckup | 💉 |
| **other** (其他) | other | 📌 |

### 4.3 关键事件

以下事件类型的 `isKeyEvent` 自动标记为 `true`：

```
admission, discharge, surgery, diagnosis,
diagnosisChange, emergency, transfer
```

---

## 5. 事件分类体系 (category)

### 5.1 分类定义

9 个类别用于粗粒度过滤和展示分组：

| category | 中文名 | 包含 eventType 数 | 展示优先级 |
|----------|--------|-------------------|-----------|
| `clinical` | 临床事件 | 8 | 1 |
| `diagnostic` | 检查/检验事件 | 6 | 2 |
| `medication` | 用药事件 | 3 | 3 |
| `surgical` | 手术事件 | 2 | 4 |
| `administrative` | 行政事件 | 3 | 5 |
| `monitoring` | 监测事件 | 2 | 6 |
| `emergency` | 紧急事件 | 2 | 7 |
| `preventive` | 预防事件 | 2 | 8 |
| `other` | 其他 | 1 | 9 |

### 5.2 分类映射表 (eventTypeCategoryMap)

timeline.json 顶层包含参考映射：

```json
"eventTypeCategoryMap": {
  "clinical": ["diagnosis", "diagnosisChange", "symptom", "symptom_change",
               "round", "doctor_round", "consultation", "note"],
  "diagnostic": ["exam", "new_exam", "exam_result", "labResult", "imaging", "pathology"],
  "medication": ["medicationStart", "medicationStop", "medicationChange"],
  "surgical": ["surgery", "procedure"],
  "administrative": ["admission", "discharge", "transfer"],
  "monitoring": ["vitalSigns", "followUp"],
  "emergency": ["emergency", "allergyReaction"],
  "preventive": ["vaccination", "healthCheckup"]
}
```

---

## 6. 事件 ID 格式

### 6.1 生成规则

```
evt-{源类型缩写}-{YYYYMMDD}-{4位随机}

示例:
  evt-exam-20250613-a3f8    ← 来自 exams.json
  evt-hosp-20250601-d4e5    ← 来自 hospitalizations.json
  evt-med-20200315-b2c1     ← 来自 medications.json
  evt-dis-20200115-c7d9     ← 来自 diseases.json
  evt-task-20250701-e1f2    ← 来自 tasks.json
  evt-man-20250613-a1b2     ← 手动创建
```

### 6.2 源类型缩写

| sourceType | 缩写 |
|-----------|------|
| `hospitalization` | hosp |
| `exam` | exam |
| `medication` | med |
| `disease` | dis |
| `task` | task |
| `manual` | man |

### 6.3 eventIdSource

| 值 | 说明 |
|----|------|
| `auto` | 由聚合引擎自动生成 |
| `manual` | 手工创建或外部系统导入 |

---

## 7. 数据流

### 7.1 写入流

```
用户操作 / Report Analyzer OCR
       │
       ▼
原始 JSON 文件 (data/*.json)
  ├── exams.json         ← 写入一条检查记录
  ├── hospitalizations.json ← 写入一条住院记录
  ├── medications.json   ← 写入一条用药记录
  ├── diseases.json      ← 写入一条疾病记录
  └── tasks.json         ← 写入一条任务记录
       │
       ▼
aggregate_timeline.py    ← 读取5个源文件
       │                   按 patientId 过滤
       │                   调用对应聚合器
       │                   生成事件→排序→建立索引→生成摘要
       ▼
timeline.json            ← 写入（覆盖）
```

### 7.2 查询流

```
用户请求 (按患者/疾病/时间)
       │
       ▼
timeline.json            ← 优先读取已聚合结果
       │
       ▼
是否存在该患者的时间轴？
  ├── 是 → 直接使用
  └── 否 → 调用 aggregate_timeline.py 自动构建
       │
       ▼
事件过滤引擎
  ├── 疾病过滤：relatedDiseaseIds + episode hospitalizationId
  └── 时间过滤：startDate ≤ event.date ≤ endDate
       │
       ▼
视图渲染
  ├── 病程时间轴 (build_timeline.py --view full)
  ├── 住院时间轴 (build_timeline.py --view hospitalization)
  └── 会诊时间轴 (build_timeline.py --view consultation)
       │
       ▼
摘要合成
  ├── 病史摘要 (generate_summary.py --type medical-history)
  ├── 住院总结 (generate_summary.py --type hospitalization)
  ├── 会诊摘要 (generate_summary.py --type consultation)
  └── 复诊摘要 (generate_summary.py --type follow-up)
```

---

## 8. 事件来源映射

每条事件对应一条原始数据记录：

### 8.1 hospitalization → 事件

| 住院数据 | 生成事件 |
|---------|---------|
| hospitalizations[].admissionDate | admission |
| hospitalizations[].dischargeDate | discharge |
| hospitalizations[].dailyProgress[] (type=dailyProgress) | note |
| hospitalizations[].dailyProgress[] (type=roundNote) | doctor_round |
| hospitalizations[].dailyProgress[] (type=consultationNote) | consultation |
| hospitalizations[].dailyProgress[] (type=criticalNote) | emergency |
| hospitalizations[].dailyProgress[] (type=preOpNote) | note |
| hospitalizations[].dailyProgress[] (type=postOpNote) | note |
| hospitalizations[].dailyProgress[] (type=transferNote) | transfer |
| hospitalizations[].surgeries[] | surgery |
| hospitalizations[].consultations[] | consultation |
| hospitalizations[].followUpPlan.followUpDate | followUp |

### 8.2 exam → 事件

| 检查数据 | 生成事件 |
|---------|---------|
| exams[].examDate | new_exam |
| exams[].reportDate / conclusion | exam_result |

异常项自动标记 severity=warning，tags=["abnormal"]

### 8.3 medication → 事件

| 用药数据 | 生成事件 |
|---------|---------|
| medications[].startDate | medicationStart |
| medications[].endDate | medicationStop |
| medications[].sideEffects[] | symptom |

### 8.4 disease → 事件

| 疾病数据 | 生成事件 |
|---------|---------|
| diseases[].diagnosedDate | diagnosis |
| diseases[].episodes[].startDate | symptom_change |
| diseases[].complications[].diagnosedDate | diagnosisChange |

### 8.5 task → 事件

| 任务类型 | 生成 eventType |
|---------|---------------|
| followUp | followUp |
| examReminder | exam |
| medicationRefill | medicationChange |
| vaccination | vaccination |
| labTest | labResult |
| imaging | imaging |
| checkup | healthCheckup |
| surgeryFollowUp | followUp |
| bloodPressureLog / bloodSugarLog / weightLog | vitalSigns |

---

## 9. 严重度 (severity) 规则

| 严重度 | 含义 | 触发条件 | 显示标记 |
|--------|------|---------|---------|
| `info` | 常规信息 | 默认值 | — |
| `normal` | 正常 | 检查结果全部正常 | ✅ |
| `warning` | 异常需关注 | 检查有异常项(high/low)、疾病确诊 | ⚠️ |
| `critical` | 危急 | 手术、紧急事件、危急值(↑↑/↓↓) | 🔴 |

```python
severity_map = {
    # 事件类型 → 严重度
    "surgery": "critical",
    "emergency": "critical",
    "allergyReaction": "critical",
    "diagnosis": "warning",
    # 条件性
    "exam_result": "warning" if any_abnormal else "info",
    "diagnosisChange": "critical" if severity in ("severe","critical") else "warning",
}
```

---

## 10. 月份分组 (monthlyGroups)

### 10.1 索引结构

```json
"monthlyGroups": {
  "2025-06": ["evt-hosp-20250601-d4e5", "evt-exam-20250613-a3f8"],
  "2025-07": ["evt-med-20250701-e1f2"]
}
```

### 10.2 重建规则

每次过滤事件后需要重建月份索引：

```python
def rebuild_monthly_groups(events):
    groups = {}
    for ev in events:
        month = ev["date"][:7]  # "2025-06"
        groups.setdefault(month, []).append(ev["eventId"])
    return dict(sorted(groups.items()))
```

---

## 11. 校验规则 (Timeline Validation)

```python
def validate_timeline(timeline):
    errors = []
    # 1. 每条事件必填字段
    for ev in events:
        if not ev.get("eventId"):    errors.append("缺少 eventId")
        if not ev.get("eventType"):  errors.append("缺少 eventType")
        if not ev.get("date"):       errors.append("缺少 date")
        if not ev.get("sourceType"): errors.append("缺少 sourceType")

    # 2. 信息来源标注
    if sourceType != "manual" and not sourceDoctor and not sourceInstitution:
        errors.append("缺少信息来源标注")

    # 3. monthlyGroups 一致性
    all_ids = {e["eventId"] for e in events}
    indexed_ids = set()
    for ids in monthlyGroups.values():
        indexed_ids.update(ids)
    if all_ids - indexed_ids:
        errors.append("以下事件未在 monthlyGroups 中索引")
    if indexed_ids - all_ids:
        errors.append("monthlyGroups 中存在无效事件ID")

    return errors
```

---

## 12. 与 Timeline Builder 的协作

```python
# 查询层只读 timeline.json
timeline = load_or_build_timeline(patientId)

# 过滤 → 排序 → 统计 → 渲染
events = timeline["events"]
events = filter_by_disease(events, diseaseId)
events = filter_by_date(events, start, end)
stats  = compute_stats(events)
groups = rebuild_monthly_groups(events)

markdown = render_full_view(patient, events, stats)
```

> **基本原则：** timeline.json 是聚合产物，不应直接编辑。增删改应操作原始数据表文件后重新调用 `aggregate_timeline.py`。

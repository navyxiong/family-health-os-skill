# Timeline Builder Workflow

**适用场景：** 聚合后的医疗事件 → 按条件查询 → 生成定制化时间轴视图

**架构位置：** 在 `aggregate_timeline.py`（数据写入层）之上，作为 **查询+渲染层**

```
原始数据层 (memory/schemas/*.json)
    │ aggregate_timeline.py (写入)
    ▼
数据存储层 (timeline.json)
    │ build_timeline.py (查询+渲染)
    ▼
展示层 (按视图输出)
    ├── 病程时间轴 (全病程)
    ├── 住院时间轴 (按住院)
    └── 专家会诊时间轴 (按会诊)
```

---

## 1. 整体架构

```
                  ┌──────────────────────────────┐
                  │      Timeline Builder         │
                  │   scripts/build_timeline.py   │
                  └──────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ 按患者查询    │ │ 按疾病查询    │ │ 按时间查询    │
    │ patientId    │ │ diseaseId    │ │ start/end    │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │
           └────────────────┼────────────────┘
                            ▼
                    ┌───────────────┐
                    │   事件过滤     │
                    │  Filter Engine │
                    └───────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ 病程时间轴    │ │ 住院时间轴    │ │ 会诊时间轴    │
    │ Full Timeline│ │Hosp Timeline │ │Consult Tl    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 2. 查询模式

### 2.1 按患者查询

```
查询参数: patientId=<UUID>
行为:   读取该患者的所有事件
数据源: 优先读 timeline.json（已聚合），不存在则调用 aggregate_timeline.py
```

**数据源优先级：**
1. `memory/schemas/timeline.json` — 查找 `patientId` 匹配的记录
2. 若不存在 → 自动运行 `aggregate_timeline.py <patientId>` 构建

**返回结构：**
```json
{
  "patient": { "id": "...", "name": "张三" },
  "timeline": { /* timeline.json 完整结构 */ },
  "stats": {
    "totalEvents": 42,
    "dateRange": { "earliest": "2023-03-01", "latest": "2026-06-13" },
    "byCategory": { "clinical": 15, "diagnostic": 12, ... },
    "byType": { "diagnosis": 3, "exam_result": 8, ... }
  }
}
```

**统计摘要生成规则：**

| 统计维度 | 计算方式 |
|---------|---------|
| `totalEvents` | events.length |
| `dateRange` | events[0].date ~ events[-1].date |
| `byCategory` | 按 events[].category 分组计数 |
| `byType` | 按 events[].eventType 分组计数 |
| `bySeverity` | 按 events[].severity 分组计数 |
| `keyEvents` | events.filter(isKeyEvent) 列表 |

---

### 2.2 按疾病查询

```
查询参数: diseaseId=<UUID>
行为:   筛选与该疾病相关的事件
数据源: 遍历该患者的 timeline，按以下规则匹配
```

**关联匹配规则：**

| 来源表 | 匹配方式 |
|--------|---------|
| `diseases.json` | 直接匹配 `id == diseaseId`（确诊事件） |
| `exams.json` | `relatedDiseaseIds[]` 包含该 diseaseId |
| `medications.json` | `relatedDiseaseIds[]` 包含该 diseaseId |
| `hospitalizations.json` | 通过 diseases.episodes[].hospitalizationId 关联 |
| `timeline.events[].tags` | 包含疾病名或 ICD 编码标签 |

**事件过滤链：**

```
1. 从 diseases.json 获取疾病名 + ICD 编码 + 关联 hospitalizationIds
2. 从 timeline 中筛选：
   a. eventType = "diagnosis" 且 sourceId == diseaseId
   b. sourceType = "exam" 且该 exam 的 relatedDiseaseIds 包含 diseaseId
   c. sourceType = "medication" 且该 med 的 relatedDiseaseIds 包含 diseaseId
   d. sourceType = "hospitalization" 且 hospitalizationId 在 1 的结果中
   e. tags 包含疾病名
3. 去重 + 排序
```

**返回示例：**
```
📋 疾病: 2型糖尿病 (E11)
📅 病程: 2020-01 ~ 2026-06
├── 2020-01-15 确诊：2型糖尿病
├── 2020-03-10 开始用药：二甲双胍 500mg 每日2次
├── 2021-06-01 检查结果：糖化血红蛋白 7.2% ↑
├── 2022-09-20 住院：糖尿病足感染
│   ├── 2022-09-20 入院
│   ├── 2022-09-21 查房记录
│   ├── 2022-09-25 手术：左足清创
│   └── 2022-10-05 出院
├── 2024-11-01 并发症：糖尿病视网膜病变
└── 2025-03-15 用药调整：增加达格列净 10mg
```

---

### 2.3 按时间查询

```
查询参数:
  patientId=<UUID>   (必填)
  startDate=<ISO>    (可选，默认 timeline.earliest)
  endDate=<ISO>      (可选，默认 timeline.latest)

行为: 仅在指定时间范围内筛选事件
```

**时间过滤精度：**

| 粒度 | 参数格式 | 用途 |
|------|---------|------|
| 年 | `year=2025` | 年度回顾 |
| 月 | `start=2025-06-01&end=2025-06-30` | 月度报告 |
| 日 | `start=2025-06-13&end=2025-06-13` | 单日详情 |
| 自定义区间 | `start=2025-03-01&end=2025-09-01` | 任意区间 |

**monthlyGroups 重建逻辑：**
```python
# 过滤后需要重建 monthlyGroups 索引
filtered_events = [e for e in all_events if start <= e["date"] <= end]
monthly_groups = {}
for ev in filtered_events:
    month = ev["date"][:7]
    monthly_groups.setdefault(month, []).append(ev["eventId"])
```

---

## 3. 三种时间轴视图

### 3.1 病程时间轴 (Full Timeline)

**视图定义：** 展示患者全病程的所有事件，按月份分组 + 类别色标

**渲染规则：**

```
# 模板

## 📅 {YYYY}年{MM}月

[{图标}] {事件类型标签} **{标题}** — {医生} @ {医院}
  {描述摘要前80字}
  {如有异常标记：⚠️ 异常项：项目名 值↑/↓}

# 图标映射
| 分类 | 图标 |
|------|------|
| clinical | 🏥 |
| diagnostic | 🔬 |
| medication | 💊 |
| surgical | 🔪 |
| administrative | 📋 |
| monitoring | 📊 |
| emergency | 🚨 |
| preventive | 💉 |
| other | 📌 |

# 示例输出
## 📅 2025年06月

🏥 **确诊：2型糖尿病** — 王医生 @ 北京大学第三医院
  ICD编码：E11；严重程度：moderate

🔬 **开具检查：胸部CT平扫** — 李医生 @ 北京大学第三医院

🔬 **检查结果：胸部CT平扫** — 张医生 @ 放射科
  结论：右肺上叶磨玻璃结节，建议随访；异常项：磨玻璃结节8mm×6mm↑

💊 **开始用药：二甲双胍（降血糖）** — 王医生
  剂量：500mg，每日2次，途径：oral

🚨 **住院：2型糖尿病并发症** — @ 北京大学第三医院
  ├ 2025-06-10 入院
  ├ 2025-06-11 查房记录
  └ 2025-06-20 出院
```

**关键事件标记：**
```python
KEY_EVENT_TYPES = {
    "admission", "discharge", "surgery", "diagnosis",
    "diagnosisChange", "emergency", "transfer",
}
```
关键事件在输出中加 `**` 粗体 + `★` 标记。

**异常事件标记：**
```python
if event["severity"] == "critical":
    # 🔴 红色标记
    prefix = "🔴"
elif event["severity"] == "warning":
    # ⚠️ 黄色标记
    prefix = "⚠️"
elif event.get("tags") and "abnormal" in event["tags"]:
    # ↑ 异常标记
    prefix = "⬆"
```

---

### 3.2 住院时间轴 (Hospitalization Timeline)

**视图定义：** 以每次住院为单元，展示入院→每日病程→手术→出院的全流程

**数据源：** `hospitalizations.json` + 该住院期间关联的 `exams.json` / `medications.json`

**事件排序（按住院内时间线）：**
```
┌─────────────────────────────────────────┐
│  🏥 住院 #1                             │
│  ├── 入院诊断：社区获得性肺炎             │
│  ├── 科室：呼吸内科 @ 北京大学第三医院    │
│  ├── 主治医师：王主任                     │
│  ├── 时间：2025-06-01 → 2025-06-10 (9天)│
│  ├──                                      │
│  │  Day 1 | 2025-06-01                    │
│  │  ├ 📋 [admission] 入院                  │
│  │  ├ 🔬 [exam] 开具胸部CT                 │
│  │  ├ 💊 [medicationStart] 阿莫西林 500mg │
│  │  └ 📋 [dailyProgress] 发热38.5℃      │
│  │                                        │
│  │  Day 2 | 2025-06-02                    │
│  │  ├ 🔬 [exam_result] CT示右肺下叶炎症   │
│  │  └ 📋 [roundNote] 王主任查房           │
│  │                                        │
│  │  ...                                   │
│  │                                        │
│  │  Day 9 | 2025-06-09                    │
│  │  ├ 📊 [vitalSigns] 体温36.5℃ 正常     │
│  │  └ 📋 [postOpNote] 准备出院            │
│  │                                        │
│  │  Day 10 | 2025-06-10                   │
│  │  └ 📋 [discharge] 出院                  │
│  │    出院诊断：社区获得性肺炎（好转）      │
│  │    出院带药：阿莫西林 250mg×7天         │
│  │    随访：1周后呼吸科门诊复查             │
│  └──                                      │
└─────────────────────────────────────────┘
```

**输出结构：**
```json
{
  "hospitalizationId": "uuid",
  "hospital": "北京大学第三医院",
  "department": "呼吸内科",
  "admissionDate": "2025-06-01",
  "dischargeDate": "2025-06-10",
  "totalDays": 9,
  "admittingDiagnosis": "社区获得性肺炎",
  "dischargeDiagnosis": "社区获得性肺炎（好转）",
  "attendingPhysician": "王主任",
  "events": [
    { "day": 1, "date": "2025-06-01", "events": [...] },
    { "day": 2, "date": "2025-06-02", "events": [...] },
    ...
  ],
  "summary": {
    "totalEvents": 18,
    "surgeries": 0,
    "medicationChanges": 2,
    "consultations": 1,
    "keyFindings": ["CT示右肺下叶炎症", "体温3日后降至正常"]
  }
}
```

**每日事件聚合规则：**
```python
# 同一天的事件按时间顺序聚合为一个 day 条目
day_events = {}
for ev in filtered_events:
    day_key = ev["date"][:10]
    day_events.setdefault(day_key, []).append(ev)
```

---

### 3.3 专家会诊时间轴 (Consultation Timeline)

**视图定义：** 仅展示会诊相关事件，含会诊意见、来源科室、医生信息

**数据源：**
1. `timeline.events[].eventType == "consultation"` — 直接会诊事件
2. `hospitalizations.json.consultations[]` — 住院期间会诊详情
3. `timeline.events[].eventType` 涉及多科室协作的事件（如 `diagnosisChange`、`surgery`）

**事件类型过滤：**
```python
CONSULTATION_EVENT_TYPES = {
    "consultation",      # 会诊事件
    "doctor_round",      # 医生查房（含上级医师查房意见）
    "diagnosisChange",   # 诊断变更（常涉及会诊结论）
}
```

**输出结构：**

```
## 👨‍⚕️ 专家会诊时间轴

### 2025-06-02 呼吸内科 → 影像科 会诊
├── 申请科室：呼吸内科
├── 会诊科室：影像科
├── 会诊医生：赵主任（影像科）
├── 会诊意见：
│   右肺下叶炎症，磨玻璃结节建议3个月后复查CT
├── 推荐方案：
│   建议抗感染治疗后复查
└── 来源：北京大学第三医院

### 2025-06-05 呼吸内科 → 心内科 会诊
├── 申请科室：呼吸内科
├── 会诊科室：心内科
├── 会诊医生：钱主任（心内科）
├── 会诊意见：
│    患者既往冠心病史，当前心电图未见明显异常，
│    建议监测心肌酶，控制血压
├── 推荐方案：
│    继续现有降压方案，加用他汀
└── 来源：北京大学第三医院
```

**会诊统计：**
```json
{
  "totalConsultations": 3,
  "byDepartment": {
    "影像科": 1,
    "心内科": 1,
    "内分泌科": 1
  },
  "byDoctor": {
    "赵主任": 1,
    "钱主任": 1,
    "孙主任": 1
  },
  "duringHospitalization": {
    "住院ID": "xxx",
    "住院期间会诊数": 3,
    "平均响应天数": 1.5
  }
}
```

---

## 4. CLI 工具: `scripts/build_timeline.py`

### 4.1 用法

```bash
# 按患者查询 → 病程时间轴 (默认)
python3 build_timeline.py <patientId>

# 按患者 + 时间范围
python3 build_timeline.py <patientId> --start 2025-01-01 --end 2025-12-31

# 按疾病查询 → 该疾病相关病程
python3 build_timeline.py <patientId> --disease <diseaseId>

# 住院时间轴
python3 build_timeline.py <patientId> --view hospitalization

# 按具体住院
python3 build_timeline.py <patientId> --view hospitalization --hospitalization <hospId>

# 会诊时间轴
python3 build_timeline.py <patientId> --view consultation

# 会诊时间轴 + 时间范围
python3 build_timeline.py <patientId> --view consultation --start 2025-01-01 --end 2025-12-31

# 输出格式控制
python3 build_timeline.py <patientId> --format json     # 原始 JSON
python3 build_timeline.py <patientId> --format markdown  # 可读 Markdown (默认)
python3 build_timeline.py <patientId> --format text      # 纯文本摘要
```

### 4.2 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `patientId` | string | — | 患者UUID（必填） |
| `--disease <id>` | string | — | 按疾病筛选 |
| `--start <date>` | date | earliest | 起始日期 |
| `--end <date>` | date | latest | 截止日期 |
| `--view <type>` | enum | `full` | `full` / `hospitalization` / `consultation` |
| `--hospitalization <id>` | string | — | 指定住院ID（仅 view=hospitalization） |
| `--format <fmt>` | enum | `markdown` | `json` / `markdown` / `text` |
| `--data-dir <path>` | string | schemas/ | 数据目录 |
| `--output <file>` | string | stdout | 输出到文件 |

### 4.3 实现流程

```python
def build(patient_id, disease_id=None, start_date=None, end_date=None,
          view="full", hospitalization_id=None, data_dir=SCHEMA_DIR):
    # Step 1: 加载或构建患者时间轴
    timeline = load_or_build_timeline(patient_id, data_dir)

    # Step 2: 疾病过滤（如果指定）
    if disease_id:
        disease_filter = build_disease_filter(disease_id, data_dir)
        timeline["events"] = [e for e in timeline["events"]
                              if disease_filter.matches(e)]

    # Step 3: 时间范围过滤（如果指定）
    if start_date or end_date:
        timeline["events"] = filter_by_date(timeline["events"], start_date, end_date)
        timeline["monthlyGroups"] = rebuild_monthly_groups(timeline["events"])

    # Step 4: 应用视图
    if view == "full":
        return render_full_view(timeline)
    elif view == "hospitalization":
        return render_hospitalization_view(timeline, hospitalization_id, data_dir)
    elif view == "consultation":
        return render_consultation_view(timeline, data_dir)

    # Step 5: 格式化输出
    if format == "markdown":
        return to_markdown(result)
    elif format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)
```

---

## 5. 渲染引擎详解

### 5.1 病程时间轴渲染 (render_full_view)

**Markdown 模板：**

```
# 🏥 {患者姓名} 病程时间轴
📅 {earliest} → {latest} | 共 {totalEvents} 条事件

## 📊 概览
| 分类 | 计数 |
|------|------|
| 🏥 临床 | {clinicalCount} |
| 🔬 检查 | {diagnosticCount} |
| 💊 用药 | {medicationCount} |
| 🔪 手术 | {surgicalCount} |
| 📋 行政 | {administrativeCount} |
| 📊 监测 | {monitoringCount} |
| 🚨 紧急 | {emergencyCount} |
| 💉 预防 | {preventiveCount} |

## ⭐ 关键事件
{key_events_list}

---

{monthly_sections}
```

**月份分组渲染：**
```python
def render_month(events):
    lines = []
    for ev in sorted(events, key=lambda e: e["date"]):
        icon = CATEGORY_ICONS.get(ev["category"], "📌")
        severity_mark = ""
        if ev["severity"] == "critical":
            severity_mark = "🔴"
        elif ev["severity"] == "warning":
            severity_mark = "⚠️"

        title = f"**{ev['title']}**" if ev['isKeyEvent'] else ev['title']
        source = f" — {ev['sourceDoctor']}" if ev.get('sourceDoctor') else ""
        inst = f" @ {ev['sourceInstitution']}" if ev.get('sourceInstitution') else ""

        lines.append(f"{severity_mark}{icon} {title}{source}{inst}")

        if ev.get("description"):
            desc = ev["description"][:80]
            lines.append(f"  {desc}")

        if ev.get("affectedBodySite"):
            lines.append(f"  部位：{ev['affectedBodySite']}")

    return "\n".join(lines)
```

### 5.2 住院时间轴渲染 (render_hospitalization_view)

**按住院分组的算法：**

```python
def group_by_hospitalization(events, data_dir):
    """
    1. 读取 hospitalizations.json，获取所有住院记录
    2. 对每个住院：
       a. 从 timeline 中筛选 sourceType="hospitalization" 
          且 sourceId == hosp.id 的事件
       b. 按日期分组为 daily_events
       c. 从 exams 中筛选 relatedHospitalizationId == hosp.id 的事件
       d. 从 medications 中筛选 relatedHospitalizationId == hosp.id 的事件
    3. 合并后输出
    """
```

**每日分组渲染：**
```python
def render_hospital_day(day_num, date_str, events):
    lines = [f"  **Day {day_num} | {date_str}**"]
    for ev in sorted(events, key=lambda e: e["date"]):
        evt_label = EVENT_TYPE_LABELS.get(ev["eventType"], ev["eventType"])
        lines.append(f"  ├ {evt_label} {ev['title']}")
        if ev.get("description"):
            lines.append(f"  │ {ev['description'][:60]}")
    return "\n".join(lines)
```

### 5.3 会诊时间轴渲染 (render_consultation_view)

**会诊详情增强：**
```python
def enrich_consultation(ev, data_dir):
    """
    从 hospitalizations.json 中查找完整的会诊详情
    """
    if ev.get("sourceType") == "hospitalization":
        hosp = find_hospitalization(ev["sourceId"], data_dir)
        if hosp and "consultations" in hosp:
            for cons in hosp["consultations"]:
                if cons.get("consultingDoctor") == ev.get("sourceDoctor"):
                    return {
                        **ev,
                        "consultationDetail": cons
                    }
    return ev
```

---

## 6. 错误处理

| 场景 | 处理 |
|------|------|
| patientId 不存在 | 报错并列出所有可用患者 |
| diseaseId 不存在 | 报错并列出该患者的所有疾病 |
| 时间范围无数据 | 返回空时间轴 + 提示"该时间段无记录" |
| hospitalizationId 不属于该患者 | 报错 |
| timeline.json 不存在 | 自动运行 aggregate_timeline.py 构建 |
| 数据文件损坏 | 报错 + 提示检查 memory/schemas/ |

---

## 7. 与聚合引擎的关系

| 维度 | aggregate_timeline.py | build_timeline.py |
|------|----------------------|-------------------|
| 职责 | **写入层**：从源数据构建 events[] | **查询层**：从 timeline 查询+渲染 |
| 调用时机 | 每次新数据写入后 | 每次用户查询时 |
| 输出 | timeline.json 原始 JSON | Markdown / JSON / Text 报告 |
| 数据源 | exams.json, hospitalizations.json 等 | timeline.json (已聚合) |
| 视图 | 无（只存原始结构） | 病程/住院/会诊 三种视图 |
| 过滤 | 按 patientId | patientId + diseaseId + 时间 |

**集成流程：**

```
用户上传报告
    → report-analyzer workflow (OCR → 提取 → 写入)
    → aggregate_timeline.py (更新时间轴)
    → build_timeline.py (返回更新后的视图)
```

---

## 附录: 事件类型标签映射

```python
EVENT_TYPE_LABELS = {
    "admission": "📋 入院",
    "discharge": "📋 出院",
    "surgery": "🔪 手术",
    "exam": "🔬 检查",
    "new_exam": "🔬 新开检查",
    "exam_result": "🔬 检查结果",
    "medicationStart": "💊 开始用药",
    "medicationStop": "💊 停药",
    "medicationChange": "💊 调整用药",
    "diagnosis": "🏥 确诊",
    "diagnosisChange": "🏥 诊断变更",
    "consultation": "👨‍⚕️ 会诊",
    "round": "🏥 查房",
    "doctor_round": "👨‍⚕️ 主任查房",
    "vaccination": "💉 疫苗接种",
    "allergyReaction": "🚨 过敏反应",
    "emergency": "🚨 紧急事件",
    "followUp": "📊 随访",
    "labResult": "🔬 检验结果",
    "imaging": "🔬 影像检查",
    "pathology": "🔬 病理结果",
    "procedure": "🔪 操作",
    "transfer": "📋 转科",
    "symptom": "📊 症状",
    "symptom_change": "📊 症状变化",
    "vitalSigns": "📊 生命体征",
    "healthCheckup": "💉 体检",
    "note": "📝 病程记录",
    "other": "📌 其他",
}

CATEGORY_ICONS = {
    "clinical": "🏥",
    "diagnostic": "🔬",
    "medication": "💊",
    "surgical": "🔪",
    "administrative": "📋",
    "monitoring": "📊",
    "emergency": "🚨",
    "preventive": "💉",
    "other": "📌",
}
```

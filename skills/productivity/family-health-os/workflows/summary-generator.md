# Medical Summary Generator

**适用场景：** 为临床场景生成结构化叙事摘要，供医生快速掌握患者情况。

**架构位置：** Layer 3.5 — 在 Timeline Builder（事件展示层）之上，面向特定临床场景的摘要合成层。

```
原始数据层 (memory/schemas/*.json)
    │ aggregate_timeline.py
    ▼
时间轴存储层 (timeline.json)
    │ build_timeline.py (事件查询)
    ▼
摘要合成层 (Summary Generator)
    ├── 病史摘要     → 给新接诊医生
    ├── 住院总结     → 出院/转科时
    ├── 专家会诊摘要 → 会诊归档
    └── 复诊摘要     → 复诊前准备
```

---

## 1. 整体架构

```
                    ┌────────────────────────────────────┐
                    │      Summary Generator              │
                    │   scripts/generate_summary.py       │
                    └────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │  病史摘要      │   │  住院总结      │   │  会诊摘要/复诊  │
    │ medicalHistory│   │ hospitalization│   │ consultation/  │
    │               │   │                │   │ followUp       │
    └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                    ┌────────────────────────────────────┐
                    │      数据读取层                      │
                    │  patients / diseases / exams / meds │
                    │  hospitalizations / timeline / tasks│
                    └────────────────────────────────────┘
```

**4 种摘要统一输出为 Markdown，结构一致：**
```
# {摘要类型} — {患者姓名}

## 基本信息
...

## {章节 A}
...

## {章节 B}
...

---

*生成时间: {datetime} | 数据来源: Family Health OS*
```

---

## 2. 病史摘要 (Medical History Summary)

**目的：** 新接诊医生快速了解患者全部健康背景。类似"入院记录"中的既往史 + 现病史概要。

**触发场景：**
- 患者首次就诊/转诊
- 医生要求提供完整病史
- 多学科会诊前准备

**数据源：** patients, diseases, exams（最新关键结果）, medications（当前用药）, hospitalizations（最近一次）, allergies

### 模板

```
# 🏥 病史摘要 — {患者姓名}

## 👤 基本信息
| 项目 | 内容 |
|------|------|
| 姓名 | {name} |
| 性别 | {gender_label} |
| 年龄 | {age}岁 |
| 血型 | {bloodType} |
| 过敏史 | {allergies_summary} |
| 建档日期 | {createdAt} |

## 🩺 现病史 — 当前疾病概况

### 活跃疾病
{disease_list}
*格式：疾病名 (ICD编码) | 确诊日期 | 当前状态 | 严重程度*

### 当前用药
{current_medications}
*格式：药品名 剂量 频率 | 用途 | 起止时间*

---

## 📋 既往史

### 既往疾病
{past_diseases}
*格式：疾病名 | 确诊日期 | 状态*

### 手术史
{surgery_history}
*格式：手术名 | 日期 | 医院*

### 住院史
{hospitalization_history}
*格式：住院时间 | 科室 | 入院诊断 | 天数*

### 家族病史
{family_history}
*格式：疾病名 | 关系*

---

## 🔬 近期关键检查（最近6个月）

{recent_exams}
*异常项已标记 ↑↓*

---

## 📊 关键事件时间轴摘要

{timeline_summary}
*仅显示关键事件（确诊/手术/入院/出院/紧急事件）*

---

*生成时间: {datetime}*
*数据来源: Family Health OS*
```

### 字段提取规则

| 模板字段 | 数据来源 | 提取逻辑 |
|---------|---------|---------|
| `age` | patients.birthDate | `(today - birthDate).years` |
| `gender_label` | patients.gender | `male→男 / female→女 / other→其他` |
| `allergies_summary` | patients.allergies[] | 无→"无已知过敏"；有→"allergen(severity: reaction), ..." |
| `disease_list` | diseases.json | 筛选 `patientId`, 按 `status` 排序(active/controlled > resolved) |
| `current_medications` | medications.json | 筛选 `isOngoing == true`, 按 `startDate` 排序 |
| `past_diseases` | diseases.json | 筛选 `status in (resolved, recovered)` |
| `surgery_history` | hospitalizations.json.surgeries[] | 全部手术记录，按日期排序 |
| `hospitalization_history` | hospitalizations.json | 全部住院，按 admissionDate 排序 |
| `family_history` | patients.familyHistory[] | 直接读取 |
| `recent_exams` | exams.json | 最近 180 天内，按 examDate 排序，含异常标记 |
| `timeline_summary` | timeline.events | 筛选 `isKeyEvent == true` |

### 疾病列表渲染格式

```markdown
#### 活跃疾病
| 疾病 | ICD | 确诊日期 | 状态 | 严重度 | 控制目标 |
|------|-----|---------|------|--------|---------|
| 2型糖尿病 | E11 | 2020-01-15 | active | moderate | HbA1c < 7.0% |
| 原发性高血压 | I10 | 2018-03-01 | controlled | mild | BP < 130/80 |

#### 缓解/已愈疾病
| 疾病 | 确诊日期 | 状态 |
|------|---------|------|
| 社区获得性肺炎 | 2025-06-01 | recovered |
```

### 当前用药渲染格式

```markdown
| 药品 | 剂量 | 频率 | 途径 | 用途 | 起始 | 医生 |
|------|------|------|------|------|------|------|
| 二甲双胍 | 500mg | 每日2次 | oral | 降血糖 | 2020-01 | 王医生 |
| 氨氯地平 | 5mg | 每日1次 | oral | 降血压 | 2018-03 | 李医生 |
```

### 近期检查渲染格式

```markdown
| 日期 | 项目 | 异常项 | 结论 |
|------|------|--------|------|
| 2026-05-20 | 糖化血红蛋白 | HbA1c 7.2% ↑ | 血糖控制欠佳 |
| 2026-04-15 | 胸部CT平扫 | 磨玻璃结节 8mm ↑ | 建议随访 |
| 2026-03-01 | 血常规 | — | 正常 |
```
*无异常项标记 `—`，异常项含 `↑↓` 符号。*

---

## 3. 住院总结 (Hospitalization Summary)

**目的：** 完整出院小结替代。供医生/患者掌握某次住院全貌。

**触发场景：**
- 患者出院时
- 转科时
- 病历归档时

**数据源：** hospitalizations.json（单条）, 关联的 exams, medications, timeline

### 模板

```
# 🏥 住院总结 — {患者姓名}

## 📋 基本信息
| 项目 | 内容 |
|------|------|
| 住院ID | {hospitalizationId} |
| 医院 | {hospital.name} ({hospital.level_label}) |
| 科室 | {department} |
| 床位 | {ward} |
| 入院类型 | {admissionType_label} |
| 主治医师 | {attendingPhysician} |
| 入院日期 | {admissionDate} |
| 出院日期 | {dischargeDate} |
| 住院天数 | {totalDays}天 |
| 总费用 | {totalCost}元 (医保报销 {insuranceCoverage}元) |

## 🩺 诊断
| 类型 | 诊断 |
|------|------|
| 入院诊断 | {admittingDiagnosis} |
| 出院诊断 | {dischargeDiagnosis} |
| 出院状态 | {dischargeStatus_label} |

## 📝 入院情况
**主诉：** {chiefComplaint}
**现病史：** {presentIllness}
**既往史：** {pastHistory}
**入院生命体征：** {vital_signs_summary}

---

## 📅 住院经过

{progress_timeline}
*按日期顺序，标注类型*

---

## 🔪 手术记录（如有）

{surgery_details}

---

## 👨‍⚕️ 会诊记录（如有）

{consultation_details}

---

## 🔬 住院期间检查（按日期）

{exam_results}
*异常项标记 ↑↓*

---

## 💊 用药记录

{medication_changes}
*住院期间所有用药及调整*

---

## 📋 出院小结

{dischargeSummary}

---

## 💊 出院带药

{discharge_medications}

---

## 📊 随访计划
| 项目 | 内容 |
|------|------|
| 复诊日期 | {followUpDate} |
| 复诊科室 | {followUpDepartment} |
| 复诊医生 | {followUpDoctor} |
| 医嘱 | {instructions} |
| 饮食建议 | {dietaryAdvice} |
| 活动限制 | {activityRestriction} |
| 需复诊指征 | {returnIf} |

---

*生成时间: {datetime}*
*数据来源: Family Health OS*
```

### 字段提取规则

| 模板字段 | 数据来源 | 提取逻辑 |
|---------|---------|---------|
| `hospital.level_label` | hospital.level | `tertiary→三级 / secondary→二级 / primary→一级 / clinic→诊所` |
| `admissionType_label` | admissionType | `emergency→急诊 / elective→择期 / transfer→转院` |
| `dischargeStatus_label` | dischargeStatus | `cured→痊愈 / improved→好转 / unchanged→未愈 / deteriorated→恶化 / transferred→转院 / died→死亡 / againstAdvice→自动出院` |
| `vital_signs_summary` | vitalSignsOnAdmission | `体温 {T}℃ | 心率 {HR}次/分 | 呼吸 {R}次/分 | 血压 {SBP}/{DBP}mmHg | 血氧 {SpO2}%` |
| `progress_timeline` | dailyProgress[] | 按日期分组，type 转换中文标签 |
| `surgery_details` | surgeries[] | 逐个渲染完整手术信息 |
| `consultation_details` | consultations[] | 按会诊渲染 |
| `exam_results` | exams (relatedHospitalizationId) | 住院期间的检查 |
| `medication_changes` | dailyProgress[].medicationChanges | 合并 dailyProgress 中的用药调整 |
| `discharge_medications` | dischargeMedications[] | 表格渲染 |

### 住院经过渲染

```markdown
| 日期 | 类型 | 内容 | 医生 |
|------|------|------|------|
| 2025-06-01 | 📋 日常病程 | 发热38.5℃，咳嗽，予物理降温 | 王医生 |
| 2025-06-01 | 🔬 开具检查 | 胸部CT平扫 | 李医生 |
| 2025-06-02 | 👨‍⚕️ 主任查房 | 考虑社区获得性肺炎，继续抗感染 | 刘主任 |
| 2025-06-02 | 🔬 检查结果 | CT示右肺下叶斑片状影，符合肺炎 | 张医生 |
| 2025-06-02 | 💊 用药调整 | start: 阿莫西林 500mg q8h 抗感染 | 王医生 |
| 2025-06-05 | 📋 日常病程 | 体温降至36.5℃，咳嗽减轻 | 王医生 |
| 2025-06-08 | 📊 生命体征 | T 36.4℃ HR 72 R 16 BP 120/80 SpO2 98% | 护士 |
| 2025-06-10 | 📋 出院 | 好转出院 | 王医生 |
```

### 手术详情渲染

```markdown
### 🔪 手术 #1
| 项目 | 内容 |
|------|------|
| 手术名称 | 左足清创术 |
| 手术日期 | 2025-06-05 14:30 |
| 主刀医生 | 赵主任 |
| 助手 | 钱医生 |
| 麻醉方式 | 局部麻醉 |
| 术前诊断 | 左足糖尿病足感染 |
| 术后诊断 | 左足糖尿病足感染伴骨髄炎 |
| 术中发现 | 第2、3趾间深部脓肿，骨质破坏 |
| 出血量 | 50mL |
| 手术结果 | 成功 |
```

---

## 4. 专家会诊摘要 (Consultation Summary)

**目的：** 跨科室会诊意见汇总。供多学科团队快速了解各科室意见。

**触发场景：**
- MDT（多学科会诊）后
- 住院期间多次会诊汇总
- 申请院外会诊时

**数据源：** hospitalizations.json.consultations[] + timeline 中的 consultation/doctor_round 事件

### 模板

```
# 👨‍⚕️ 专家会诊摘要 — {患者姓名}

## 📋 患者信息
| 项目 | 内容 |
|------|------|
| 姓名 | {name} |
| 住院/门诊号 | {visitInfo} |
| 主要诊断 | {primaryDiagnoses} |

## 🤝 会诊汇总

### 总会诊情况
- **会诊次数：** {totalConsultations}
- **涉及科室：** {departments_involved}
- **涉及医生：** {doctors_involved}
- **会诊类型：** 科内 / 科间 / 全院 / 院外
- **时间范围：** {earliest} ~ {latest}

---

{consultation_details}

---

## 🔗 会诊关联

### 会诊前后变化
{changes_after_consultation}

*会诊后发生了哪些诊疗变化（用药调整、手术决策、诊断变更等）*

### 待执行会诊建议
{pending_recommendations}

*尚未执行的会诊推荐方案*

---

## 📊 会诊统计
| 科室 | 次数 | 主要建议 |
|------|------|---------|
| {dept} | {count} | {summary} |

*生成时间: {datetime}*
*数据来源: Family Health OS*
```

### 单次会诊渲染

```markdown
---
### 🤝 会诊 #1 — {consultingDepartment}

| 项目 | 内容 |
|------|------|
| ⏰ 会诊日期 | {date} |
| 📞 申请科室 | {requestingDepartment} |
| 👨‍⚕️ 会诊医生 | {consultingDoctor} |
| 🏥 医院 | {hospitalName} |

**📝 会诊原因**
{reason}

**💡 会诊意见**
{opinion}

**📋 建议方案**
{recommendations}

**来源：** {hospitalName}
```

### 关联变化提取规则

从 timeline 中筛选会诊后 72 小时内（`event.date - consultation.date ≤ 3 days`）的事件：

```
会诊 #1 (2025-06-02 影像科)
  → 2025-06-03 用药调整：加用莫西沙星 ← (会诊后第1天)
  → 2025-06-04 检查：复查CT ← (会诊后第2天)
```

---

## 5. 复诊摘要 (Follow-up Summary)

**目的：** 复诊前准备。医生一页纸了解"上次之后发生了什么、当前状态、今天需要做什么"。

**触发场景：**
- 患者预约复诊前
- 慢性病定期随访
- 术后复查

**数据源：** timeline（上次复诊至今的事件）, diseases（控制目标vs最新值）, tasks（待办）, medications（当前用药 + 续药提醒）

### 模板

```
# 📊 复诊摘要 — {患者姓名}

## 👤 患者信息
| 项目 | 内容 |
|------|------|
| 姓名 | {name} | {age}岁 {gender_label} |
| 复诊日期 | {followUpDate} |
| 复诊科室 | {followUpDepartment} |
| 上次就诊 | {lastVisitDate} |
| 距上次复诊 | {daysSinceLastVisit}天 |

---

## 🔄 上次复诊至今的变化

### 新事件（{newEventsCount}件）
{new_events}
*上次复诊至今全部新发生事件*

### 用药变更
{medication_changes_since_last}
*新增/停用/调整的药品*

### 检查结果（最新）
{latest_exams}
*最新检查结果及与上次对比*

---

## 🎯 疾病控制目标

| 疾病 | 目标 | 最新值 | 达标 |
|------|------|--------|------|
| 2型糖尿病 | HbA1c < 7.0% | 7.2% (2026-05-20) | ❌ |
| 原发性高血压 | BP < 130/80 | 128/82 (2026-06-01) | ✅ |

---

## ⏳ 待办事项

{pending_tasks}
*逾期/待完成的复查、续药、随访*

---

## ❓ 建议复诊讨论要点

{discussion_points}
*基于当前状态的建议讨论议题*

---

## 📋 当前用药清单

{current_medications}

---

*生成时间: {datetime}*
*数据来源: Family Health OS*
```

### "上次复诊至今"的界定

```python
def get_last_followup_date(events, patient_id):
    """从 timeline 中查找上一次 followUp 事件的日期"""
    followups = [e for e in events if e.get("eventType") == "followUp"]
    return followups[-1]["date"][:10] if followups else None
```

如果无 followUp 记录，则取最近一次 discharge 日期或 events 中最早的日期。

### 新事件渲染

```markdown
| 日期 | 事件 | 详情 |
|------|------|------|
| 2026-06-01 | 🚨 急诊就诊 | 胸痛3小时，心电图未见异常 |
| 2026-06-05 | 🔬 冠脉CTA | 左前降支近段狭窄30% |
| 2026-06-08 | 💊 调整用药 | 增加阿司匹林 100mg qd |
```

### 疾病控制目标表格

```markdown
| 疾病 | 指标 | 目标 | 最新值(日期) | 判定 |
|------|------|------|-------------|------|
| 2型糖尿病 | 空腹血糖 | < 7.0 mmol/L | 8.1 (2026-06-10) | ❌ ↑ |
| 2型糖尿病 | HbA1c | < 7.0% | 7.2 (2026-05-20) | ❌ ↑ |
| 原发性高血压 | 收缩压 | < 130 mmHg | 128 (2026-06-10) | ✅ |
| 原发性高血压 | 舒张压 | < 80 mmHg | 82 (2026-06-10) | ❌ ↑ |
```
*判定规则：latest_value ≤ target → ✅；latest_value > target → ❌ + ↑*
*targetValues 从 diseases.json 的 targetValues 字段读取*

### 待办事项渲染

```markdown
| 状态 | 任务 | 截止日期 | 优先级 |
|------|------|---------|--------|
| ⏰ 逾期 | 复查糖化血红蛋白 | 2026-05-01 | high |
| 📅 即将 | 续开降压药(剩余3天) | 2026-06-20 | medium |
| ✅ 已完成 | 冠脉CTA检查 | 2026-06-05 | — |
```

### 建议讨论要点生成规则

基于数据分析自动生成建议讨论议题，不含诊断/治疗建议：

```python
def suggest_discussion_points(patient, diseases, exams, meds, tasks):
    points = []
    
    # 未达标控制目标
    for d in diseases:
        for target, current in check_targets(d):
            if not current["achieved"]:
                points.append(f"• **{d['diseaseName']}**：{target}未达标"
                              f"(当前{current['value']}，目标{current['target']}，"
                              f"检查日期{current['date']})")
    
    # 逾期任务
    for t in tasks:
        if t["status"] in ("pending", "overdue"):
            points.append(f"• **待办提醒**：{t['title']} (原定{t['dueDate'][:10]})")
    
    # 新异常检查结果
    for exam in exams[-3:]:  # 最近3次
        abnormal = [i for i in exam.get("items", []) 
                    if i.get("flag") not in ("normal", None)]
        if abnormal:
            names = ", ".join(i["name"] for i in abnormal[:3])
            points.append(f"• **检查异常**：{exam.get('examName', '')} ({names}异常)")
    
    # 用药即将到期
    for m in meds:
        if m.get("refillReminder", {}).get("enabled"):
            points.append(f"• **续药提醒**：{m['medicationName']} "
                         f"({m['refillReminder']['daysBeforeRefill']}天后需续药)")
    
    return points
```

---

## 6. CLI 工具: `scripts/generate_summary.py`

### 6.1 用法

```bash
# 病史摘要
python3 generate_summary.py <patientId> --type medical-history

# 住院总结
python3 generate_summary.py <patientId> --type hospitalization
python3 generate_summary.py <patientId> --type hospitalization --hospitalization <hospId>

# 会诊摘要
python3 generate_summary.py <patientId> --type consultation
python3 generate_summary.py <patientId> --type consultation --hospitalization <hospId>

# 复诊摘要
python3 generate_summary.py <patientId> --type follow-up
python3 generate_summary.py <patientId> --type follow-up --date 2026-07-01

# 输出控制
python3 generate_summary.py <patientId> --type medical-history --output report.md
```

### 6.2 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `patientId` | string | — | 患者UUID（必填） |
| `--type` | enum | `medical-history` | `medical-history` / `hospitalization` / `consultation` / `follow-up` |
| `--hospitalization <id>` | string | 最近一次 | 指定住院ID |
| `--date <date>` | date | today | 复诊日期（仅 follow-up） |
| `--output <file>` | string | stdout | 输出到文件 |
| `--data-dir <path>` | string | schemas/ | 数据目录 |

### 6.3 实现流程

```python
def generate_summary(patient_id, summary_type, data_dir, **kwargs):
    # Step 1: 加载患者
    patient = find_patient(patient_id, data_dir)
    
    # Step 2: 加载基础数据
    diseases = load_patient_diseases(patient_id, data_dir)
    exams = load_patient_exams(patient_id, data_dir)
    meds = load_patient_medications(patient_id, data_dir)
    hospitals = load_patient_hospitalizations(patient_id, data_dir)
    timeline = load_or_build_timeline(patient_id, data_dir)
    tasks = load_patient_tasks(patient_id, data_dir)
    
    # Step 3: 按类型选择摘要器
    if summary_type == "medical-history":
        summary = generate_medical_history(patient, diseases, exams, meds,
                                           hospitals, timeline)
    elif summary_type == "hospitalization":
        hosp_id = kwargs.get("hospitalization_id")
        summary = generate_hospitalization_summary(patient, hospitals,
                                                   exams, meds, timeline, hosp_id)
    elif summary_type == "consultation":
        summary = generate_consultation_summary(patient, hospitals, timeline)
    elif summary_type == "follow-up":
        followup_date = kwargs.get("followup_date")
        summary = generate_followup_summary(patient, diseases, exams, meds,
                                            timeline, tasks, followup_date)
    
    # Step 4: 渲染 Markdown
    return render_to_markdown(summary)
```

---

## 7. 输出规范

### 7.1 统一格式要求

| 规范 | 要求 |
|------|------|
| 文件编码 | UTF-8 |
| 标题层级 | `#` 文档标题 → `##` 章节 → `###` 子章节 → `####` 如需更细 |
| 表格 | 必须带表头分隔行 `\|------\|------\|` |
| 列表 | 无序列表用 `-`，有序用 `1.` |
| 粗体 | 关键数据用 `**` 包裹 |
| 异常标记 | `↑` `↓` `↑↑` `↓↓` 紧跟在值后面 |
| 来源标注 | 底部固定行 `*数据来源: Family Health OS*` |
| 时间标注 | 底部固定行 `*生成时间: {datetime}*` |

### 7.2 性别映射

| schema 值 | 显示 |
|-----------|------|
| `male` | 男 |
| `female` | 女 |
| `other` | 其他 |

### 7.3 医院等级映射

| schema 值 | 显示 |
|-----------|------|
| `tertiary` | 三级医院 |
| `secondary` | 二级医院 |
| `primary` | 一级医院 |
| `clinic` | 诊所 |
| `other` | 其他 |

### 7.4 过敏渲染规则

```python
def render_allergies(allergies):
    if not allergies:
        return "无已知过敏"
    parts = []
    for a in allergies:
        severity_label = {
            "mild": "轻度", "moderate": "中度",
            "severe": "重度", "anaphylaxis": "过敏性休克"
        }.get(a["severity"], a["severity"])
        reaction = f" ({a['reaction']})" if a.get("reaction") else ""
        parts.append(f"{a['allergen']}({severity_label}{reaction})")
    return "；".join(parts)
```

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| patientId 不存在 | 报错并列出可用患者 |
| 住院总结时无住院记录 | 提示"该患者无住院记录" |
| 会诊摘要时会诊事件为0 | "无会诊记录" |
| 复诊摘要时无既往数据 | "该患者尚无完整的病程记录" |
| 数据文件损坏 | 报错并提示检查 memory/schemas/ |
| timeline.json 不存在 | 自动调用 aggregate_timeline.py |

---

## 9. 三种摘要的对比

| 维度 | 病史摘要 | 住院总结 | 会诊摘要 | 复诊摘要 |
|------|---------|---------|---------|---------|
| **受众** | 新接诊医生 | 出院患者/下级医院 | MDT团队 | 复诊医生 |
| **时间跨度** | 全生命周期 | 单次住院 | 会诊期间 | 上次复诊至今 |
| **核心信息** | 疾病+用药+过敏 | 入院→经过→出院 | 各科室意见 | 近期变化+待办 |
| **数据源数量** | 6个 | 4个 | 2个 | 5个 |
| **聚焦点** | 全面了解 | 住院全流程 | 跨科室意见 | 对比+跟进 |
| **输出长度** | 中（约50-80行） | 长（约80-150行） | 短（约30-60行） | 中（约40-70行） |
| **典型用例** | 初诊/转诊 | 出院/转科 | MDT/会诊归档 | 慢性病复诊 |

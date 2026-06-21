# Family Health OS — Schema 字段参考指南

## 1. patients.json — 患者档案

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string (uuid) | ✓ | 患者唯一标识 |
| `name` | string | ✓ | 姓名 |
| `gender` | enum | ✓ | male / female / other |
| `birthDate` | date (YYYY-MM-DD) | ✓ | 出生日期 |
| `bloodType` | enum | | A+ / A- / B+ / B- / AB+ / AB- / O+ / O- / unknown |
| `allergies[]` | array | | 过敏史：allergen, severity (mild/moderate/severe/anaphylaxis), reaction, confirmedDate |
| `emergencyContact` | object | | name, relationship, phone, alternatePhone |
| `identityDocument` | object | | type (idCard/passport/other), number |
| `insurance` | object | | provider, policyNumber, coverage |
| `height` | number | | 身高 (cm) |
| `weight` | number | | 体重 (kg) |
| `bloodPressureBaseline` | object | | systolic (mmHg), diastolic (mmHg) |
| `familyHistory[]` | array | | disease, relationship, note |
| `lifestyle` | object | | smokingStatus, alcoholConsumption, occupation |
| `tags[]` | array | | 自定义标签 |
| `notes` | string | | 备注 |
| `isActive` | boolean | | 档案是否有效，默认 true |
| `createdAt` | date-time | | 建档时间 |
| `updatedAt` | date-time | | 最后更新时间 |

## 2. diseases.json — 疾病档案

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 疾病记录唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `diseaseName` | string | ✓ | 疾病名称 |
| `icdCode` | string | | ICD-10/11 编码 |
| `diagnosedDate` | date | ✓ | 确诊日期 |
| `diagnosedBy` | string | | 确诊医生/机构 |
| `diagnosisBasis` | string | | 诊断依据 |
| `status` | enum | ✓ | active / remission / controlled / resolved / recovered / chronic |
| `severity` | enum | | mild / moderate / severe / critical |
| `stage` | string | | 分期/分级 |
| `bodySite` | string | | 患病部位 |
| `chronic` | boolean | | 是否慢性病，默认 false |
| `episodes[]` | array | | 发作记录：{startDate, endDate, severity, trigger, symptoms[], treatment, outcome, hospitalizationId} |
| `complications[]` | array | | 并发症：{diseaseId, name, diagnosedDate} |
| `medications[]` | uuid[] | | 关联用药 ID 列表 |
| `currentManagement` | string | | 当前管理方案 |
| `targetValues` | object | | 控制目标：systolicTarget, diastolicTarget, hba1cTarget, fastingGlucoseTarget, ldlTarget, otherTargets[] |
| `notes` | string | | 备注 |
| `createdAt` | date-time | | |
| `updatedAt` | date-time | | |

## 3. exams.json — 检查报告

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 检查记录唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `examDate` | date-time | ✓ | 检查日期 |
| `reportDate` | date | | 报告出具日期 |
| `examType` | string | ✓ | bloodTest / urinalysis / xray / ct / mri / ecg / ultrasound / pathology / pulmonaryFunction / endoscopy 等 |
| `examName` | string | | 检查全称 |
| `department` | string | | 检查科室 |
| `hospital` | object | | {name, level} |
| `doctor` | string | | 开单医生 |
| `reportDoctor` | string | | 报告医生 |
| `items[]` | array | ✓ | 见下方 items 字段 |
| `conclusion` | string | | 检查结论 |
| `images[]` | array | | 影像附件：{type (dicom/jpg/png/pdf), url, description} |
| `attachments[]` | array | | 附件：{name, url, mimeType} |
| `relatedDiseaseIds[]` | uuid[] | | 关联疾病 |
| `relatedHospitalizationId` | uuid | | 关联住院 |
| `notes` | string | | 备注 |

### items[] 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✓ | 项目名称（如"白细胞计数"） |
| `code` | string | | LOINC 编码 |
| `value` | string / number / boolean | ✓ | 检测值 |
| `unit` | string | | 单位 |
| `referenceRange` | string | | 参考范围文本（如 "3.5-9.5"） |
| `referenceLow` | number | | 参考范围下限 |
| `referenceHigh` | number | | 参考范围上限 |
| `flag` | enum | | normal / high / low / criticalHigh / criticalLow / abnormal |
| `displayFlag` | string | | 展示符号：↑ / ↓ / ↑↑ / ↓↓ |
| `method` | string | | 检测方法 |
| `notes` | string | | 单项备注 |

**异常标记规则**：
- value > referenceHigh → flag: "high", displayFlag: "↑"
- value < referenceLow → flag: "low", displayFlag: "↓"
- 危急值范围另用 criticalHigh / criticalLow → displayFlag: "↑↑" / "↓↓"

## 4. medications.json — 用药记录

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 用药记录唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `medicationName` | string | ✓ | 通用名 |
| `brandName` | string | | 商品名 |
| `genericName` | string | | 英文 INN 名 |
| `atcCode` | string | | ATC 编码 |
| `dosageForm` | enum | | tablet / capsule / injection / liquid / cream / inhaler / patch / drops / suppository / other |
| `dosage` | object | ✓ | {amount, unit, concentration} |
| `frequency` | object | ✓ | {timesPerDay, interval, timing[], asNeeded, maxDailyDose} |
| `route` | enum | | oral / intravenous / intramuscular / subcutaneous / topical / inhalation / sublingual / rectal / ophthalmic / otic / intrathecal / other |
| `startDate` | date | ✓ | 开始日期 |
| `endDate` | date | | 停药日期（null = 仍在用药） |
| `isOngoing` | boolean | | 由 endDate 推断，默认 true |
| `prescribedBy` | string | | 开药医生 |
| `prescriptionDate` | date | | 处方日期 |
| `purpose` | string | | 用药目的 |
| `relatedDiseaseIds[]` | uuid[] | | 关联疾病 |
| `relatedHospitalizationId` | uuid | | 关联住院 |
| `sideEffects[]` | array | | {effect, severity (mild/moderate/severe), onsetDate, action} |
| `adherence` | enum | | good / fair / poor / unknown |
| `reasonForStop` | string | | 停药原因 |
| `refillReminder` | object | | {enabled, daysBeforeRefill, supplyDays} |
| `notes` | string | | 备注 |

## 5. hospitalizations.json — 住院档案

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 住院唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `admissionDate` | date-time | ✓ | 入院时间 |
| `dischargeDate` | date-time | | 出院时间（null=在院） |
| `admissionType` | enum | | emergency / elective / transfer / other |
| `hospital` | object | ✓ | {name, level} |
| `department` | string | ✓ | 入院科室 |
| `ward` | string | | 病房/床位 |
| `admittingDiagnosis` | string | ✓ | 入院诊断 |
| `admittingDoctor` | string | | 接诊医生 |
| `attendingPhysician` | string | | 主治医生 |
| `chiefComplaint` | string | | 主诉 |
| `presentIllness` | string | | 现病史 |
| `pastHistory` | string | | 既往史 |
| `vitalSignsOnAdmission` | object | | {temperature, heartRate, respiratoryRate, bloodPressureSystolic, bloodPressureDiastolic, oxygenSaturation} |

### dailyProgress[] 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `date` | date | ✓ | 记录日期 |
| `content` | string | ✓ | 病程内容 |
| `doctor` | string | | 记录医生 |
| `type` | enum | | dailyProgress / roundNote / consultationNote / criticalNote / preOpNote / postOpNote / transferNote |
| `vitalSigns` | object | | 当日生命体征 |
| `medicationChanges[]` | array | | {action (start/stop/adjust/continue), medicationName, newDosage, reason} |
| `examResults[]` | array | | {examId, keyFinding} |
| `assessment` | string | | 当日评估 |
| `plan` | string | | 诊疗计划 |

### surgeries[] 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `surgeryDate` | date-time | ✓ | 手术时间 |
| `surgeryName` | string | ✓ | 手术名称 |
| `surgeon` | string | ✓ | 主刀医生 |
| `assistant` | string | | 助手 |
| `anesthesiaType` | enum | | general / spinal / local / regional / other |
| `anesthesiologist` | string | | 麻醉医生 |
| `preOpDiagnosis` | string | | 术前诊断 |
| `postOpDiagnosis` | string | | 术后诊断 |
| `procedure` | string | | 手术过程 |
| `findings` | string | | 术中发现 |
| `bloodLoss` | string | | 出血量 |
| `bloodTransfusion` | string | | 输血情况 |
| `complications[]` | string[] | | 术中并发症 |
| `outcome` | string | | 手术结果 |
| `pathologyId` | uuid | | 关联病理检查 |

### 其他字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `consultations[]` | array | {date, consultingDepartment, consultingDoctor, reason, opinion, recommendations} |
| `dischargeDiagnosis` | string | 出院诊断 |
| `dischargeStatus` | enum | cured / improved / unchanged / deteriorated / transferred / died / againstAdvice |
| `dischargeSummary` | string | 出院小结 |
| `dischargeMedications[]` | array | 出院带药：{medicationName, dosage, frequency, duration, medicationId} |
| `followUpPlan` | object | {followUpDate, followUpDepartment, followUpDoctor, instructions, dietaryAdvice, activityRestriction, returnIf} |
| `totalDays` | integer | 住院天数（自动计算） |
| `totalCost` | number | 总费用（元） |
| `insuranceCoverage` | number | 医保报销（元） |

## 6. timeline.json — 病程时间轴

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 时间轴唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `generatedAt` | date-time | | 生成时间 |
| `generatedBy` | string | | auto / manual |
| `events[]` | array | ✓ | 事件列表（按时间升序） |
| `monthlyGroups` | object | | 键为 "YYYY-MM"，值为事件 ID 数组 |
| `summary` | string | | 病程摘要文本 |
| `eventCount` | integer | | 事件总数 |
| `dateRange` | object | | {earliest, latest} |
| `version` | integer | | 版本号，默认 1 |

### events[] 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eventId` | string | ✓ | 事件唯一标识 |
| `date` | date-time | ✓ | 事件时间 |
| `eventType` | enum | ✓ | 见下方事件类型 |
| `title` | string | ✓ | 事件标题 |
| `description` | string | | 详细描述 |
| `severity` | enum | | info / warning / critical / normal |
| `sourceType` | enum | | hospitalization / exam / medication / disease / manual / task |
| `sourceId` | string | | 来源数据 ID |
| `sourceDoctor` | string | | 信息来源医生 |
| `sourceInstitution` | string | | 信息来源机构 |
| `tags[]` | string[] | | 自定义标签 |
| `metadata` | object | | {value, unit, flag (↑/↓/normal), location, duration} |
| `relatedEventIds[]` | string[] | | 关联事件 |

### 事件类型枚举 (eventType)

29 种事件类型，分为 9 个分类：

| eventType | 分类 | 说明 |
|-----------|------|------|
| `admission` | administrative | 入院 |
| `discharge` | administrative | 出院 |
| `transfer` | administrative | 转科/转院 |
| `surgery` | surgical | 手术 |
| `procedure` | surgical | 其他操作 |
| `exam` | diagnostic | 检查记录 |
| `new_exam` | diagnostic | 新开检查 |
| `exam_result` | diagnostic | 检查结果回报 |
| `labResult` | diagnostic | 检验结果 |
| `imaging` | diagnostic | 影像检查 |
| `pathology` | diagnostic | 病理检查 |
| `medicationStart` | medication | 开始用药 |
| `medicationStop` | medication | 停药 |
| `medicationChange` | medication | 用药调整 |
| `diagnosis` | clinical | 确诊 |
| `diagnosisChange` | clinical | 诊断变更 |
| `symptom` | clinical | 症状记录 |
| `symptom_change` | clinical | 症状变化 |
| `round` | clinical | 查房 |
| `doctor_round` | clinical | 医生查房 |
| `consultation` | clinical | 会诊 |
| `note` | clinical | 病程记录 |
| `vitalSigns` | monitoring | 生命体征 |
| `followUp` | monitoring | 随访 |
| `emergency` | emergency | 紧急事件 |
| `allergyReaction` | emergency | 过敏反应 |
| `vaccination` | preventive | 疫苗接种 |
| `healthCheckup` | preventive | 体检 |
| `other` | other | 其他 |

### 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `eventIdSource` | enum | auto / manual |
| `category` | enum | 事件分类（9类） |
| `isKeyEvent` | boolean | 是否标记为里程碑节点 |
| `affectedBodySite` | string | 事件涉及的身体部位 |
| `eventTypeCategoryMap` | object | 类型→分类映射表（参考） |

### 事件ID格式

```
evt-{源类型缩写}-{YYYYMMDD}-{4位随机}
```

| 源类型 | 缩写 |
|--------|------|
| hospitalization | hosp |
| exam | exam |
| medication | med |
| disease | dis |
| task | task |
| manual | man |

### 聚合引擎

`scripts/aggregate_timeline.py` — 自动从各数据源读取记录，
按患者ID聚合生成完整时间轴事件，包含：
- 住院：入院→每日病程→手术→会诊→出院→随访
- 检查：开具→结果回报（异常标记）
- 用药：开始→副作用→停药
- 疾病：确诊→发作/复发→并发症
- 任务：提醒事件
- 自动按时间排序 + 月份分组索引 + 病程摘要生成

## 7. tasks.json — 复查提醒与任务

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | uuid | ✓ | 任务唯一标识 |
| `patientId` | uuid | ✓ | 关联患者 |
| `taskType` | enum | ✓ | 见下方任务类型 |
| `title` | string | ✓ | 任务标题 |
| `description` | string | | 详细描述 |
| `priority` | enum | | low / medium / high / urgent |
| `status` | enum | | pending / inProgress / completed / cancelled / overdue / deferred |
| `dueDate` | date-time | ✓ | 截止/提醒时间 |
| `completedDate` | date-time | | 完成时间 |
| `completedBy` | string | | 完成者 |
| `recurrence` | object | | {enabled, interval, unit (day/week/month/year), cronExpression, endDate, maxOccurrences, occurrenceCount, nextDueDate} |
| `reminder` | object | | {enabled, advanceNotice, remindAt, channels[], message} |
| `relatedEntities` | object | | {examType, medicationId, hospitalizationId, diseaseId} |
| `notes` | string | | 备注 |
| `tags[]` | string[] | | 自定义标签 |
| `createdBy` | string | | 创建者 |

### 任务类型枚举 (taskType)

```
followUp / examReminder / medicationRefill / medicationReminder /
vaccination / labTest / imaging / checkup / surgeryFollowUp /
rehabilitation / dietaryLog / bloodPressureLog / bloodSugarLog /
weightLog / generalReminder / other
```

---

## Schema 索引速查

```
关联路径                          参考文件
──────                           ────────
patients.id                     所有表的 patientId 字段
diseases.patientId              diseases.json
exams.patientId                 exams.json
medications.patientId           medications.json
hospitalizations.patientId      hospitalizations.json
timeline.patientId              timeline.json
tasks.patientId                 tasks.json
diseases.id                     exams.relatedDiseaseIds[]
                                medications.relatedDiseaseIds[]
diseases.episodes[].hospitalizationId → hospitalizations.id
exams.id                        hospitalizations.dailyProgress[].examResults[].examId
medications.id                  hospitalizations.medications[]
hospitalizations.id             diseases.episodes[].hospitalizationId
                                exams.relatedHospitalizationId
                                medications.relatedHospitalizationId
```

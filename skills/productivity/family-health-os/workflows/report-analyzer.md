# Medical Report Analyzer Workflow

**适用场景：** 用户上传检查报告图片/PDF → Agent 自动 OCR → 识别类型 → 提取结构化字段 → 写入 Memory → 更新时间轴

**支持的6种报告类型：**

| # | 报告类型 | examType | 目标 Schema |
|---|---------|----------|-------------|
| 1 | CT | `ct` | exams.json |
| 2 | CTA | `cta` | exams.json |
| 3 | 彩超 | `ultrasound` | exams.json |
| 4 | 病理 | `pathology` | exams.json |
| 5 | 检验报告 | `bloodTest` / `urinalysis` 等 | exams.json |
| 6 | 出院记录 | — | hospitalizations.json |

---

## 工作流总览

```
用户上传图片/PDF
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: OCR 文本提取                                         │
│ 工具: skill_view('ocr-and-documents')                        │
│ 输出: 纯文本 (raw_text)                                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 报告类型识别                                          │
│ 依据: 标题行、报告名称、检查项目描述                            │
│ 输出: report_type + confidence                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 结构化字段提取                                        │
│ 按报告类型调用对应的提取模板 (见下文)                           │
│ 输出: structured_data (dict)                                 │
└─────────────────────────────────────────────────────────────┘
    │
    ├──→ 检查/检验类 → exams.json 写入
    ├──→ 出院记录   → hospitalizations.json 写入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 写入 Memory 数据文件                                  │
│ 路径: memory/schemas/{exams,hospitalizations}.json           │
│ 操作: 读现有数据 → append → 写回                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 更新时间轴                                           │
│ 运行: scripts/aggregate_timeline.py <patientId>              │
│ 输出: 更新后的 timeline.json                                  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 6: 输出摘要给用户                                        │
│ 格式: "已识别【X报告】→ 已写入 → 时间轴已更新"                  │
│ 异常标记 ↑↓，结论摘要                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: OCR

### 工具
- 加载 `ocr-and-documents` skill → `skill_view(name='ocr-and-documents')`
- 使用 `marker-pdf` 或 `pymupdf` 从图片/PDF 提取文本

### 输入
```
文件路径: 用户上传的图片/PDF (MEDIA: 方式传入)
```

### 输出
```
raw_text: str  — 完整 OCR 文本
confidence: float — OCR 置信度 (可选)
```

### Fallback 策略
- 如果 marker-pdf 失败 → 尝试 pymupdf
- 如果纯图片 OCR 质量差 → 标记 `occlusion_warning: true`，提示用户确认

---

## Step 2: 报告类型识别

### 识别规则

| 报告类型 | 关键词 | 辅助特征 |
|---------|--------|---------|
| CT | CT、计算机断层、平扫、增强、螺旋 | body_part + "CT" |
| CTA | CTA、CT血管、CT动脉 | "CTA" + 血管名 |
| 彩超 | 彩超、彩色多普勒、超声、B超 | "超声" + specific organ |
| 病理 | 病理、病理诊断、HE、免疫组化、IHC | 含免疫组化表 |
| 检验报告 | 血常规、生化、凝血、尿常规 | 含项目+结果+参考范围表格 |
| 出院记录 | 出院记录、出院小结、出院诊断 | 含入院/出院日期、主诉 |

### 优先级
1. 首先匹配标题行（如 `XX医院 CT检查报告单`）
2. 其次匹配文中所含明确报告名称
3. 最后按文本模式特征判断

### 输出
```python
{
  "report_type": "ct" | "cta" | "ultrasound" | "pathology" |
                  "bloodTest" | "urinalysis" | "discharge",
  "confidence": "high" | "medium" | "low",
  "reasoning": "匹配到的关键词说明"
}
```

### 未知类型处理
- 如果 `confidence != "high"` 或匹配不到类型 → 标记 `report_type: "unknown"`，提示用户确认

---

## Step 3: 结构化字段提取

### 3.1 报告通用字段（所有检查报告共享）

```python
{
  "patientName": str,          # 患者姓名
  "patientId": str,             # 病历号 (非 schema id)
  "gender": str,                # 性别
  "age": int,                   # 年龄
  "examDate": str,              # 检查日期 (ISO 8601)
  "reportDate": str,            # 报告日期
  "hospital": {                 # 医院信息
    "name": str,
    "level": str | None
  },
  "department": str,            # 科室
  "doctor": str,                # 开单/申请医生
  "reportDoctor": str,          # 报告/审核医生
  "conclusion": str,            # 检查结论/印象
  "images": [                   # 原始图片附件
    {
      "type": "jpg"|"png"|"pdf",
      "url": str,
      "description": str
    }
  ]
}
```

---

### 3.2 CT 报告 (examType: `ct`)

**特征字段**

| 字段 | 类型 | 说明 | 提取来源 |
|------|------|------|---------|
| `examName` | string | `"XX部位CT平扫/增强"` | 标题行 |
| `bodyPart` | string | 扫描部位（如"胸部"） | 标题/图像描述 |
| `scanType` | string | `plain` / `enhanced` / `both` | 明确标识 |
| `technique` | string | 扫描技术参数（层厚、螺距等） | 技术描述段 |
| `findings` | string | 影像所见（详细描述） | 影像所见段落 |
| `conclusion` | string | 诊断结论/印象 | 结论段落 |
| `items` | array\[object\] | 结构化病灶列表 | 见下方 |

**items[] 病灶结构**

```python
{
  "name": str,            # 病灶名称（"右肺上叶磨玻璃结节"）
  "location": str,        # 位置（"右肺上叶尖段"）
  "size": str,            # 大小（"约8mm×6mm"）
  "density": str,         # 密度（"磨玻璃"|"实性"|"混合"）
  "margin": str,          # 边缘（"光滑"|"分叶"|"毛刺"）
  "features": [str],      # 特征标签（"钙化"|"空泡"|"胸膜凹陷"）
  "comparison": str,      # 与前次对比
  "flag": "normal"|"abnormal"|"new"|"enlarged"|"reduced"
}
```

**items[] 示例**

```json
[
  {
    "name": "磨玻璃结节",
    "location": "右肺上叶尖段",
    "size": "8mm×6mm",
    "density": "磨玻璃",
    "margin": "分叶",
    "features": ["空泡征"],
    "comparison": "较前次(2025-01)无明显变化",
    "flag": "abnormal",
    "displayFlag": "↑"
  },
  {
    "name": "主动脉钙化",
    "location": "主动脉弓",
    "size": "管壁弧形钙化",
    "flag": "abnormal"
  }
]
```

---

### 3.3 CTA 报告 (examType: `cta`)

**特征字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `examName` | string | `"XX动脉CTA"` |
| `vessel` | string | 检查血管名称（"冠状动脉""颅内动脉""腹主动脉"） |
| `technique` | string | 扫描技术参数 |
| `findings` | string | 影像所见 |
| `stenosis` | object | 狭窄评估 |

**stenosis 结构**

```python
{
  "segments": [
    {
      "name": str,           # 血管段名称（"LAD近段"）
      "severity": str,       # "none"|"mild"|"moderate"|"severe"|"occlusion"
      "stenosisPercent": int,# 狭窄百分比
      "plaqueType": str,     # "calcified"|"mixed"|"noncalcified"|"soft"
      "length": str          # 病变长度
    }
  ],
  "calcificationScore": int, # 钙化积分（冠脉CTA适用）
  "dominance": str           # 冠脉优势型（冠脉CTA适用）
}
```

---

### 3.4 彩超报告 (examType: `ultrasound`)

**特征字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `examName` | string | `"XX部位彩超"` |
| `bodyPart` | string | 检查部位（"甲状腺""乳腺""心脏""腹部"） |
| `findings` | string | 超声所见描述 |
| `conclusion` | string | 超声提示/结论 |
| `items` | array\[object\] | 测量值 + 病灶 |

**items[] 结构**

```python
{
  "name": str,              # 项目名称（"左叶大小""CDFI"）
  "value": str|number,      # 测量值
  "unit": str,              # 单位（"mm"|"cm"|"mL/s" 等）
  "referenceRange": str,    # 参考范围
  "flag": str,              # "normal"|"high"|"low"|"abnormal"
  "displayFlag": str,       # "↑"|"↓"
  # —— 病灶描述 ——
  "location": str,          # 位置
  "size": str,              # 大小
  "border": str,            # 边界（"清晰"|"模糊"）
  "echogenicity": str,      # 回声（"高"|"低"|"无"|"混合"）
  "shape": str,             # 形态
  "calcification": str,     # 钙化
  "bloodFlow": str,         # 血流信号（Adler分级等）
  "birads": str             # BI-RADS分级（乳腺适用）
}
```

---

### 3.5 病理报告 (examType: `pathology`)

**特征字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `examName` | string | `"XX部位病理诊断"` |
| `specimenType` | string | 标本类型（"穿刺""切除""活检"） |
| `specimenSite` | string | 取样部位 |
| `grossDescription` | string | 肉眼所见 |
| `microscopicDescription` | string | 镜下所见 |
| `ihcResults` | array\[object\] | 免疫组化结果 |
| `molecularResults` | array\[object\] | 分子检测结果 |
| `pathologicalDiagnosis` | string | 病理诊断（核心结论） |
| `pTNM` | string | pTNM分期 |
| `grading` | string | 分化/分级（"低分化"|"中分化"|"高分化"） |
| `items` | array\[object\] | 结构化诊断项 |

**ihcResults 结构**

```python
[
  {
    "marker": str,          # 标记物（"ER""PR""HER2""Ki-67"）
    "result": str,          # 结果（"+""-""++""+++""阳性率80%"）
    "interpretation": str   # 判读（"阳性""阴性""扩增"等）
  }
]
```

**items[] 示例**

```json
[
  {
    "name": "镜下诊断",
    "value": "浸润性导管癌，II级"
  },
  {
    "name": "送检淋巴结",
    "value": "3/12枚见癌转移"
  }
]
```

---

### 3.6 检验报告 (examType: `bloodTest` / `urinalysis` / `biochemistry` / `coagulation` 等)

**特征字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `examName` | string | `"血常规""肝功能""凝血四项"` |
| `examType` | string | `bloodTest` / `urinalysis` / `biochemistry` / `coagulation` / `hormone` / `tumorMarker` / `immunology` 等 |
| `items` | array\[object\] | **核心字段** — 每个检验项目一条 |

**items[] 结构（为核心设计）**

```python
{
  "name": str,                 # 项目中文名（"白细胞计数""空腹血糖"）
  "code": str,                 # LOINC编码（如有）
  "value": str|number,         # 检验值
  "unit": str,                 # 单位
  "referenceRange": str,       # 参考范围文本（"3.5-9.5"）
  "referenceLow": float|None,  # 参考下限（数值化后）
  "referenceHigh": float|None, # 参考上限（数值化后）
  "flag": "normal"|"high"|"low"|"criticalHigh"|"criticalLow",
  "displayFlag": "↑"|"↓"|"↑↑"|"↓↓"|"",
  "method": str,               # 检测方法
  "notes": str                 # 备注
}
```

**异常标记规则（自动化）**

| 条件 | flag | displayFlag |
|------|------|-------------|
| value > referenceHigh | `high` | `↑` |
| value < referenceLow | `low` | `↓` |
| value > criticalHigh | `criticalHigh` | `↑↑` |
| value < criticalLow | `criticalLow` | `↓↓` |
| 其他异常（定性） | `abnormal` | — |

---

### 3.7 出院记录 (目标 schema: `hospitalizations.json`)

**特征字段**

| 字段 | 类型 | 说明 | Schema 映射 |
|------|------|------|-------------|
| `admissionDate` | date-time | 入院日期 | → hospitalizations.admissionDate |
| `dischargeDate` | date-time | 出院日期 | → hospitalizations.dischargeDate |
| `hospital` | object | 医院信息 | → hospitalizations.hospital |
| `department` | string | 科室 | → hospitalizations.department |
| `ward` | string | 病房 | → hospitalizations.ward |
| `admittingDiagnosis` | string | 入院诊断 | → hospitalizations.admittingDiagnosis |
| `dischargeDiagnosis` | string | 出院诊断 | → hospitalizations.dischargeDiagnosis |
| `chiefComplaint` | string | 主诉 | → hospitalizations.chiefComplaint |
| `presentIllness` | string | 现病史 | → hospitalizations.presentIllness |
| `pastHistory` | string | 既往史 | → hospitalizations.pastHistory |
| `admissionStatus` | string | 入院情况 | → hospitalizations.presentIllness (expand) |
| `treatmentProcess` | string | 诊疗经过 | → hospitalizations.dailyProgress[] |
| `dischargeStatus` | enum | 出院情况 | → hospitalizations.dischargeStatus |
| `dischargeSummary` | string | 出院小结正文 | → hospitalizations.dischargeSummary |
| `dischargeMedications` | array | 出院带药 | → hospitalizations.dischargeMedications |
| `followUpAdvice` | string | 出院医嘱/随访 | → hospitalizations.followUpPlan |
| `attendingPhysician` | string | 主治医师 | → hospitalizations.attendingPhysician |
| `admittingDoctor` | string | 接诊医师 | → hospitalizations.admittingDoctor |

**出院带药结构**

```python
{
  "medicationName": str,     # 药品名
  "dosage": str,             # 剂量（"50mg"）
  "frequency": str,          # 频率（"每日两次"）
  "duration": str,           # 疗程（"7天"）
  "medicationId": str|None   # 关联medications.id
}
```

**诊疗经过 → dailyProgress 转换规则**

出院记录中的"诊疗经过"段落按时间顺序拆分，每条生成一个 `dailyProgress` 记录：

```
"入院后予阿莫西林抗感染治疗，3日后体温降至正常。
第5日复查CT示肺部炎症明显吸收。
第7日改为口服用药，第9日好转出院。"
↓
dailyProgress = [
  { date: <admissionDate+0>, content: "入院后予阿莫西林抗感染治疗", type: "dailyProgress" },
  { date: <admissionDate+3>, content: "体温降至正常", type: "dailyProgress" },
  { date: <admissionDate+5>, content: "复查CT示肺部炎症明显吸收", type: "dailyProgress", examResults: [{keyFinding: "肺部炎症明显吸收"}] },
  { date: <admissionDate+7>, content: "改为口服用药", type: "dailyProgress", medicationChanges: [{action: "adjust", medicationName: "阿莫西林"}] },
  { date: <dischargeDate>, content: "好转出院", type: "dailyProgress" }
]
```

---

## Step 4: 写入 Memory

### 4.1 数据文件路径

| 报告类型 | 目标文件 |
|---------|---------|
| CT / CTA / 彩超 / 病理 / 检验 | `memory/schemas/exams.json` |
| 出院记录 | `memory/schemas/hospitalizations.json` |

### 4.2 写入规则

**exams.json 写入：**
1. 读取现有数组（如果文件是一个对象数组则直接读取；如果是对象含 `exams` key 则取该项）
2. 生成新 record:
   - `id`: `str(uuid.uuid4())`
   - `patientId`: 从上下文或用户指定获取
   - 其他字段从 Step 3 提取数据映射
3. `items[]` 中每个项目的 `flag` / `displayFlag` 按异常标记规则自动计算
4. 如果本次是住院期间的检查，设置 `relatedHospitalizationId`
5. 如果有相关疾病记录，设置 `relatedDiseaseIds[]`
6. `createdAt` = `updatedAt` = `now()`
7. `append()` → `write_file(memory/schemas/exams.json, data)`

**hospitalizations.json 写入（出院记录）：**
1. 读取现有数组
2. 生成新 record:
   - `id`: `str(uuid.uuid4())`
   - `patientId`: 从上下文获取
   - 映射出院记录字段
   - `dischargeSummary` = OCR 提取的出院小结全文
   - `dailyProgress[]` = 从诊疗经过拆分的每日病程
   - `totalDays` = 自动计算 `(dischargeDate - admissionDate).days`
3. `createdAt` = `updatedAt` = `now()`
4. `append()` → `write_file(...)`

### 4.3 患者匹配

- 优先使用 OCR 提取的患者姓名 + 上下文中的 patient list 匹配
- 如果提取不出明确患者 → 提示用户选择或新增

---

## Step 5: 更新时间轴

### 执行
```python
# 运行聚合引擎
terminal(f"python3 {SKILL_DIR}/scripts/aggregate_timeline.py {patientId} --data-dir {DATA_DIR}")
```

### 输出
- 更新后的 `timeline.json`
- 新添加的事件会在时间轴上体现（如 `new_exam` / `exam_result` / `discharge` 等）

---

## Step 6: 输出摘要

### 格式模板

**检查报告类：**
```
✅ 已识别【{examName}】
🏥 {hospital.name} | 检查日期: {examDate}
📊 共 {len(items)} 项，其中异常 {abnormal_count} 项
{abnormal_items_summary}
📋 结论：{conclusion[:100]}
📎 已写入档案 | ⏱ 时间轴已更新
```

**出院记录类：**
```
✅ 已识别【出院记录】
🏥 {hospital.name}
📅 入院: {admissionDate} → 出院: {dischargeDate} ({totalDays}天)
📋 入院诊断: {admittingDiagnosis}
📋 出院诊断: {dischargeDiagnosis}
📎 已写入住院档案 | ⏱ 时间轴已更新
```

**异常汇总展示规则：**
- 每行最多展示 5 个异常项
- 超出部分标记 `...及其他 {n} 项`
- 危急值标记 `🔴` + `↑↑` / `↓↓`

---

## 错误处理

| 场景 | 处理 |
|------|------|
| OCR 提取为空 | 提示"未能从图片中提取到文本，请确认图片清晰" |
| 报告类型无法识别 | 标记为 `unknown`，展示前 200 字 OCR 结果，让用户确认 |
| 数值提取但缺少参考范围 | 设 flag 为 `abnormal`（无法判断高低），标记 `missing_reference: true` |
| 患者姓名无法匹配 | 列出已有患者列表，让用户选择 |
| 数据文件不存在 | 创建新数组，初始化 |

---

## 附录：报告类型→examType 映射表

| OCR 检测关键词 | examType | 说明 |
|---------------|----------|------|
| CT平扫、CT增强 | `ct` | |
| CTA、CT血管成像 | `cta` | |
| 彩超、彩色多普勒、超声 | `ultrasound` | |
| 病理、HE染色、免疫组化 | `pathology` | |
| 血常规、CBC | `bloodTest` | |
| 尿常规、尿液分析 | `urinalysis` | |
| 生化、肝功、肾功、电解质 | `biochemistry` | |
| 凝血四项、PT、APTT | `coagulation` | |
| 甲功、甲状腺功能 | `hormone` | |
| 肿瘤标志物、AFP、CEA | `tumorMarker` | |
| 乙肝、免疫、抗体 | `immunology` | |
| 微生物、培养、药敏 | `microbiology` | |
| 血气分析 | `bloodGas` | |
| 糖化血红蛋白、HbA1c | `hba1c` | |
| 心电图、ECG | `ecg` | |
| 骨密度、DXA | `boneDensity` | |
| MRI、磁共振 | `mri` | |
| 肺功能、PFT | `pulmonaryFunction` | |
| 内镜、胃镜、肠镜 | `endoscopy` | |

## 附录：CT 报告病灶 flag 规则

| flag | 含义 | 触发条件 |
|------|------|---------|
| `normal` | 正常 | 结论为阴性/未见异常 |
| `abnormal` | 异常发现 | 描述列表非空 |
| `new` | 新发病灶 | 对比前次"新出现" |
| `enlarged` | 增大 | 对比前次"增大/size increase" |
| `reduced` | 缩小/好转 | 对比前次"缩小/减轻" |

## 附录：CRITICAL 值段匹配规则（检验报告）

当 items[].value 满足以下条件时标记 `flag: criticalHigh` / `displayFlag: ↑↑`：

| 项目 | 危急值下限 | 危急值上限 |
|------|-----------|-----------|
| 白细胞计数 WBC | <1.0 ×10⁹/L | >30 ×10⁹/L |
| 血小板 PLT | <20 ×10⁹/L | >1000 ×10⁹/L |
| 血红蛋白 Hb | <50 g/L | >200 g/L |
| 血钾 K+ | <2.5 mmol/L | >6.5 mmol/L |
| 血钠 Na+ | <120 mmol/L | >160 mmol/L |
| 血糖 Glu | <2.2 mmol/L | >25 mmol/L |
| 肌钙蛋白 cTnI | — | >0.5 ng/mL |
| D-二聚体 | — | >5 mg/L FEU |

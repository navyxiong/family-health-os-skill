# Report Type Identification Quick Reference

## 报告类型 → examType → Schema

| 报告类型 | examType | 目标 Schema | 关键词 |
|---------|----------|-------------|--------|
| CT平扫/增强 | ct | exams.json | CT, 计算机断层, 平扫, 增强, 螺旋, 层厚 |
| CTA | cta | exams.json | CTA, CT血管, CT动脉, CTV |
| 彩超/超声 | ultrasound | exams.json | 彩超, 彩色多普勒, 超声, B超, 二维 |
| 病理诊断 | pathology | exams.json | 病理, HE, 免疫组化, IHC, 病理诊断 |
| 血常规 | bloodTest | exams.json | 血常规, CBC, 白细胞, 红细胞, 血红蛋白 |
| 尿常规 | urinalysis | exams.json | 尿常规, 尿液, 尿蛋白, 尿糖 |
| 生化全套 | biochemistry | exams.json | 生化, 肝功, 肾功, 电解质, 血脂 |
| 凝血功能 | coagulation | exams.json | 凝血, PT, APTT, INR, D-二聚体 |
| 甲功 | hormone | exams.json | 甲功, 甲状腺, TSH, FT3, FT4 |
| 肿瘤标志物 | tumorMarker | exams.json | 肿瘤标志物, AFP, CEA, CA19-9, CA125 |
| 乙肝/免疫 | immunology | exams.json | 乙肝, 免疫, 抗体, HBsAg |
| HbA1c | hba1c | exams.json | 糖化血红蛋白, HbA1c |
| 血气分析 | bloodGas | exams.json | 血气, pH, PaO2, PaCO2 |
| 微生物/培养 | microbiology | exams.json | 培养, 药敏, 涂片 |
| MRI | mri | exams.json | MRI, 磁共振, 核磁 |
| ECG | ecg | exams.json | 心电图, ECG, 心电 |
| 肺功能 | pulmonaryFunction | exams.json | 肺功能, PFT, FEV1, FVC |
| 骨密度 | boneDensity | exams.json | 骨密度, DXA |
| 内镜 | endoscopy | exams.json | 胃镜, 肠镜, 内镜 |
| 出院记录 | — | hospitalizations.json | 出院记录, 出院小结, 出院诊断 |

## 匹配优先级

```
1. 标题行匹配（XX医院 XX检查报告单）
2. 文内关键词匹配（含"CT""病理""彩超"等）
3. 表格结构/模式匹配（含"项目-结果-参考范围"三列表格 → 检验报告）
```

Fallback: `report_type: "unknown"`, 提示用户确认。

## 异常标记规则

```
value > refHigh  → flag: "high"        → displayFlag: "↑"
value < refLow   → flag: "low"         → displayFlag: "↓"
value > critHigh → flag: "criticalHigh" → displayFlag: "↑↑"
value < critLow  → flag: "criticalLow"  → displayFlag: "↓↓"
缺参考范围       → flag: "abnormal"    → displayFlag: ""
```

## 危急值阈值（自动标记 criticalHigh / criticalLow）

| 项目 | 危急低值 | 危急高值 |
|------|---------|---------|
| WBC (×10⁹/L) | 1.0 | 30 |
| PLT (×10⁹/L) | 20 | 1000 |
| Hb (g/L) | 50 | 200 |
| K⁺ (mmol/L) | 2.5 | 6.5 |
| Na⁺ (mmol/L) | 120 | 160 |
| Glu (mmol/L) | 2.2 | 25 |
| cTnI (ng/mL) | — | 0.5 |
| D-Dimer (mg/L FEU) | — | 5 |

## CT 病灶 flag 规则

| flag | 触发条件 |
|------|---------|
| `normal` | 结论为"未见异常""阴性" |
| `abnormal` | 描述非空，无前次对比 |
| `new` | "新出现""新发" |
| `enlarged` | "增大""较前增大""size increase" |
| `reduced` | "缩小""减轻""好转""较前减小" |

## 出院记录 mapping 速查

| OCR 字段 | Schema 字段 |
|----------|------------|
| 入院日期 | admissionDate |
| 出院日期 | dischargeDate |
| 入院诊断 | admittingDiagnosis |
| 出院诊断 | dischargeDiagnosis |
| 主诉 | chiefComplaint |
| 现病史 | presentIllness |
| 既往史 | pastHistory |
| 诊疗经过 | → dailyProgress[] (按时间拆分) |
| 出院情况 | dischargeStatus |
| 出院医嘱 | followUpPlan.instructions |
| 出院带药 | dischargeMedications[] |
| 主治医师 | attendingPhysician |

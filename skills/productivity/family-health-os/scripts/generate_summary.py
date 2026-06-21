#!/usr/bin/env python3
"""
Family Health OS — Summary Generator

合成层：从原始数据合成4种结构化叙事摘要。
位于 build_timeline.py（事件展示层）之上。

用法:
  python3 generate_summary.py <patientId> --type <type>

类型:
  medical-history   病史摘要
  hospitalization   住院总结
  consultation      会诊摘要
  follow-up         复诊摘要

示例:
  python3 generate_summary.py <patientId> --type medical-history
  python3 generate_summary.py <patientId> --type hospitalization
  python3 generate_summary.py <patientId> --type consultation --hospitalization <hospId>
  python3 generate_summary.py <patientId> --type follow-up --date 2026-07-01
"""

import json
import os
import sys
from datetime import datetime, date
from collections import defaultdict
from typing import Any, Optional

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "memory", "data")
SCRIPT_DIR = os.path.dirname(__file__)

# ============================================================
# 工具函数
# ============================================================

def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_patient(patient_id: str, data_dir: str) -> Optional[dict]:
    patients = load_json(os.path.join(data_dir, "patients.json"))
    if not patients:
        return None
    data = patients if isinstance(patients, list) else patients.get("patients", [])
    for p in data:
        if p.get("id") == patient_id:
            return p
    return None


def list_patients(data_dir: str) -> list[dict]:
    patients = load_json(os.path.join(data_dir, "patients.json"))
    if not patients:
        return []
    return patients if isinstance(patients, list) else patients.get("patients", [])


def filter_by_patient(data: Any, patient_id: str) -> list[dict]:
    if not data:
        return []
    records = data if isinstance(data, list) else list(data.values())[0] if isinstance(data, dict) else []
    return [r for r in records if isinstance(r, dict) and r.get("patientId") == patient_id]


def load_or_build_timeline(patient_id: str, data_dir: str) -> dict:
    """加载已聚合的 timeline，不存在则自动构建"""
    timeline_path = os.path.join(data_dir, "timeline.json")
    timeline = load_json(timeline_path)
    if timeline:
        if isinstance(timeline, list):
            for tl in timeline:
                if tl.get("patientId") == patient_id:
                    return tl
        elif isinstance(timeline, dict):
            if timeline.get("patientId") == patient_id:
                return timeline
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "aggregate_timeline.py"),
         patient_id, "--data-dir", data_dir],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"聚合失败: {result.stderr}")
    try:
        output = json.loads(result.stdout)
        return output.get("timeline", output)
    except json.JSONDecodeError:
        raise RuntimeError(f"聚合解析失败")


# ============================================================
# 映射表
# ============================================================

GENDER_LABEL = {"male": "男", "female": "女", "other": "其他"}

HOSPITAL_LEVEL = {
    "tertiary": "三级医院", "secondary": "二级医院",
    "primary": "一级医院", "clinic": "诊所", "other": "其他",
}

ADMISSION_TYPE = {
    "emergency": "急诊", "elective": "择期", "transfer": "转院", "other": "其他",
}

DISCHARGE_STATUS = {
    "cured": "痊愈", "improved": "好转", "unchanged": "未愈",
    "deteriorated": "恶化", "transferred": "转院", "died": "死亡",
    "againstAdvice": "自动出院",
}

SEVERITY_LABEL = {"mild": "轻度", "moderate": "中度", "severe": "重度", "critical": "危急"}

ALLERGY_SEVERITY = {
    "mild": "轻度", "moderate": "中度", "severe": "重度", "anaphylaxis": "过敏性休克",
}

DISEASE_STATUS = {
    "active": "活跃期", "remission": "缓解期", "controlled": "控制中",
    "resolved": "已愈", "recovered": "已康复", "chronic": "慢性",
}

EVENT_TYPE_LABELS = {
    "admission": "📋 入院", "discharge": "📋 出院",
    "surgery": "🔪 手术", "exam": "🔬 检查",
    "new_exam": "🔬 新开检查", "exam_result": "🔬 检查结果",
    "medicationStart": "💊 开始用药", "medicationStop": "💊 停药",
    "medicationChange": "💊 调整用药",
    "diagnosis": "🏥 确诊", "diagnosisChange": "🏥 诊断变更",
    "consultation": "👨‍⚕️ 会诊",
    "round": "🏥 查房", "doctor_round": "👨‍⚕️ 主任查房",
    "vaccination": "💉 疫苗接种", "allergyReaction": "🚨 过敏反应",
    "emergency": "🚨 紧急事件", "followUp": "📊 随访",
    "labResult": "🔬 检验结果", "imaging": "🔬 影像检查",
    "pathology": "🔬 病理结果", "procedure": "🔪 操作",
    "transfer": "📋 转科", "symptom": "📊 症状",
    "symptom_change": "📊 症状变化", "vitalSigns": "📊 生命体征",
    "healthCheckup": "💉 体检", "note": "📝 病程记录", "other": "📌 其他",
}


def age_from_birth(birth_date: str) -> int:
    if not birth_date:
        return 0
    try:
        bd = datetime.strptime(birth_date[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except ValueError:
        return 0


def render_allergies(allergies: list) -> str:
    if not allergies:
        return "无已知过敏"
    parts = []
    for a in allergies:
        sev = ALLERGY_SEVERITY.get(a.get("severity", ""), a.get("severity", ""))
        rxn = f" ({a['reaction']})" if a.get("reaction") else ""
        parts.append(f"{a['allergen']}({sev}{rxn})")
    return "；".join(parts)


def fmt_flag(flag: str) -> str:
    return {"high": "↑", "low": "↓", "criticalHigh": "↑↑",
            "criticalLow": "↓↓", "abnormal": "⚠", "normal": ""}.get(flag, "")


# ============================================================
# 病史摘要
# ============================================================

def generate_medical_history(patient: dict, diseases: list, exams: list,
                              meds: list, hospitals: list, timeline: dict) -> str:
    lines = []
    name = patient.get("name", "?")
    gender = GENDER_LABEL.get(patient.get("gender", ""), patient.get("gender", ""))
    age = age_from_birth(patient.get("birthDate", ""))
    blood = patient.get("bloodType", "未记录")
    allergies = render_allergies(patient.get("allergies", []))

    lines.append(f"# 🏥 病史摘要 — {name}")
    lines.append("")
    lines.append("## 👤 基本信息")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 姓名 | {name} |")
    lines.append(f"| 性别 | {gender} |")
    lines.append(f"| 年龄 | {age}岁 |")
    lines.append(f"| 血型 | {blood} |")
    lines.append(f"| 过敏史 | {allergies} |")
    lines.append("")

    # 活跃疾病
    active_d = [d for d in diseases if d.get("status") in ("active", "chronic", "controlled")]
    other_d = [d for d in diseases if d not in active_d]

    lines.append("## 🩺 现病史 — 当前疾病概况")
    if active_d:
        lines.append("### 活跃疾病")
        lines.append("| 疾病 | ICD | 确诊日期 | 状态 | 严重度 |")
        lines.append("|------|-----|---------|------|--------|")
        for d in active_d:
            status = DISEASE_STATUS.get(d.get("status", ""), d.get("status", ""))
            sev = SEVERITY_LABEL.get(d.get("severity", ""), d.get("severity", ""))
            lines.append(f"| {d.get('diseaseName', '')} | {d.get('icdCode', '')} | "
                        f"{d.get('diagnosedDate', '')[:10]} | {status} | {sev} |")
        lines.append("")

    # 当前用药
    ongoing = [m for m in meds if m.get("isOngoing", True) and not m.get("endDate")]
    if ongoing:
        lines.append("### 当前用药")
        lines.append("| 药品 | 剂量 | 频率 | 途径 | 用途 | 起始 |")
        lines.append("|------|------|------|------|------|------|")
        for m in ongoing:
            dose = m.get("dosage", {})
            dose_str = f"{dose.get('amount', '')}{dose.get('unit', '')}" if dose.get("amount") else ""
            freq = m.get("frequency", {})
            freq_str = f"每日{freq.get('timesPerDay', '')}次" if freq.get("timesPerDay") else ""
            route = m.get("route", "")
            purpose = m.get("purpose", "")
            start = m.get("startDate", "")[:10]
            lines.append(f"| {m.get('medicationName', '')} | {dose_str} | {freq_str} | "
                        f"{route} | {purpose} | {start} |")
        lines.append("")

    lines.append("---")
    lines.append("## 📋 既往史")

    if other_d:
        lines.append("### 既往疾病")
        lines.append("| 疾病 | ICD | 确诊日期 | 状态 |")
        lines.append("|------|-----|---------|------|")
        for d in other_d:
            status = DISEASE_STATUS.get(d.get("status", ""), d.get("status", ""))
            lines.append(f"| {d.get('diseaseName', '')} | {d.get('icdCode', '')} | "
                        f"{d.get('diagnosedDate', '')[:10]} | {status} |")
        lines.append("")

    # 手术史
    surgeries = []
    for h in hospitals:
        for s in h.get("surgeries", []):
            surgeries.append((s, h))
    if surgeries:
        lines.append("### 手术史")
        surgeries.sort(key=lambda x: x[0].get("surgeryDate", ""))
        for s, h in surgeries:
            inst = h.get("hospital", {}).get("name", "")
            lines.append(f"- **{s['surgeryName']}** — {s.get('surgeon', '')} @ {inst} ({s.get('surgeryDate', '')[:10]})")
        lines.append("")

    # 住院史
    if hospitals:
        lines.append("### 住院史")
        lines.append("| 时间 | 科室 | 入院诊断 | 天数 |")
        lines.append("|------|------|---------|------|")
        for h in sorted(hospitals, key=lambda x: x.get("admissionDate", "")):
            adm = h.get("admissionDate", "")[:10]
            dis = h.get("dischargeDate", "")[:10] if h.get("dischargeDate") else "在院"
            lines.append(f"| {adm} ~ {dis} | {h.get('department', '')} | "
                        f"{h.get('admittingDiagnosis', '')[:30]} | {h.get('totalDays', '?')}天 |")
        lines.append("")

    # 家族病史
    fh = patient.get("familyHistory", [])
    if fh:
        lines.append("### 家族病史")
        lines.append("| 疾病 | 关系 | 备注 |")
        lines.append("|------|------|------|")
        for f in fh:
            lines.append(f"| {f.get('disease', '')} | {f.get('relationship', '')} | {f.get('note', '')} |")
        lines.append("")

    # 近期检查
    recent = sorted([e for e in exams if e.get("examDate")],
                    key=lambda e: e["examDate"], reverse=True)[:5]
    if recent:
        lines.append("## 🔬 近期关键检查")
        lines.append("| 日期 | 项目 | 异常项 | 结论 |")
        lines.append("|------|------|--------|------|")
        for ex in recent:
            abnormal = [i for i in ex.get("items", [])
                        if i.get("flag") not in ("normal", None)]
            if abnormal:
                abnormal_str = "; ".join(
                    f"{i.get('itemName', i.get('name', '?'))} {i.get('value', '')}{fmt_flag(i.get('flag', ''))}"
                    for i in abnormal[:3]
                )
            else:
                abnormal_str = "—"
            conclusion = (ex.get("conclusion", "") or "")[:30]
            lines.append(f"| {ex.get('examDate', '')[:10]} | {ex.get('examName', '')} | "
                        f"{abnormal_str} | {conclusion} |")
        lines.append("")

    # 关键事件
    events = timeline.get("events", [])
    key_events = [e for e in events if e.get("isKeyEvent")]
    if key_events:
        lines.append("## ⭐ 关键事件时间轴摘要")
        for e in key_events[:15]:
            lbl = EVENT_TYPE_LABELS.get(e.get("eventType", ""), e.get("eventType", ""))
            lines.append(f"- **{e['date'][:10]}** {lbl} {e.get('title', '')}")
        lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*数据来源: Family Health OS*")
    return "\n".join(lines)


# ============================================================
# 住院总结
# ============================================================

def generate_hospitalization_summary(patient: dict, hospitals: list,
                                      exams: list, meds: list,
                                      timeline: dict, target_id: str = None) -> str:
    if not hospitals:
        return "# 🏥 住院总结\n\n该患者无住院记录。\n"

    # 选取目标住院
    if target_id:
        hosp = next((h for h in hospitals if h["id"] == target_id), None)
        if not hosp:
            return f"住院记录 {target_id} 不存在。"
    else:
        hosp = max(hospitals, key=lambda h: h.get("admissionDate", ""))

    lines = []
    name = patient.get("name", "?")
    lines.append(f"# 🏥 住院总结 — {name}")
    lines.append("")

    # 基本信息
    inst = hosp.get("hospital", {}).get("name", "")
    level = HOSPITAL_LEVEL.get(hosp.get("hospital", {}).get("level", ""), "")
    adm = hosp.get("admissionDate", "")[:10]
    dis = hosp.get("dischargeDate", "")[:10] if hosp.get("dischargeDate") else "在院中"
    total = hosp.get("totalDays", "?")

    lines.append("## 📋 基本信息")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 医院 | {inst} ({level}) |")
    lines.append(f"| 科室 | {hosp.get('department', '')} |")
    lines.append(f"| 床位 | {hosp.get('ward', '')} |")
    lines.append(f"| 入院类型 | {ADMISSION_TYPE.get(hosp.get('admissionType', ''), '')} |")
    lines.append(f"| 主治医师 | {hosp.get('attendingPhysician', '')} |")
    lines.append(f"| 入院日期 | {adm} |")
    lines.append(f"| 出院日期 | {dis} |")
    lines.append(f"| 住院天数 | {total}天 |")
    lines.append("")

    # 诊断
    lines.append("## 🩺 诊断")
    lines.append("| 类型 | 诊断 |")
    lines.append("|------|------|")
    lines.append(f"| 入院诊断 | {hosp.get('admittingDiagnosis', '')} |")
    lines.append(f"| 出院诊断 | {hosp.get('dischargeDiagnosis', '')} |")
    lines.append(f"| 出院状态 | {DISCHARGE_STATUS.get(hosp.get('dischargeStatus', ''), '')} |")
    lines.append("")

    # 入院情况
    lines.append("## 📝 入院情况")
    if hosp.get("chiefComplaint"):
        lines.append(f"**主诉：** {hosp['chiefComplaint']}")
    if hosp.get("presentIllness"):
        lines.append(f"**现病史：** {hosp['presentIllness']}")
    if hosp.get("pastHistory"):
        lines.append(f"**既往史：** {hosp['pastHistory']}")
    vs = hosp.get("vitalSignsOnAdmission", {})
    if vs:
        t = f"{vs.get('temperature', '')}℃" if vs.get('temperature') else ""
        hr = f"{vs.get('heartRate', '')}次/分" if vs.get('heartRate') else ""
        rr = f"{vs.get('respiratoryRate', '')}次/分" if vs.get('respiratoryRate') else ""
        bp = f"{vs.get('bloodPressureSystolic', '')}/{vs.get('bloodPressureDiastolic', '')}mmHg" if vs.get('bloodPressureSystolic') else ""
        spo2 = f"{vs.get('oxygenSaturation', '')}%" if vs.get('oxygenSaturation') else ""
        parts = " | ".join(p for p in [t, hr, rr, bp, spo2] if p)
        if parts:
            lines.append(f"**入院生命体征：** {parts}")
    lines.append("")

    # 住院经过
    progress = hosp.get("dailyProgress", [])
    if progress:
        lines.append("## 📅 住院经过")
        lines.append("| 日期 | 类型 | 内容 | 医生 |")
        lines.append("|------|------|------|------|")
        type_labels = {
            "dailyProgress": "📋 日常病程", "roundNote": "👨‍⚕️ 查房记录",
            "consultationNote": "👨‍⚕️ 会诊记录", "criticalNote": "🚨 危急记录",
            "preOpNote": "🔪 术前记录", "postOpNote": "🔪 术后记录",
            "transferNote": "📋 转科记录",
        }
        for p in progress:
            lbl = type_labels.get(p.get("type", ""), "📝 " + p.get("type", ""))
            content = (p.get("content", "") or "")[:50]
            doc = p.get("doctor", "")
            lines.append(f"| {p.get('date', '')} | {lbl} | {content} | {doc} |")
        lines.append("")

    # 手术
    surgeries = hosp.get("surgeries", [])
    if surgeries:
        lines.append("## 🔪 手术记录")
        for i, s in enumerate(surgeries, 1):
            lines.append(f"### 手术 #{i}")
            lines.append(f"**名称：** {s.get('surgeryName', '')}")
            lines.append(f"**日期：** {s.get('surgeryDate', '')[:16]}")
            lines.append(f"**主刀：** {s.get('surgeon', '')}  **助手：** {s.get('assistant', '')}")
            lines.append(f"**麻醉：** {s.get('anesthesiaType', '')} ({s.get('anesthesiologist', '')})")
            if s.get("preOpDiagnosis"):
                lines.append(f"**术前诊断：** {s['preOpDiagnosis']}")
            if s.get("postOpDiagnosis"):
                lines.append(f"**术后诊断：** {s['postOpDiagnosis']}")
            if s.get("findings"):
                lines.append(f"**术中发现：** {s['findings']}")
            if s.get("bloodLoss"):
                lines.append(f"**出血量：** {s['bloodLoss']}")
            lines.append("")

    # 会诊
    consultations = hosp.get("consultations", [])
    if consultations:
        lines.append("## 👨‍⚕️ 会诊记录")
        for c in consultations:
            lines.append(f"- **{c.get('consultingDepartment', '')}** — {c.get('consultingDoctor', '')}")
            if c.get("reason"):
                lines.append(f"  原因：{c['reason'][:80]}")
            if c.get("opinion"):
                lines.append(f"  意见：{c['opinion'][:100]}")
            if c.get("recommendations"):
                lines.append(f"  建议：{c['recommendations'][:80]}")
        lines.append("")

    # 住院期间检查
    hosp_id = hosp["id"]
    hosp_exams = [e for e in exams if e.get("relatedHospitalizationId") == hosp_id]
    if not hosp_exams:
        # 通过时间范围匹配
        try:
            adm_dt = datetime.strptime(adm, "%Y-%m-%d")
            dis_dt = datetime.strptime(dis, "%Y-%m-%d") if dis != "在院中" else datetime.now()
            hosp_exams = [e for e in exams if e.get("examDate") and
                          adm_dt <= datetime.strptime(e["examDate"][:10], "%Y-%m-%d") <= dis_dt]
        except (ValueError, TypeError):
            pass

    if hosp_exams:
        lines.append("## 🔬 住院期间检查")
        for ex in sorted(hosp_exams, key=lambda e: e.get("examDate", "")):
            abnormal = [i for i in ex.get("items", [])
                        if i.get("flag") not in ("normal", None)]
            flags = " ".join(fmt_flag(i.get("flag", "")) for i in abnormal) if abnormal else ""
            lines.append(f"- **{ex.get('examDate', '')[:10]}** {ex.get('examName', '')} "
                        f"{'⚠️ ' + flags if flags else '✅'}")
            if abnormal:
                for i in abnormal[:3]:
                    lines.append(f"  - {i['name']}: {i.get('value', '')}{i.get('unit', '')}"
                                f"{fmt_flag(i.get('flag', ''))}")
        lines.append("")

    # 出院小结
    if hosp.get("dischargeSummary"):
        lines.append("## 📋 出院小结")
        lines.append(hosp["dischargeSummary"])
        lines.append("")

    # 出院带药
    dm = hosp.get("dischargeMedications", [])
    if dm:
        lines.append("## 💊 出院带药")
        lines.append("| 药品 | 剂量 | 频率 | 疗程 |")
        lines.append("|------|------|------|------|")
        for m in dm:
            lines.append(f"| {m.get('medicationName', '')} | {m.get('dosage', '')} | "
                        f"{m.get('frequency', '')} | {m.get('duration', '')} |")
        lines.append("")

    # 随访
    fup = hosp.get("followUpPlan", {})
    if fup:
        lines.append("## 📊 随访计划")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        if fup.get("followUpDate"):
            lines.append(f"| 复诊日期 | {fup['followUpDate']} |")
        if fup.get("followUpDepartment"):
            lines.append(f"| 复诊科室 | {fup['followUpDepartment']} |")
        if fup.get("followUpDoctor"):
            lines.append(f"| 复诊医生 | {fup['followUpDoctor']} |")
        if fup.get("instructions"):
            lines.append(f"| 医嘱 | {fup['instructions']} |")
        if fup.get("dietaryAdvice"):
            lines.append(f"| 饮食建议 | {fup['dietaryAdvice']} |")
        if fup.get("activityRestriction"):
            lines.append(f"| 活动限制 | {fup['activityRestriction']} |")
        if fup.get("returnIf"):
            lines.append(f"| 需复诊指征 | {fup['returnIf']} |")
        lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*数据来源: Family Health OS*")
    return "\n".join(lines)


# ============================================================
# 会诊摘要
# ============================================================

def generate_consultation_summary(patient: dict, hospitals: list, timeline: dict) -> str:
    lines = []
    name = patient.get("name", "?")
    lines.append(f"# 👨‍⚕️ 专家会诊摘要 — {name}")
    lines.append("")

    # 从住院档案中收集所有会诊
    all_consults = []
    for h in hospitals:
        for c in h.get("consultations", []):
            all_consults.append({
                **c,
                "_hospital": h.get("hospital", {}).get("name", ""),
                "_department": h.get("department", ""),
                "_hosp_id": h["id"],
            })

    # 从 timeline 中收集会诊事件
    events = timeline.get("events", [])
    cons_events = [e for e in events if e.get("eventType") == "consultation"]

    if not all_consults and not cons_events:
        lines.append("无会诊记录。")
        lines.append("")
        lines.append("---")
        lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("*数据来源: Family Health OS*")
        return "\n".join(lines)

    lines.append("## 🤝 会诊汇总")

    # 会诊详情
    if all_consults:
        for i, c in enumerate(all_consults, 1):
            lines.append(f"---")
            lines.append(f"### 🤝 会诊 #{i} — {c.get('consultingDepartment', '')}")
            lines.append(f"| 项目 | 内容 |")
            lines.append(f"|------|------|")
            lines.append(f"| ⏰ 会诊日期 | {c.get('date', '')} |")
            lines.append(f"| 👨‍⚕️ 会诊医生 | {c.get('consultingDoctor', '')} |")
            lines.append(f"| 🏥 医院 | {c.get('_hospital', '')} |")
            lines.append("")
            if c.get("reason"):
                lines.append(f"**📝 会诊原因**")
                lines.append(f"{c['reason']}")
                lines.append("")
            if c.get("opinion"):
                lines.append(f"**💡 会诊意见**")
                lines.append(f"{c['opinion']}")
                lines.append("")
            if c.get("recommendations"):
                lines.append(f"**📋 建议方案**")
                lines.append(f"{c['recommendations']}")
                lines.append("")

    # 会诊事件
    if cons_events and not all_consults:
        for e in cons_events:
            lines.append(f"### {e.get('date', '')[:10]} {e.get('title', '')}")
            if e.get("sourceDoctor"):
                lines.append(f"- **医生：** {e['sourceDoctor']}")
            if e.get("description"):
                lines.append(f"- **内容：** {e['description'][:200]}")
            if e.get("sourceInstitution"):
                lines.append(f"- **来源：** {e['sourceInstitution']}")
            lines.append("")

    # 统计
    dept_count = defaultdict(int)
    doc_count = defaultdict(int)
    for c in all_consults:
        if c.get("consultingDepartment"):
            dept_count[c["consultingDepartment"]] += 1
        if c.get("consultingDoctor"):
            doc_count[c["consultingDoctor"]] += 1

    if dept_count or doc_count:
        lines.append("## 📊 会诊统计")
        if dept_count:
            lines.append("| 科室 | 次数 |")
            lines.append("|------|------|")
            for dept, cnt in sorted(dept_count.items(), key=lambda x: -x[1]):
                lines.append(f"| {dept} | {cnt} |")
            lines.append("")
        if doc_count:
            lines.append("| 医生 | 次数 |")
            lines.append("|------|------|")
            for doc, cnt in sorted(doc_count.items(), key=lambda x: -x[1]):
                lines.append(f"| {doc} | {cnt} |")
            lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*数据来源: Family Health OS*")
    return "\n".join(lines)


# ============================================================
# 复诊摘要
# ============================================================

def generate_followup_summary(patient: dict, diseases: list, exams: list,
                               meds: list, timeline: dict, tasks: list,
                               target_date: str = None) -> str:
    lines = []
    name = patient.get("name", "?")
    gender = GENDER_LABEL.get(patient.get("gender", ""), patient.get("gender", ""))
    age = age_from_birth(patient.get("birthDate", ""))
    fup_date = target_date or datetime.now().strftime("%Y-%m-%d")

    lines.append(f"# 📊 复诊摘要 — {name}")
    lines.append("")

    events = timeline.get("events", [])

    # 上次复诊日期
    last_fup = None
    followups = [e for e in events if e.get("eventType") == "followUp"]
    if followups:
        last_fup = followups[-1]["date"][:10]
    else:
        discharges = [e for e in events if e.get("eventType") == "discharge"]
        if discharges:
            last_fup = discharges[-1]["date"][:10]

    lines.append("## 👤 患者信息")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 姓名 | {name} | {age}岁 {gender} |")
    lines.append(f"| 复诊日期 | {fup_date} |")
    if last_fup:
        try:
            days = (datetime.strptime(fup_date, "%Y-%m-%d") - datetime.strptime(last_fup, "%Y-%m-%d")).days
            lines.append(f"| 上次就诊 | {last_fup} |")
            lines.append(f"| 距上次复诊 | {days}天 |")
        except ValueError:
            pass
    lines.append("")

    # 上次至今新事件
    lines.append("## 🔄 上次复诊至今的变化")
    if last_fup:
        new_events = [e for e in events if e["date"][:10] >= last_fup and e["date"][:10] < fup_date]
    else:
        new_events = events[-20:] if len(events) > 20 else events

    if new_events:
        lines.append(f"### 新事件（{len(new_events)}件）")
        for e in new_events[:10]:
            lbl = EVENT_TYPE_LABELS.get(e.get("eventType", ""), e.get("eventType", ""))
            lines.append(f"- **{e['date'][:10]}** {lbl} {e.get('title', '')}")
        if len(new_events) > 10:
            lines.append(f"  ...及其他 {len(new_events) - 10} 件")
        lines.append("")

    # 用药变更
    if last_fup:
        med_changes = [e for e in new_events
                       if e.get("eventType") in ("medicationStart", "medicationStop", "medicationChange")]
        if med_changes:
            lines.append("### 用药变更")
            for e in med_changes:
                lbl = EVENT_TYPE_LABELS.get(e.get("eventType", ""), "")
                lines.append(f"- **{e['date'][:10]}** {lbl} {e.get('title', '')}")
            lines.append("")

    # 最新检查
    recent_exams = sorted([e for e in exams if e.get("examDate")],
                          key=lambda e: e["examDate"], reverse=True)[:5]
    if recent_exams:
        lines.append("### 最新检查结果")
        for ex in recent_exams:
            abnormal = [i for i in ex.get("items", [])
                        if i.get("flag") not in ("normal", None)]
            flags = " ".join(fmt_flag(i.get("flag", "")) for i in abnormal) if abnormal else ""
            lines.append(f"- **{ex.get('examDate', '')[:10]}** {ex.get('examName', '')} "
                        f"{'⚠️ ' + flags if flags else '✅'}")
            if abnormal:
                for i in abnormal[:3]:
                    lines.append(f"  - {i['name']}: {i.get('value', '')}{i.get('unit', '')}"
                                f"{fmt_flag(i.get('flag', ''))} {i.get('referenceRange', '')}")
        lines.append("")

    # 疾病控制目标
    if diseases:
        lines.append("## 🎯 疾病控制目标")
        has_target = False
        for d in diseases:
            tv = d.get("targetValues", {})
            if not tv:
                continue
            has_target = True
            for key, label in [("hba1cTarget", "HbA1c"), ("fastingGlucoseTarget", "空腹血糖"),
                               ("ldlTarget", "LDL-C"), ("systolicTarget", "收缩压"),
                               ("diastolicTarget", "舒张压")]:
                target_val = tv.get(key)
                if not target_val:
                    continue
                # 从报告中找最新相关值
                latest_val = "—"
                latest_date = ""
                for ex in recent_exams:
                    for item in ex.get("items", []):
                        if label in item.get("name", "") or key.replace("Target", "").lower() in item.get("name", "").lower():
                            latest_val = f"{item.get('value', '')}{item.get('unit', '')}{fmt_flag(item.get('flag', ''))}"
                            latest_date = ex.get("examDate", "")[:10]
                            break
                achieved = "✅" if "↑" not in str(latest_val) else "❌"
                if latest_val != "—":
                    lines.append(f"| {d.get('diseaseName', '')} | {label} | < {target_val} | {latest_val} ({latest_date}) | {achieved} |")
        if has_target:
            # Add table header if we have targets
            lines.insert(lines.index("## 🎯 疾病控制目标") + 1,
                        "| 疾病 | 指标 | 目标 | 最新值 | 达标 |")
            lines.insert(lines.index("## 🎯 疾病控制目标") + 2,
                        "|------|------|------|--------|------|")
        lines.append("")

    # 待办
    pending = [t for t in tasks if t.get("status") in ("pending", "overdue")]
    if pending:
        lines.append("## ⏳ 待办事项")
        for t in pending:
            status = "⏰ 逾期" if t.get("status") == "overdue" else "📅 待办"
            pri = t.get("priority", "")
            pri_mark = {"high": "🔴", "medium": "🟡", "low": "🟢", "urgent": "🚨"}.get(pri, "")
            lines.append(f"- {status} {pri_mark} **{t.get('title', '')}** (截止 {t.get('dueDate', '')[:10]})")
        lines.append("")

    # 讨论要点
    points = []
    # 未达标控制目标
    for d in diseases:
        tv = d.get("targetValues", {})
        if tv.get("hba1cTarget"):
            for ex in recent_exams:
                for item in ex.get("items", []):
                    if "糖化" in item.get("name", "") or "HbA1c" in item.get("name", ""):
                        try:
                            val = float(str(item.get("value", "0")).replace(">", "").replace("<", ""))
                            if val > tv["hba1cTarget"]:
                                points.append(f"• **{d['diseaseName']}**：HbA1c {val}% 未达标"
                                            f"（目标 < {tv['hba1cTarget']}%，检查日期 {ex.get('examDate', '')[:10]}）")
                        except ValueError:
                            pass
    # 逾期任务
    for t in pending:
        if t.get("status") == "overdue":
            points.append(f"• **待办提醒**：{t['title']}（原定{t['dueDate'][:10]}，已逾期）")
    # 新异常检查
    for ex in recent_exams[:3]:
        abnormal = [i for i in ex.get("items", []) if i.get("flag") not in ("normal", None)]
        if abnormal:
            names = ", ".join(i["name"] for i in abnormal[:3])
            points.append(f"• **检查异常**：{ex.get('examName', '')}（{names}异常，{ex.get('examDate', '')[:10]}）")
    # 续药提醒
    for m in meds:
        rr = m.get("refillReminder", {})
        if rr and rr.get("enabled") and m.get("isOngoing", True):
            points.append(f"• **续药提醒**：{m.get('medicationName', '')}（{rr.get('daysBeforeRefill', '?')}天后需续药）")

    if points:
        lines.append("## ❓ 建议复诊讨论要点")
        for p in points:
            lines.append(p)
        lines.append("")

    # 当前用药
    ongoing = [m for m in meds if m.get("isOngoing", True) and not m.get("endDate")]
    if ongoing:
        lines.append("## 📋 当前用药清单")
        lines.append("| 药品 | 剂量 | 频率 | 用途 |")
        lines.append("|------|------|------|------|")
        for m in ongoing:
            dose = m.get("dosage", {})
            dose_str = f"{dose.get('amount', '')}{dose.get('unit', '')}" if dose.get("amount") else ""
            freq = m.get("frequency", {})
            freq_str = f"每日{freq.get('timesPerDay', '')}次" if freq.get("timesPerDay") else ""
            lines.append(f"| {m.get('medicationName', '')} | {dose_str} | {freq_str} | {m.get('purpose', '')} |")
        lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*数据来源: Family Health OS*")
    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================

SUMMARY_TYPES = {
    "medical-history": generate_medical_history,
    "hospitalization": generate_hospitalization_summary,
    "consultation": generate_consultation_summary,
    "follow-up": generate_followup_summary,
}

def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <patientId> --type <type>")
        print(f"类型: {', '.join(SUMMARY_TYPES.keys())}")
        sys.exit(1)

    patient_id = sys.argv[1]
    args = sys.argv[2:]

    kwargs = {"data_dir": SCHEMA_DIR}
    summary_type = "medical-history"
    target_hosp = None
    target_date = None
    output_file = None

    for i, arg in enumerate(args):
        if arg == "--type" and i + 1 < len(args):
            summary_type = args[i + 1]
        elif arg == "--hospitalization" and i + 1 < len(args):
            target_hosp = args[i + 1]
        elif arg == "--date" and i + 1 < len(args):
            target_date = args[i + 1]
        elif arg == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
        elif arg == "--data-dir" and i + 1 < len(args):
            kwargs["data_dir"] = args[i + 1]

    data_dir = kwargs["data_dir"]

    if summary_type not in SUMMARY_TYPES:
        print(f"未知摘要类型: {summary_type}")
        print(f"可选: {', '.join(SUMMARY_TYPES.keys())}")
        sys.exit(1)

    # 验证患者
    patient = find_patient(patient_id, data_dir)
    if not patient:
        available = list_patients(data_dir)
        err = f"患者 {patient_id} 不存在。"
        if available:
            err += "\n可用患者:\n" + "\n".join(
                f"  {p['id']}: {p.get('name', '?')}" for p in available)
        print(err)
        sys.exit(1)

    # 加载数据
    diseases = filter_by_patient(load_json(os.path.join(data_dir, "diseases.json")), patient_id)
    exams = filter_by_patient(load_json(os.path.join(data_dir, "exams.json")), patient_id)
    meds = filter_by_patient(load_json(os.path.join(data_dir, "medications.json")), patient_id)
    hospitals = filter_by_patient(load_json(os.path.join(data_dir, "hospitalizations.json")), patient_id)
    tasks = filter_by_patient(load_json(os.path.join(data_dir, "tasks.json")), patient_id)

    try:
        timeline = load_or_build_timeline(patient_id, data_dir)
    except RuntimeError as e:
        timeline = {"events": []}

    # 生成摘要
    if summary_type == "medical-history":
        result = generate_medical_history(patient, diseases, exams, meds, hospitals, timeline)
    elif summary_type == "hospitalization":
        result = generate_hospitalization_summary(patient, hospitals, exams, meds, timeline, target_hosp)
    elif summary_type == "consultation":
        result = generate_consultation_summary(patient, hospitals, timeline)
    elif summary_type == "follow-up":
        result = generate_followup_summary(patient, diseases, exams, meds, timeline, tasks, target_date)
    else:
        result = "未知类型"

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"✅ 摘要已写入 {output_file}")
    else:
        print(result)


if __name__ == "__main__":
    main()

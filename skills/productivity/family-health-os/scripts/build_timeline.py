#!/usr/bin/env python3
"""
Family Health OS — Timeline Builder

查询+渲染层：从聚合后的 timeline.json 按条件过滤并生成三种视图。
位于 aggregate_timeline.py（写入层）之上。

用法:
  python3 build_timeline.py <patientId> [options]

视图:
  --view full           病程时间轴（默认）
  --view hospitalization 住院时间轴
  --view consultation    会诊时间轴

过滤:
  --disease <id>        按疾病ID筛选
  --start <date>        起始日期 (YYYY-MM-DD)
  --end <date>          截止日期 (YYYY-MM-DD)

格式:
  --format markdown     Markdown 可读输出（默认）
  --format json         原始 JSON 输出
  --format text         纯文本摘要

示例:
  python3 build_timeline.py p-001
  python3 build_timeline.py p-001 --view hospitalization
  python3 build_timeline.py p-001 --view consultation --start 2025-01-01
  python3 build_timeline.py p-001 --disease d-001 --format json
"""

import json
import os
import sys
import subprocess
from datetime import datetime, date
from collections import defaultdict
from typing import Any, Optional

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "memory", "data")
SCRIPT_DIR = os.path.dirname(__file__)

# ============================================================
# 事件类型 → 标签 & 图标
# ============================================================

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

KEY_EVENT_TYPES = {
    "admission", "discharge", "surgery", "diagnosis",
    "diagnosisChange", "emergency", "transfer",
}

CONSULTATION_EVENT_TYPES = {"consultation", "doctor_round", "diagnosisChange"}

SEVERITY_PREFIX = {
    "critical": "🔴",
    "warning": "⚠️",
    "info": "",
    "normal": "",
}


def load_json(path: str) -> Optional[Any]:
    """加载 JSON 文件"""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_patient(patient_id: str, data_dir: str) -> Optional[dict]:
    """在 patients.json 中查找患者"""
    patients = load_json(os.path.join(data_dir, "patients.json"))
    if not patients:
        return None
    data = patients if isinstance(patients, list) else patients.get("patients", [])
    for p in data:
        if p.get("id") == patient_id:
            return p
    return None


def find_disease(disease_id: str, data_dir: str) -> Optional[dict]:
    """在 diseases.json 中查找疾病"""
    diseases = load_json(os.path.join(data_dir, "diseases.json"))
    if not diseases:
        return None
    data = diseases if isinstance(diseases, list) else diseases.get("diseases", [])
    for d in data:
        if d.get("id") == disease_id:
            return d
    return None


def list_patients(data_dir: str) -> list[dict]:
    """列出所有患者"""
    patients = load_json(os.path.join(data_dir, "patients.json"))
    if not patients:
        return []
    return patients if isinstance(patients, list) else patients.get("patients", [])


def list_diseases_for_patient(patient_id: str, data_dir: str) -> list[dict]:
    """列出某患者的所有疾病"""
    diseases = load_json(os.path.join(data_dir, "diseases.json"))
    if not diseases:
        return []
    data = diseases if isinstance(diseases, list) else diseases.get("diseases", [])
    return [d for d in data if d.get("patientId") == patient_id]


# ============================================================
# 时间轴加载
# ============================================================

def load_or_build_timeline(patient_id: str, data_dir: str) -> dict:
    """加载已聚合的 timeline，不存在则自动构建"""
    timeline_path = os.path.join(data_dir, "timeline.json")
    timeline = load_json(timeline_path)

    if timeline:
        # timeline.json 可能是单个对象或多患者数组
        if isinstance(timeline, list):
            for tl in timeline:
                if tl.get("patientId") == patient_id:
                    return tl
        elif isinstance(timeline, dict):
            if timeline.get("patientId") == patient_id:
                return timeline

    # 不存在 → 调用 aggregate_timeline.py
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
        raise RuntimeError(f"聚合输出解析失败: {result.stdout[:200]}")


# ============================================================
# 过滤引擎
# ============================================================

def filter_by_date(events: list[dict], start: str = None, end: str = None) -> list[dict]:
    """按时间范围过滤"""
    if not start and not end:
        return events
    filtered = []
    for ev in events:
        ev_date = ev["date"][:10]
        if start and ev_date < start:
            continue
        if end and ev_date > end:
            continue
        filtered.append(ev)
    return filtered


def build_disease_filter(disease_id: str, data_dir: str):
    """构建疾病过滤上下文"""
    disease = find_disease(disease_id, data_dir)
    if not disease:
        raise ValueError(f"疾病 {disease_id} 不存在")

    disease_name = disease.get("diseaseName", "")
    icd_code = disease.get("icdCode", "")

    # 收集关联的 hospitalizationIds
    related_hosp_ids = set()
    for ep in disease.get("episodes", []):
        if ep.get("hospitalizationId"):
            related_hosp_ids.add(ep["hospitalizationId"])

    # 收集关联的 examIds（通过 relatedDiseaseIds）
    exams = load_json(os.path.join(data_dir, "exams.json"))
    related_exam_ids = set()
    if exams:
        data = exams if isinstance(exams, list) else exams.get("exams", [])
        for ex in data:
            if disease_id in ex.get("relatedDiseaseIds", []):
                related_exam_ids.add(ex["id"])

    # 收集关联的 medicationIds
    meds = load_json(os.path.join(data_dir, "medications.json"))
    related_med_ids = set()
    if meds:
        data = meds if isinstance(meds, list) else meds.get("medications", [])
        for m in data:
            if disease_id in m.get("relatedDiseaseIds", []):
                related_med_ids.add(m["id"])

    def matches(ev: dict) -> bool:
        """判断事件是否与疾病相关"""
        # 直接来源是疾病记录
        if ev.get("sourceType") == "disease" and ev.get("sourceId") == disease_id:
            return True
        # 关联的检查
        if ev.get("sourceType") == "exam" and ev.get("sourceId") in related_exam_ids:
            return True
        # 关联的用药
        if ev.get("sourceType") == "medication" and ev.get("sourceId") in related_med_ids:
            return True
        # 关联的住院
        if ev.get("sourceType") == "hospitalization" and ev.get("sourceId") in related_hosp_ids:
            return True
        # 标签中包含疾病名或ICD编码
        if disease_name and disease_name in ev.get("tags", []):
            return True
        if icd_code and icd_code in ev.get("tags", []):
            return True
        # 事件标题或描述中包含疾病名
        if disease_name:
            title = ev.get("title", "")
            desc = ev.get("description", "")
            if disease_name in title or disease_name in desc:
                return True
        return False

    return disease, matches


def rebuild_monthly_groups(events: list[dict]) -> dict[str, list[str]]:
    """重建月份分组索引"""
    groups: dict[str, list[str]] = {}
    for ev in events:
        month = ev["date"][:7]
        groups.setdefault(month, []).append(ev["eventId"])
    return dict(sorted(groups.items()))


def compute_stats(events: list[dict]) -> dict:
    """计算事件统计"""
    stats = {
        "totalEvents": len(events),
        "byCategory": defaultdict(int),
        "byType": defaultdict(int),
        "bySeverity": defaultdict(int),
        "keyEvents": [],
    }
    for ev in events:
        stats["byCategory"][ev.get("category", "other")] += 1
        stats["byType"][ev.get("eventType", "other")] += 1
        stats["bySeverity"][ev.get("severity", "info")] += 1
        if ev.get("isKeyEvent"):
            stats["keyEvents"].append(ev)

    if events:
        stats["dateRange"] = {
            "earliest": events[0]["date"][:10],
            "latest": events[-1]["date"][:10],
        }
    return stats


# ============================================================
# 视图渲染器
# ============================================================

def render_full_view(patient: dict, events: list[dict], stats: dict) -> str:
    """渲染病程时间轴（Markdown）"""
    lines = []
    name = patient.get("name", "未知")
    dr = stats.get("dateRange", {})
    lines.append(f"# 🏥 {name} 病程时间轴")
    lines.append(f"📅 {dr.get('earliest', '—')} → {dr.get('latest', '—')} | 共 {stats['totalEvents']} 条事件")
    lines.append("")

    # 概览表
    lines.append("## 📊 概览")
    lines.append("| 分类 | 计数 |")
    lines.append("|------|------|")
    cat_order = ["clinical", "diagnostic", "medication", "surgical",
                 "administrative", "monitoring", "emergency", "preventive", "other"]
    cat_names = {
        "clinical": "🏥 临床", "diagnostic": "🔬 检查", "medication": "💊 用药",
        "surgical": "🔪 手术", "administrative": "📋 行政", "monitoring": "📊 监测",
        "emergency": "🚨 紧急", "preventive": "💉 预防", "other": "📌 其他",
    }
    for cat in cat_order:
        count = stats["byCategory"].get(cat, 0)
        if count > 0:
            lines.append(f"| {cat_names.get(cat, cat)} | {count} |")
    lines.append("")

    # 关键事件
    if stats["keyEvents"]:
        lines.append("## ⭐ 关键事件")
        for ev in stats["keyEvents"]:
            date_part = ev["date"][:10]
            lines.append(f"- **{date_part}** {ev['title']}")
        lines.append("")

    # 按月分组
    monthly = rebuild_monthly_groups(events)
    for month, ev_ids in monthly.items():
        year, mon = month.split("-")
        lines.append(f"---")
        lines.append(f"## 📅 {year}年{int(mon)}月")
        lines.append("")

        month_events = [e for e in events if e["date"][:7] == month]
        for ev in month_events:
            icon = CATEGORY_ICONS.get(ev.get("category", ""), "📌")
            label = EVENT_TYPE_LABELS.get(ev.get("eventType", ""), ev.get("eventType", ""))
            sev = SEVERITY_PREFIX.get(ev.get("severity", ""), "")

            title = ev.get("title", "")
            if ev.get("isKeyEvent"):
                title = f"**{title}**"

            source = f" — {ev.get('sourceDoctor', '')}" if ev.get("sourceDoctor") else ""
            inst = f" @ {ev.get('sourceInstitution', '')}" if ev.get("sourceInstitution") else ""

            date_part = ev["date"][:10]
            lines.append(f"{sev}{icon} **{date_part}** {label} {title}{source}{inst}")

            if ev.get("description"):
                desc = ev["description"][:100]
                lines.append(f"  > {desc}")

            if ev.get("affectedBodySite"):
                lines.append(f"  部位：{ev['affectedBodySite']}")

            # 异常标记
            meta = ev.get("metadata", {})
            if meta.get("flag") and meta["flag"] != "normal":
                lines.append(f"  ⚠️ {meta.get('value', '')} {meta.get('unit', '')} {meta['flag']}")

            lines.append("")

    return "\n".join(lines)


def render_hospitalization_view(patient: dict, events: list[dict], data_dir: str,
                                 target_hosp_id: str = None) -> str:
    """渲染住院时间轴（Markdown）"""
    lines = []
    name = patient.get("name", "未知")
    lines.append(f"# 🏥 {name} 住院时间轴")
    lines.append("")

    # 加载住院档案
    hospitals = load_json(os.path.join(data_dir, "hospitalizations.json"))
    if not hospitals:
        return "无住院记录"

    hosp_data = hospitals if isinstance(hospitals, list) else hospitals.get("hospitalizations", [])
    if target_hosp_id:
        hosp_data = [h for h in hosp_data if h["id"] == target_hosp_id]

    # 过滤出住院事件
    hosp_events = [e for e in events if e.get("sourceType") == "hospitalization"]

    for hosp in hosp_data:
        hid = hosp["id"]
        inst = hosp.get("hospital", {}).get("name", "")
        dept = hosp.get("department", "")
        adm_date = hosp.get("admissionDate", "")[:10]
        dis_date = hosp.get("dischargeDate", "")[:10] if hosp.get("dischargeDate") else "在院中"
        total = hosp.get("totalDays", "?")

        lines.append(f"---")
        lines.append(f"## 🏥 住院 — {dept} @ {inst}")
        lines.append(f"**入院诊断：** {hosp.get('admittingDiagnosis', '')}")
        if hosp.get("dischargeDiagnosis"):
            lines.append(f"**出院诊断：** {hosp['dischargeDiagnosis']}")
        lines.append(f"**主治医师：** {hosp.get('attendingPhysician', '')}")
        lines.append(f"**时间：** {adm_date} → {dis_date} ({total}天)")
        lines.append("")

        # 本住院的事件
        he = sorted(
            [e for e in hosp_events if e.get("sourceId") == hid],
            key=lambda e: e["date"]
        )

        # 按日期分组
        by_day: dict[str, list[dict]] = {}
        for ev in he:
            day = ev["date"][:10]
            by_day.setdefault(day, []).append(ev)

        # 计算天数偏移
        try:
            adm_dt = datetime.strptime(adm_date, "%Y-%m-%d").date()
        except ValueError:
            adm_dt = None

        for day_str in sorted(by_day.keys()):
            day_events = sorted(by_day[day_str], key=lambda e: e["date"])
            day_num = ""
            if adm_dt:
                try:
                    cur_dt = datetime.strptime(day_str, "%Y-%m-%d").date()
                    day_num = f"Day {(cur_dt - adm_dt).days + 1}"
                except ValueError:
                    pass

            lines.append(f"### {day_str} {'| ' + day_num if day_num else ''}")
            for ev in day_events:
                label = EVENT_TYPE_LABELS.get(ev.get("eventType", ""), ev.get("eventType", ""))
                sev = SEVERITY_PREFIX.get(ev.get("severity", ""), "")
                title = ev.get("title", "")
                if ev.get("isKeyEvent"):
                    title = f"**{title}**"
                lines.append(f"- {sev}{label} {title}")
                if ev.get("description"):
                    lines.append(f"  - {ev['description'][:80]}")
            lines.append("")

        # 手术
        if hosp.get("surgeries"):
            lines.append("### 🔪 手术记录")
            for surg in hosp["surgeries"]:
                lines.append(f"- **{surg['surgeryName']}** — {surg.get('surgeon', '')}")
                if surg.get("preOpDiagnosis"):
                    lines.append(f"  术前诊断：{surg['preOpDiagnosis']}")
                if surg.get("postOpDiagnosis"):
                    lines.append(f"  术后诊断：{surg['postOpDiagnosis']}")
            lines.append("")

        # 会诊
        if hosp.get("consultations"):
            lines.append("### 👨‍⚕️ 会诊记录")
            for cons in hosp["consultations"]:
                lines.append(f"- **{cons.get('consultingDepartment', '')}** — {cons.get('consultingDoctor', '')}")
                lines.append(f"  意见：{cons.get('opinion', '')[:100]}")
            lines.append("")

        # 出院
        if hosp.get("dischargeMedications"):
            lines.append("### 💊 出院带药")
            for med in hosp["dischargeMedications"]:
                lines.append(f"- {med.get('medicationName', '')} "
                            f"{med.get('dosage', '')} "
                            f"{med.get('frequency', '')} "
                            f"{med.get('duration', '')}")

        if hosp.get("followUpPlan", {}).get("followUpDate"):
            fup = hosp["followUpPlan"]
            lines.append(f"**📊 随访：** {fup.get('followUpDate', '')} @ {fup.get('followUpDepartment', '')}")
            if fup.get("instructions"):
                lines.append(f"  {fup['instructions'][:100]}")
        lines.append("")

        if target_hosp_id:
            break

    return "\n".join(lines)


def render_consultation_view(patient: dict, events: list[dict], data_dir: str) -> str:
    """渲染会诊时间轴（Markdown）"""
    lines = []
    name = patient.get("name", "未知")
    lines.append(f"# 👨‍⚕️ {name} 专家会诊时间轴")
    lines.append("")

    # 筛选会诊事件
    cons_events = [e for e in events if e.get("eventType") in CONSULTATION_EVENT_TYPES]

    if not cons_events:
        lines.append("无会诊记录")
        return "\n".join(lines)

    # 加载住院档案以获取会诊详情
    hospitals = load_json(os.path.join(data_dir, "hospitalizations.json"))
    hosp_by_id = {}
    if hospitals:
        data = hospitals if isinstance(hospitals, list) else hospitals.get("hospitalizations", [])
        for h in data:
            hosp_by_id[h["id"]] = h

    # 统计
    dept_count = defaultdict(int)
    doctor_count = defaultdict(int)
    enriched_events = []

    for ev in cons_events:
        detail = None
        # 从住院档案中查找完整会诊详情
        if ev.get("sourceType") == "hospitalization" and ev.get("sourceId") in hosp_by_id:
            hosp = hosp_by_id[ev["sourceId"]]
            for cons in hosp.get("consultations", []):
                if (cons.get("consultingDoctor") == ev.get("sourceDoctor") or
                        cons.get("consultingDepartment") in ev.get("title", "")):
                    detail = cons
                    break

        enriched = dict(ev)
        enriched["_detail"] = detail
        enriched_events.append(enriched)

        doctor = detail.get("consultingDoctor") if detail else ev.get("sourceDoctor", "")
        dept = detail.get("consultingDepartment") if detail else ""

        if doctor:
            doctor_count[doctor] += 1
        if dept:
            dept_count[dept] += 1

    # 输出
    for ev in enriched_events:
        label = EVENT_TYPE_LABELS.get(ev.get("eventType", ""), ev.get("eventType", ""))
        date_part = ev["date"][:10]
        title = ev.get("title", "")
        sev = SEVERITY_PREFIX.get(ev.get("severity", ""), "")

        lines.append(f"### {sev}{date_part} {label} {title}")
        detail = ev.get("_detail")

        if detail:
            lines.append(f"- **申请科室：** {detail.get('consultingDepartment', '')}")
            if detail.get("consultingDoctor"):
                lines.append(f"- **会诊医生：** {detail['consultingDoctor']}")
            if detail.get("reason"):
                lines.append(f"- **会诊原因：** {detail['reason'][:100]}")
            if detail.get("opinion"):
                lines.append(f"- **会诊意见：** {detail['opinion'][:200]}")
            if detail.get("recommendations"):
                lines.append(f"- **推荐方案：** {detail['recommendations'][:100]}")
        else:
            if ev.get("sourceDoctor"):
                lines.append(f"- **医生：** {ev['sourceDoctor']}")
            if ev.get("description"):
                lines.append(f"- **内容：** {ev['description'][:150]}")

        if ev.get("sourceInstitution"):
            lines.append(f"- **来源：** {ev['sourceInstitution']}")
        lines.append("")

    # 统计
    lines.append("---")
    lines.append("## 📊 会诊统计")
    lines.append(f"**总会诊事件：** {len(cons_events)}")
    lines.append("")
    if dept_count:
        lines.append("### 按科室")
        for dept, cnt in sorted(dept_count.items(), key=lambda x: -x[1]):
            lines.append(f"- {dept}: {cnt}次")
        lines.append("")
    if doctor_count:
        lines.append("### 按医生")
        for doc, cnt in sorted(doctor_count.items(), key=lambda x: -x[1]):
            lines.append(f"- {doc}: {cnt}次")

    return "\n".join(lines)


# ============================================================
# 主函数
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <patientId> [options]")
        print(f"示例:")
        print(f"  {sys.argv[0]} <patientId>")
        print(f"  {sys.argv[0]} <patientId> --view hospitalization")
        print(f"  {sys.argv[0]} <patientId> --view consultation --start 2025-01-01")
        print(f"  {sys.argv[0]} <patientId> --disease <diseaseId> --format json")
        sys.exit(1)

    patient_id = sys.argv[1]

    # 解析参数
    args = sys.argv[2:]
    kwargs = {}
    for i, arg in enumerate(args):
        if arg == "--disease" and i + 1 < len(args):
            kwargs["disease_id"] = args[i + 1]
        elif arg == "--start" and i + 1 < len(args):
            kwargs["start_date"] = args[i + 1]
        elif arg == "--end" and i + 1 < len(args):
            kwargs["end_date"] = args[i + 1]
        elif arg == "--view" and i + 1 < len(args):
            kwargs["view"] = args[i + 1]
        elif arg == "--format" and i + 1 < len(args):
            kwargs["fmt"] = args[i + 1]
        elif arg == "--hospitalization" and i + 1 < len(args):
            kwargs["hosp_id"] = args[i + 1]
        elif arg == "--data-dir" and i + 1 < len(args):
            kwargs["data_dir"] = args[i + 1]

    data_dir = kwargs.get("data_dir", SCHEMA_DIR)
    disease_id = kwargs.get("disease_id")
    start_date = kwargs.get("start_date")
    end_date = kwargs.get("end_date")
    view = kwargs.get("view", "full")
    fmt = kwargs.get("fmt", "markdown")
    hosp_id = kwargs.get("hosp_id")

    # 验证患者
    patient = find_patient(patient_id, data_dir)
    if not patient:
        available = list_patients(data_dir)
        err = f"患者 {patient_id} 不存在。"
        if available:
            names = "\n".join(f"  {p['id']}: {p.get('name', '?')}" for p in available)
            err += f"\n可用患者:\n{names}"
        print(err)
        sys.exit(1)

    # 验证疾病（如果指定）
    disease = None
    disease_filter = None
    if disease_id:
        try:
            disease, disease_filter = build_disease_filter(disease_id, data_dir)
        except ValueError as e:
            available = list_diseases_for_patient(patient_id, data_dir)
            err = str(e)
            if available:
                names = "\n".join(f"  {d['id']}: {d.get('diseaseName', '?')}" for d in available)
                err += f"\n该患者疾病:\n{names}"
            print(err)
            sys.exit(1)

    # 加载时间轴
    try:
        timeline = load_or_build_timeline(patient_id, data_dir)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    events = timeline.get("events", [])

    # 疾病过滤
    if disease_filter:
        events = [e for e in events if disease_filter(e)]

    # 时间过滤
    events = filter_by_date(events, start_date, end_date)

    # 统计
    stats = compute_stats(events)

    # 渲染
    result = ""
    if view == "full":
        if disease:
            # 疾病视角
            result = f"# 🏥 {patient.get('name', '')} — {disease.get('diseaseName', '')} 病程\n"
            result += f"ICD编码: {disease.get('icdCode', '')} | "
            result += f"状态: {disease.get('status', '')}\n\n"
            result += render_full_view(patient, events, stats)
        else:
            result = render_full_view(patient, events, stats)
    elif view == "hospitalization":
        result = render_hospitalization_view(patient, events, data_dir, hosp_id)
    elif view == "consultation":
        result = render_consultation_view(patient, events, data_dir)
    else:
        print(f"未知视图: {view} (可选: full / hospitalization / consultation)")
        sys.exit(1)

    # 格式输出
    if fmt == "json":
        output = {
            "patient": patient,
            "view": view,
            "stats": dict(stats),
            "events": events,
            "rendered": result if fmt == "text" else None,
        }
        if disease:
            output["disease"] = disease
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif fmt == "markdown":
        print(result)
    elif fmt == "text":
        # 纯文本摘要
        dr = stats.get("dateRange", {})
        print(f"患者: {patient.get('name', '')}")
        print(f"视图: {view}")
        if disease:
            print(f"疾病: {disease.get('diseaseName', '')}")
        print(f"时间: {dr.get('earliest', '')} → {dr.get('latest', '')}")
        print(f"事件总数: {stats['totalEvents']}")
        print(f"关键事件: {len(stats['keyEvents'])}")

    # 如果 events 为空，提示
    if not events:
        print("\n⚠️ 该条件匹配到 0 条事件。请检查查询参数。")


if __name__ == "__main__":
    main()

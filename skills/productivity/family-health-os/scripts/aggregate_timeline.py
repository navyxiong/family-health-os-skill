#!/usr/bin/env python3
"""
Family Health OS — 时间轴聚合引擎

从 patients / diseases / exams / medications / hospitalizations / tasks 数据中
自动聚合生成 timeline.json 事件模型。

用法：
  python3 aggregate_timeline.py <patientId> [--data-dir <path>]

输出：
  打印聚合后的 timeline JSON 到 stdout
"""

import json
import os
import sys
import uuid
import random
import string
from datetime import datetime, date
from typing import Any, Optional, List, Dict

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "memory", "data")

# ============================================================
# 事件类型分类映射
# ============================================================
CATEGORY_MAP: Dict[str, str] = {
    "admission": "administrative",
    "discharge": "administrative",
    "transfer": "administrative",
    "surgery": "surgical",
    "procedure": "surgical",
    "exam": "diagnostic",
    "new_exam": "diagnostic",
    "exam_result": "diagnostic",
    "labResult": "diagnostic",
    "imaging": "diagnostic",
    "pathology": "diagnostic",
    "medicationStart": "medication",
    "medicationStop": "medication",
    "medicationChange": "medication",
    "diagnosis": "clinical",
    "diagnosisChange": "clinical",
    "symptom": "clinical",
    "symptom_change": "clinical",
    "round": "clinical",
    "doctor_round": "clinical",
    "consultation": "clinical",
    "note": "clinical",
    "vitalSigns": "monitoring",
    "followUp": "monitoring",
    "emergency": "emergency",
    "allergyReaction": "emergency",
    "vaccination": "preventive",
    "healthCheckup": "preventive",
    "other": "other",
}

# 源类型 → 事件ID前缀缩写
SOURCE_PREFIX = {
    "hospitalization": "hosp",
    "exam": "exam",
    "medication": "med",
    "disease": "dis",
    "task": "task",
    "manual": "man",
}

# 事件类型 → 是否是关键里程碑事件
KEY_EVENT_TYPES = {
    "admission", "discharge", "surgery", "diagnosis",
    "diagnosisChange", "emergency", "transfer",
}


# ============================================================
# 工具函数
# ============================================================

def generate_event_id(source_type: str, evt_date: str) -> str:
    """生成事件ID：evt-{源类型缩写}-{YYYYMMDD}-{4位随机}"""
    prefix = SOURCE_PREFIX.get(source_type, "evt")
    date_part = evt_date[:10].replace("-", "")  # YYYYMMDD
    rand_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"evt-{prefix}-{date_part}-{rand_part}"


def load_json(path: str) -> Optional[Any]:
    """加载 JSON 文件，返回内容或 None"""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def gen_event(
    event_type: str,
    title: str,
    date_str: str,
    source_type: str,
    source_id: str = "",
    source_doctor: str = "",
    source_institution: str = "",
    description: str = "",
    severity: str = "info",
    tags: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
    affected_body_site: str = "",
    related_event_ids: Optional[List[str]] = None,
) -> dict:
    """构造一个标准事件对象"""
    return {
        "eventId": generate_event_id(source_type, date_str),
        "eventIdSource": "auto",
        "date": date_str,
        "eventType": event_type,
        "category": CATEGORY_MAP.get(event_type, "other"),
        "title": title,
        "description": description,
        "severity": severity,
        "isKeyEvent": event_type in KEY_EVENT_TYPES,
        "sourceType": source_type,
        "sourceId": source_id,
        "sourceDoctor": source_doctor,
        "sourceInstitution": source_institution,
        "tags": tags or [],
        "affectedBodySite": affected_body_site,
        "metadata": metadata or {},
        "relatedEventIds": related_event_ids or [],
    }


# ============================================================
# 各数据源的聚合器
# ============================================================

def aggregate_from_hospitalizations(hospitals: List[dict], base_dir: str) -> List[dict]:
    """从住院档案生成事件"""
    events = []
    for hosp in hospitals:
        hid = hosp["id"]
        inst = hosp.get("hospital", {}).get("name", "")
        doctor = hosp.get("admittingDoctor", "") or hosp.get("attendingPhysician", "")

        # 入院
        events.append(gen_event(
            "admission",
            f"入院：{hosp.get('admittingDiagnosis', '')}",
            hosp["admissionDate"],
            "hospitalization", hid,
            doctor, inst,
            description=f"入院类型：{hosp.get('admissionType', '')}；科室：{hosp.get('department', '')}",
        ))

        # 每日病程
        for day in hosp.get("dailyProgress", []):
            day_type = day.get("type", "dailyProgress")
            evt_type = {
                "dailyProgress": "note",
                "roundNote": "doctor_round",
                "consultationNote": "consultation",
                "criticalNote": "emergency",
                "preOpNote": "note",
                "postOpNote": "note",
                "transferNote": "transfer",
            }.get(day_type, "note")

            events.append(gen_event(
                evt_type,
                f"[{day_type}] {day['date']} 病程记录",
                f"{day['date']}T00:00:00",
                "hospitalization", hid,
                day.get("doctor", ""), inst,
                description=day.get("content", "")[:200],
            ))

        # 手术
        for surg in hosp.get("surgeries", []):
            events.append(gen_event(
                "surgery",
                f"手术：{surg['surgeryName']}",
                surg["surgeryDate"],
                "hospitalization", hid,
                surg.get("surgeon", ""), inst,
                description=f"术前诊断：{surg.get('preOpDiagnosis', '')}；术后诊断：{surg.get('postOpDiagnosis', '')}",
                severity="critical",
            ))

        # 会诊
        for cons in hosp.get("consultations", []):
            events.append(gen_event(
                "consultation",
                f"会诊：{cons.get('consultingDepartment', '')}",
                f"{cons['date']}T00:00:00",
                "hospitalization", hid,
                cons.get("consultingDoctor", ""), inst,
                description=cons.get("opinion", "")[:200],
            ))

        # 出院
        if hosp.get("dischargeDate"):
            events.append(gen_event(
                "discharge",
                f"出院诊断：{hosp.get('dischargeDiagnosis', '')}",
                hosp["dischargeDate"],
                "hospitalization", hid,
                doctor, inst,
                description=f"出院状态：{hosp.get('dischargeStatus', '')}",
            ))

        if hosp.get("followUpPlan", {}).get("followUpDate"):
            fup = hosp["followUpPlan"]
            events.append(gen_event(
                "followUp",
                f"随访复诊：{fup.get('followUpDepartment', '')}",
                f"{fup['followUpDate']}T00:00:00",
                "hospitalization", hid,
                fup.get("followUpDoctor", ""), inst,
                description=f"医嘱：{fup.get('instructions', '')[:100]}",
            ))

    return events


def aggregate_from_exams(exams: List[dict]) -> List[dict]:
    """从检查报告生成事件"""
    events = []
    for exam in exams:
        eid = exam["id"]
        inst = exam.get("hospital", {}).get("name", "")
        doctor = exam.get("doctor", "") or exam.get("reportDoctor", "")

        # 新开检查
        events.append(gen_event(
            "new_exam",
            f"开具检查：{exam.get('examName', exam.get('examType', ''))}",
            exam["examDate"],
            "exam", eid,
            doctor, inst,
        ))

        # 检查结论/异常结果
        conclusion = exam.get("conclusion", "")
        abnormal_items = [
            item for item in exam.get("items", [])
            if item.get("flag") in ("high", "low", "criticalHigh", "criticalLow", "abnormal")
        ]

        if conclusion or abnormal_items:
            desc_parts = []
            if conclusion:
                desc_parts.append(f"结论：{conclusion}")
            for item in abnormal_items[:5]:
                df = item.get("displayFlag", "")
                item_name = item.get('itemName') or item.get('name', '')
                desc_parts.append(f"{item_name}：{item.get('value', '')}{item.get('unit', '')}{df}")
            if len(abnormal_items) > 5:
                desc_parts.append(f"...及其他 {len(abnormal_items) - 5} 项异常")

            report_date = exam.get("reportDate") or exam["examDate"]
            events.append(gen_event(
                "exam_result",
                f"检查结果：{exam.get('examName', exam.get('examType', ''))}",
                f"{report_date}T00:00:00" if "T" not in (report_date or "") else report_date,
                "exam", eid,
                exam.get("reportDoctor", ""), inst,
                description="；".join(desc_parts),
                severity="warning" if abnormal_items else "info",
                tags=["abnormal"] if abnormal_items else [],
            ))

    return events


def aggregate_from_medications(meds: List[dict]) -> List[dict]:
    """从用药记录生成事件"""
    events = []
    for med in meds:
        mid = med["id"]
        name = med.get("medicationName", "")
        dosage = med.get("dosage", {})
        freq = med.get("frequency", {})
        dose_str = f"{dosage.get('amount', '')}{dosage.get('unit', '')}" if dosage.get("amount") else ""
        freq_str = f"每日{freq.get('timesPerDay', '')}次" if freq.get("timesPerDay") else ""
        purpose = med.get("purpose", "")

        # 开始用药
        events.append(gen_event(
            "medicationStart",
            f"开始用药：{name}{'（' + purpose + '）' if purpose else ''}",
            f"{med['startDate']}T00:00:00",
            "medication", mid,
            med.get("prescribedBy", ""),
            description=f"剂量：{dose_str}，{freq_str}，途径：{med.get('route', '')}",
        ))

        # 停药
        if med.get("endDate"):
            events.append(gen_event(
                "medicationStop",
                f"停药：{name}",
                f"{med['endDate']}T00:00:00",
                "medication", mid,
                med.get("prescribedBy", ""),
                description=f"停药原因：{med.get('reasonForStop', '')}",
            ))

        # 副作用
        for se in med.get("sideEffects", []):
            events.append(gen_event(
                "symptom",
                f"不良反应：{se.get('effect', '')}",
                f"{se.get('onsetDate', '')}T00:00:00" if se.get("onsetDate") else med["startDate"],
                "medication", mid,
                description=f"严重程度：{se.get('severity', '')}；处理：{se.get('action', '')}",
                severity={
                    "mild": "info",
                    "moderate": "warning",
                    "severe": "critical",
                }.get(se.get("severity", ""), "info"),
            ))

    return events


def aggregate_from_diseases(diseases: List[dict]) -> List[dict]:
    """从疾病档案生成事件"""
    events = []
    for dis in diseases:
        did = dis["id"]
        name = dis.get("diseaseName", "")
        doctor = dis.get("diagnosedBy", "")

        # 确诊
        events.append(gen_event(
            "diagnosis",
            f"确诊：{name}",
            f"{dis['diagnosedDate']}T00:00:00",
            "disease", did,
            doctor,
            description=f"ICD编码：{dis.get('icdCode', '')}；严重程度：{dis.get('severity', '')}；分期：{dis.get('stage', '')}",
            severity=("critical" if dis.get("severity") in ("severe", "critical") else "warning"),
            tags=[dis.get("status", "")] if dis.get("status") else [],
        ))

        # 疾病状态变化
        # (状态变更通过 episodes 和 complications 追踪)

        # 发作/复发
        for ep in dis.get("episodes", []):
            events.append(gen_event(
                "symptom_change",
                f"{name}发作",
                f"{ep.get('startDate', '')}T00:00:00",
                "disease", did,
                doctor,
                description=f"严重度：{ep.get('severity', '')}；诱因：{ep.get('trigger', '')}；症状：{', '.join(ep.get('symptoms', []))}",
                severity={
                    "mild": "info",
                    "moderate": "warning",
                    "severe": "critical",
                }.get(ep.get("severity", ""), "info"),
            ))

        # 并发症
        for comp in dis.get("complications", []):
            events.append(gen_event(
                "diagnosisChange",
                f"并发症：{comp.get('name', '')}",
                f"{comp.get('diagnosedDate', '')}T00:00:00",
                "disease", did,
                doctor,
                description=f"由 {name} 引发的并发症",
                severity="warning",
            ))

    return events


def aggregate_from_tasks(tasks: List[dict]) -> List[dict]:
    """从任务/提醒生成事件"""
    events = []
    for task in tasks:
        tid = task["id"]
        task_type = task.get("taskType", "other")
        evt_type = {
            "followUp": "followUp",
            "examReminder": "exam",
            "medicationRefill": "medicationChange",
            "medicationReminder": "note",
            "vaccination": "vaccination",
            "labTest": "labResult",
            "imaging": "imaging",
            "checkup": "healthCheckup",
            "surgeryFollowUp": "followUp",
            "bloodPressureLog": "vitalSigns",
            "bloodSugarLog": "vitalSigns",
            "weightLog": "vitalSigns",
        }.get(task_type, "other")

        events.append(gen_event(
            evt_type,
            task.get("title", ""),
            task["dueDate"],
            "task", tid,
            task.get("createdBy", ""),
            description=task.get("description", ""),
            severity={
                "high": "warning",
                "urgent": "critical",
                "medium": "info",
                "low": "info",
            }.get(task.get("priority", ""), "info"),
            tags=[task_type],
        ))

    return events


# ============================================================
# 主聚合函数
# ============================================================

def build_timeline(
    patient_id: str,
    data_dir: str,
) -> dict:
    """为指定患者构建完整时间轴"""
    all_events: List[dict] = []
    source_counts: Dict[str, int] = {}

    # 从各数据源聚合事件
    aggregators = [
        ("hospitalizations", aggregate_from_hospitalizations),
        ("exams", aggregate_from_exams),
        ("medications", aggregate_from_medications),
        ("diseases", aggregate_from_diseases),
        ("tasks", aggregate_from_tasks),
    ]

    for entity_name, aggregator in aggregators:
        path = os.path.join(data_dir, f"{entity_name}.json")
        records = load_json(path)
        if not records:
            continue
        # 如果是对象列表，过滤属于该患者的
        data = records if isinstance(records, list) else records.get(entity_name, [])
        patient_records = [r for r in data if r.get("patientId") == patient_id]
        if patient_records:
            # aggregate_from_hospitalizations 需要 base_dir
            if entity_name == "hospitalizations":
                evts = aggregator(patient_records, data_dir)
            else:
                evts = aggregator(patient_records)
            all_events.extend(evts)
            source_counts[entity_name] = len(evts)

    # 按时间排序
    all_events.sort(key=lambda e: e["date"])

    # 构建月份分组索引
    monthly_groups: Dict[str, List[str]] = {}
    for ev in all_events:
        month_key = ev["date"][:7]  # YYYY-MM
        if month_key not in monthly_groups:
            monthly_groups[month_key] = []
        monthly_groups[month_key].append(ev["eventId"])

    # 构建时间范围
    if all_events:
        earliest = all_events[0]["date"][:10]
        latest = all_events[-1]["date"][:10]
    else:
        earliest = latest = ""

    # 日期范围使用 date 格式
    date_range = {"earliest": earliest, "latest": latest} if earliest else {}

    timeline = {
        "id": str(uuid.uuid4()),
        "patientId": patient_id,
        "generatedAt": datetime.now().isoformat(),
        "generatedBy": "auto",
        "events": all_events,
        "monthlyGroups": dict(sorted(monthly_groups.items())),
        "summary": "",
        "eventCount": len(all_events),
        "dateRange": date_range,
        "version": 1,
    }

    # 生成病程摘要
    timeline["summary"] = generate_summary(timeline, source_counts)

    return timeline


def generate_summary(timeline: dict, source_counts: Dict[str, int]) -> str:
    """根据聚合结果生成病程摘要"""
    events = timeline["events"]
    if not events:
        return "暂无病程记录"

    date_range = timeline.get("dateRange", {})
    earliest = date_range.get("earliest", "")
    latest = date_range.get("latest", "")
    total = timeline["eventCount"]

    # 统计事件类型
    type_counts: dict[str, int] = {}
    for ev in events:
        t = ev["eventType"]
        type_counts[t] = type_counts.get(t, 0) + 1

    type_labels = {
        "admission": "入院", "discharge": "出院", "surgery": "手术",
        "diagnosis": "确诊", "consultation": "会诊", "emergency": "紧急",
        "medicationStart": "用药", "medicationStop": "停药",
        "exam_result": "检查结果", "followUp": "随访",
    }

    type_summary = "；".join(
        f"{type_labels.get(t, t)}×{c}"
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:8]
    )

    source_summary = "、".join(
        f"{k.replace('s', '').capitalize()}({c}件)"
        for k, c in sorted(source_counts.items(), key=lambda x: -x[1])
    )

    return (
        f"时间跨度：{earliest} ~ {latest}，共 {total} 条事件 | "
        f"事件分布：{type_summary} | "
        f"数据来源：{source_summary}"
    )


# ============================================================
# 校验
# ============================================================

def validate_timeline(timeline: dict) -> list[str]:
    """校验时间轴数据完整性"""
    errors = []
    events = timeline.get("events", [])

    if not events:
        errors.append("WARNING: 时间轴为空")

    for ev in events:
        eid = ev.get("eventId", "?")
        if not ev.get("eventId"):
            errors.append(f"事件缺少 eventId")
        if not ev.get("eventType"):
            errors.append(f"{eid}: 缺少 eventType")
        if not ev.get("date"):
            errors.append(f"{eid}: 缺少 date")
        if not ev.get("sourceType"):
            errors.append(f"{eid}: 缺少 sourceType")
        if not ev.get("category"):
            errors.append(f"{eid}: 缺少 category")
        if ev.get("sourceType") != "manual" and not ev.get("sourceDoctor") and not ev.get("sourceInstitution"):
            errors.append(f"{eid}: 缺少信息来源标注 (sourceDoctor/sourceInstitution)")

    # 验证 monthlyGroups 与 events 一致
    mg = timeline.get("monthlyGroups", {})
    all_event_ids = {ev["eventId"] for ev in events}
    indexed_ids = set()
    for month_ids in mg.values():
        indexed_ids.update(month_ids)

    missing_in_index = all_event_ids - indexed_ids
    if missing_in_index:
        errors.append(f"以下事件未在 monthlyGroups 中索引：{', '.join(list(missing_in_index)[:5])}")

    extra_in_index = indexed_ids - all_event_ids
    if extra_in_index:
        errors.append(f"monthlyGroups 中有 {len(extra_in_index)} 个事件ID在 events 中不存在")

    return errors


# ============================================================
# CLI 入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <patientId> [--data-dir <path>]")
        sys.exit(1)

    patient_id = sys.argv[1]
    data_dir = SCHEMA_DIR
    for i, arg in enumerate(sys.argv):
        if arg == "--data-dir" and i + 1 < len(sys.argv):
            data_dir = sys.argv[i + 1]

    timeline = build_timeline(patient_id, data_dir)
    errors = validate_timeline(timeline)

    output = {"timeline": timeline}
    if errors:
        output["validation"] = errors

    print(json.dumps(output, ensure_ascii=False, indent=2))

    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()

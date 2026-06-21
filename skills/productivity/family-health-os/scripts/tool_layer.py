#!/usr/bin/env python3
"""
Family Health OS — Tool Layer

这层是 Agent 可直接调用的工具接口，封装 Memory Manager 和聚合引擎，
提供简洁的语义化操作。

每条工具函数 = 一个完整业务操作（非原子文件操作）。
"""

import json
import os
import sys
import uuid
from datetime import datetime, date
from typing import Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "memory", "data")

# ──────────────────────────────────────────────
# 基础工具
# ──────────────────────────────────────────────

def _load(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Handle timeline.json: {"timeline": {...}} or single object
        if "timeline" in data:
            return [data["timeline"]]
        # Single patient/timeline object
        if data.get("id") or data.get("patientId"):
            return [data]
    return []

def _save(path: str, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _path(entity: str) -> str:
    return os.path.join(DATA_DIR, f"{entity}.json")

def _now() -> str:
    return datetime.now().isoformat()

def _new_id() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# 业务工具函数（供 Agent 调用）
# ──────────────────────────────────────────────

def add_patient(name: str, gender: str, birth_date: str,
                blood_type: str = "", allergies: list = None,
                emergency_contact: dict = None,
                family_history: list = None,
                lifestyle: dict = None) -> dict:
    """添加家庭成员"""
    record = {
        "id": _new_id(),
        "name": name,
        "gender": gender,
        "birthDate": birth_date,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if blood_type:
        record["bloodType"] = blood_type
    if allergies:
        record["allergies"] = allergies
    if emergency_contact:
        record["emergencyContact"] = emergency_contact
    if family_history:
        record["familyHistory"] = family_history
    if lifestyle:
        record["lifestyle"] = lifestyle

    records = _load(_path("patients"))
    records.append(record)
    _save(_path("patients"), records)
    return {"success": True, "entity": "patients", "record": record}


def add_exam(patient_id: str, exam_name: str, exam_type: str,
             exam_date: str, hospital: dict, items: list,
             conclusion: str = "", doctor: str = "",
             report_doctor: str = "",
             related_disease_ids: list = None,
             related_hospitalization_id: str = "",
             images: list = None) -> dict:
    """录入检查报告，自动标记异常值"""
    processed_items = []
    for item in items:
        pi = dict(item)
        # 自动标记 flag
        if "referenceLow" in pi or "referenceHigh" in pi:
            val = pi.get("value")
            try:
                val_f = float(str(val).replace(">","").replace("<",""))
                low = pi.get("referenceLow")
                high = pi.get("referenceHigh")
                if low is not None and high is not None:
                    if val_f > high:
                        pi["flag"] = "criticalHigh" if val_f > high * 2 else "high"
                        pi["displayFlag"] = "↑↑" if val_f > high * 2 else "↑"
                    elif val_f < low:
                        pi["flag"] = "criticalLow" if val_f < low / 2 else "low"
                        pi["displayFlag"] = "↓↓" if val_f < low / 2 else "↓"
                    else:
                        pi["flag"] = "normal"
            except (ValueError, TypeError):
                pass
        processed_items.append(pi)

    record = {
        "id": _new_id(),
        "patientId": patient_id,
        "examDate": exam_date,
        "reportDate": exam_date[:10],
        "examType": exam_type,
        "examName": exam_name,
        "hospital": hospital,
        "doctor": doctor,
        "reportDoctor": report_doctor,
        "items": processed_items,
        "conclusion": conclusion,
        "images": images or [],
        "attachments": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if related_disease_ids:
        record["relatedDiseaseIds"] = related_disease_ids
    if related_hospitalization_id:
        record["relatedHospitalizationId"] = related_hospitalization_id

    records = _load(_path("exams"))
    records.append(record)
    _save(_path("exams"), records)

    _trigger_aggregate(patient_id)
    return {"success": True, "entity": "exams", "record": record,
            "abnormal_count": sum(1 for i in processed_items if i.get("flag") not in (None, "normal"))}


def add_hospitalization(patient_id: str, admission_date: str,
                         hospital: dict, department: str,
                         admitting_diagnosis: str,
                         discharge_date: str = "",
                         chief_complaint: str = "",
                         present_illness: str = "",
                         attending_physician: str = "",
                         daily_progress: list = None,
                         surgeries: list = None,
                         consultations: list = None,
                         discharge_diagnosis: str = "",
                         discharge_summary: str = "",
                         discharge_medications: list = None,
                         follow_up_plan: dict = None) -> dict:
    """录入住院档案"""
    # 计算住院天数
    total_days = None
    if discharge_date:
        try:
            adm = datetime.strptime(admission_date[:10], "%Y-%m-%d")
            dis = datetime.strptime(discharge_date[:10], "%Y-%m-%d")
            total_days = (dis - adm).days
        except ValueError:
            pass

    record = {
        "id": _new_id(),
        "patientId": patient_id,
        "admissionDate": admission_date,
        "admissionType": "emergency",
        "hospital": hospital,
        "department": department,
        "admittingDiagnosis": admitting_diagnosis,
        "attendingPhysician": attending_physician,
        "chiefComplaint": chief_complaint,
        "presentIllness": present_illness,
        "dailyProgress": daily_progress or [],
        "surgeries": surgeries or [],
        "consultations": consultations or [],
        "dischargeMedications": discharge_medications or [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if discharge_date:
        record["dischargeDate"] = discharge_date
    if discharge_diagnosis:
        record["dischargeDiagnosis"] = discharge_diagnosis
    if discharge_summary:
        record["dischargeSummary"] = discharge_summary
    if follow_up_plan:
        record["followUpPlan"] = follow_up_plan
    if total_days is not None:
        record["totalDays"] = total_days

    records = _load(_path("hospitalizations"))
    records.append(record)
    _save(_path("hospitalizations"), records)

    _trigger_aggregate(patient_id)
    return {"success": True, "entity": "hospitalizations", "record": record}


def add_medication(patient_id: str, medication_name: str,
                   dosage: dict, frequency: dict,
                   route: str, start_date: str,
                   end_date: str = "",
                   purpose: str = "",
                   prescribed_by: str = "",
                   related_disease_ids: list = None,
                   related_hospitalization_id: str = "",
                   side_effects: list = None) -> dict:
    """录入用药记录"""
    record = {
        "id": _new_id(),
        "patientId": patient_id,
        "medicationName": medication_name,
        "dosage": dosage,
        "frequency": frequency,
        "route": route,
        "startDate": start_date,
        "isOngoing": not bool(end_date),
        "purpose": purpose,
        "prescribedBy": prescribed_by,
        "sideEffects": side_effects or [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if end_date:
        record["endDate"] = end_date
    if related_disease_ids:
        record["relatedDiseaseIds"] = related_disease_ids
    if related_hospitalization_id:
        record["relatedHospitalizationId"] = related_hospitalization_id

    records = _load(_path("medications"))
    records.append(record)
    _save(_path("medications"), records)

    _trigger_aggregate(patient_id)
    return {"success": True, "entity": "medications", "record": record}


def add_disease(patient_id: str, disease_name: str,
                diagnosed_date: str, status: str,
                icd_code: str = "",
                severity: str = "",
                diagnosed_by: str = "",
                diagnosis_basis: str = "",
                episodes: list = None,
                target_values: dict = None) -> dict:
    """录入疾病诊断"""
    record = {
        "id": _new_id(),
        "patientId": patient_id,
        "diseaseName": disease_name,
        "diagnosedDate": diagnosed_date,
        "status": status,
        "episodes": episodes or [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if icd_code:
        record["icdCode"] = icd_code
    if severity:
        record["severity"] = severity
    if diagnosed_by:
        record["diagnosedBy"] = diagnosed_by
    if diagnosis_basis:
        record["diagnosisBasis"] = diagnosis_basis
    if target_values:
        record["targetValues"] = target_values

    records = _load(_path("diseases"))
    records.append(record)
    _save(_path("diseases"), records)

    _trigger_aggregate(patient_id)
    return {"success": True, "entity": "diseases", "record": record}


def add_task(patient_id: str, task_type: str, title: str,
             due_date: str, priority: str = "medium",
             description: str = "",
             recurrence: dict = None) -> dict:
    """添加复查提醒/任务"""
    record = {
        "id": _new_id(),
        "patientId": patient_id,
        "taskType": task_type,
        "title": title,
        "dueDate": due_date,
        "priority": priority,
        "status": "pending",
        "description": description,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if recurrence:
        record["recurrence"] = recurrence

    records = _load(_path("tasks"))
    records.append(record)
    _save(_path("tasks"), records)
    return {"success": True, "entity": "tasks", "record": record}


# ──────────────────────────────────────────────
# 查询工具
# ──────────────────────────────────────────────

def get_patient(patient_id: str) -> Optional[dict]:
    """查询患者"""
    records = _load(_path("patients"))
    return next((r for r in records if r.get("id") == patient_id), None)


def get_patient_by_name(name: str) -> list:
    """按姓名查找患者"""
    records = _load(_path("patients"))
    return [r for r in records if name in r.get("name", "")]


def list_patients() -> list:
    """列出所有患者"""
    return _load(_path("patients"))


def get_patient_events(patient_id: str) -> list:
    """获取患者的所有事件（从 timeline）"""
    tl_path = _path("timeline")
    if not os.path.exists(tl_path):
        return []
    records = _load(tl_path)
    for r in records:
        if r.get("patientId") == patient_id:
            return r.get("events", [])
    return []


def get_patient_summary(patient_id: str) -> Optional[dict]:
    """获取患者完整档案摘要"""
    patient = get_patient(patient_id)
    if not patient:
        return None
    return {
        "patient": patient,
        "diseases": [r for r in _load(_path("diseases")) if r.get("patientId") == patient_id],
        "exams": [r for r in _load(_path("exams")) if r.get("patientId") == patient_id],
        "medications": [r for r in _load(_path("medications")) if r.get("patientId") == patient_id],
        "hospitalizations": [r for r in _load(_path("hospitalizations")) if r.get("patientId") == patient_id],
        "tasks": [r for r in _load(_path("tasks")) if r.get("patientId") == patient_id],
    }


# ──────────────────────────────────────────────
# 聚合触发
# ──────────────────────────────────────────────

def _trigger_aggregate(patient_id: str):
    """异步触发时间轴聚合"""
    import subprocess
    try:
        script = os.path.join(SCRIPT_DIR, "aggregate_timeline.py")
        subprocess.Popen(
            [sys.executable, script, patient_id, "--data-dir", DATA_DIR],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def rebuild_timeline(patient_id: str) -> dict:
    """同步重建时间轴并返回结果"""
    import subprocess
    script = os.path.join(SCRIPT_DIR, "aggregate_timeline.py")
    r = subprocess.run(
        [sys.executable, script, patient_id, "--data-dir", DATA_DIR],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        return {"success": False, "error": r.stderr}
    
    output = json.loads(r.stdout)
    timeline_data = output.get("timeline", output)
    
    # Save to timeline.json (multi-patient list)
    tl_path = os.path.join(DATA_DIR, "timeline.json")
    existing = []
    if os.path.exists(tl_path):
        with open(tl_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            existing = raw
        elif isinstance(raw, dict):
            # Single patient timeline
            existing = [raw.get("timeline", raw)] if raw.get("patientId") or raw.get("id") else []
    
    # Remove existing entry for this patient
    existing = [t for t in existing if t.get("patientId") != patient_id]
    # Add new entry
    if isinstance(timeline_data, dict):
        existing.append(timeline_data)
    
    with open(tl_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return {"success": True, "output": output}


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    """演示完整链路"""
    print("=" * 60)
    print("Family Health OS — Tool Layer 演示")
    print("=" * 60)

    # 列出所有患者
    patients = list_patients()
    print(f"\n📋 现有患者: {len(patients)} 人")
    for p in patients:
        print(f"   {p['id'][:8]}... {p['name']}")

    # 对每个患者展示摘要
    for p in patients:
        pid = p["id"]
        print(f"\n{'='*60}")
        print(f"👤 患者: {p['name']}")
        summary = get_patient_summary(pid)
        if summary:
            print(f"  疾病: {len(summary['diseases'])} 条")
            for d in summary['diseases']:
                print(f"    - {d['diseaseName']} ({d.get('status','')})")
            print(f"  检查: {len(summary['exams'])} 条")
            print(f"  用药: {len(summary['medications'])} 条")
            print(f"  住院: {len(summary['hospitalizations'])} 条")

        # 时间轴
        events = get_patient_events(pid)
        print(f"  时间轴: {len(events)} 条事件")
        if events:
            key_events = [e for e in events if e.get("isKeyEvent")]
            print(f"  关键事件: {len(key_events)} 件")
            for e in key_events[:5]:
                print(f"    ★ {e['date'][:10]} {e.get('title','')}")

    print(f"\n{'='*60}")
    print("✅ Tool Layer 演示完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

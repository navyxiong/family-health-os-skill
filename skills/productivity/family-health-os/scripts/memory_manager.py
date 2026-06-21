#!/usr/bin/env python3
"""
Family Health OS — Memory Manager V1

统一管理所有数据文件的 CRUD + 查询操作。
Layer 0.5: 原始数据文件之上的统一访问层。

用法:
  # 作为模块导入
  from memory_manager import MemoryManager
  mm = MemoryManager("memory/schemas/")
  mm.createRecord("patients", {"name": "张三", ...})

  # 作为 CLI
  python3 memory_manager.py <entity> <action> [args...]
"""

import json
import os
import sys
import uuid
import fcntl
import copy
import time
from datetime import datetime
from typing import Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "memory", "data")

# ============================================================
# 支持的实体
# ============================================================

ENTITIES = {
    "patients", "diseases", "exams", "medications",
    "hospitalizations", "tasks", "timeline", "events",
}

REQUIRED_FIELDS = {
    "patients": ["name", "gender", "birthDate"],
    "diseases": ["patientId", "diseaseName", "diagnosedDate", "status"],
    "exams": ["patientId", "examDate", "examType", "items"],
    "medications": ["patientId", "medicationName", "startDate"],
    "hospitalizations": ["patientId", "admissionDate", "hospital", "department", "admittingDiagnosis"],
    "tasks": ["patientId", "taskType", "title", "dueDate"],
    "events": ["patientId", "eventType", "date"],
}

# timeline 禁止直接操作
READ_ONLY_ENTITIES = {"timeline"}

# 已知枚举值校验
VALID_GENDERS = {"male", "female", "other"}
VALID_DISEASE_STATUS = {"active", "remission", "controlled", "resolved", "recovered", "chronic"}
VALID_SEVERITIES = {"mild", "moderate", "severe", "critical"}
VALID_TASK_STATUS = {"pending", "inProgress", "completed", "cancelled", "overdue", "deferred"}
VALID_ADMISSION_TYPES = {"emergency", "elective", "transfer", "other"}
VALID_DISCHARGE_STATUS = {"cured", "improved", "unchanged", "deteriorated", "transferred", "died", "againstAdvice"}
VALID_TASK_TYPES = {
    "followUp", "examReminder", "medicationRefill", "medicationReminder",
    "vaccination", "labTest", "imaging", "checkup", "surgeryFollowUp",
    "rehabilitation", "dietaryLog", "bloodPressureLog", "bloodSugarLog",
    "weightLog", "generalReminder", "other",
}
VALID_EXAM_TYPES = {
    "ct", "cta", "ultrasound", "pathology", "bloodTest", "urinalysis",
    "biochemistry", "coagulation", "hormone", "tumorMarker", "immunology",
    "microbiology", "bloodGas", "hba1c", "ecg", "boneDensity", "mri",
    "xray", "pulmonaryFunction", "endoscopy", "other",
}
VALID_DOSAGE_FORMS = {"tablet", "capsule", "injection", "liquid", "cream", "inhaler", "patch", "drops", "suppository", "other"}
VALID_ROUTES = {"oral", "intravenous", "intramuscular", "subcutaneous", "topical", "inhalation", "sublingual", "rectal", "ophthalmic", "otic", "intrathecal", "other"}
VALID_EVENT_TYPES = {
    "admission", "discharge", "surgery", "exam", "new_exam", "exam_result",
    "medicationStart", "medicationStop", "medicationChange",
    "diagnosis", "diagnosisChange", "consultation", "round", "doctor_round",
    "vaccination", "allergyReaction", "emergency", "followUp",
    "labResult", "imaging", "pathology", "procedure", "transfer",
    "symptom", "symptom_change", "vitalSigns", "healthCheckup", "note", "other",
}
VALID_SOURCE_TYPES = {"hospitalization", "exam", "medication", "disease", "manual", "task"}
VALID_EVENT_SEVERITIES = {"info", "warning", "critical", "normal"}

# ============================================================
# 错误类型
# ============================================================

class EntityNotFoundError(Exception): pass
class RecordNotFoundError(Exception): pass
class ValidationError(Exception): pass
class FieldLockedError(Exception): pass
class FileLockError(Exception): pass
class CascadeError(Exception): pass
class QueryError(Exception): pass
class ReadOnlyEntityError(Exception): pass

# ============================================================
# MemoryManager
# ============================================================

class MemoryManager:
    def __init__(self, data_dir: str = SCHEMA_DIR):
        self.data_dir = data_dir
        self._lock_timeout = 5  # seconds

    # ── 文件 I/O ──

    def _filepath(self, entity: str) -> str:
        return os.path.join(self.data_dir, f"{entity}.json")

    def _read_file(self, entity: str) -> list:
        path = self._filepath(entity)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # 尝试从字典中提取列表（兼容 timeline 格式）
            if "events" in data:
                return [data]  # timeline 单对象包装为列表
            # 按实体名提取
            for key in [entity, entity + "s", entity.replace("s", "")]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        return []

    def _write_file(self, entity: str, data: list):
        path = self._filepath(entity)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _file_lock(self, entity: str):
        """文件锁上下文管理器"""
        class FileLock:
            def __init__(self, mgr, entity):
                self.mgr = mgr
                self.entity = entity
                self.lock_path = self.mgr._filepath(entity) + ".lock"
                self.fd = None

            def __enter__(self):
                self.fd = open(self.lock_path, "w")
                deadline = time.time() + self.mgr._lock_timeout
                while time.time() < deadline:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return self
                    except IOError:
                        time.sleep(0.1)
                raise FileLockError(f"File {self.entity}.json is locked after {self.mgr._lock_timeout}s")

            def __exit__(self, *args):
                if self.fd:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                    self.fd.close()
                    try:
                        os.remove(self.lock_path)
                    except OSError:
                        pass
        return FileLock(self, entity)

    # ── 校验 ──

    def _validate_entity(self, entity: str):
        if entity not in ENTITIES:
            raise EntityNotFoundError(
                f"Entity '{entity}' not found. Supported: {', '.join(sorted(ENTITIES))}"
            )

    def _validate_readonly(self, entity: str):
        if entity in READ_ONLY_ENTITIES:
            raise ReadOnlyEntityError(f"Entity '{entity}' is read-only. Use aggregate_timeline.py to rebuild.")

    def _validate_required(self, entity: str, data: dict):
        missing = [f for f in REQUIRED_FIELDS.get(entity, []) if f not in data]
        if missing:
            raise ValidationError(f"Missing required field(s): {', '.join(missing)}")

    def _validate_generic(self, entity: str, data: dict):
        """通用字段校验"""
        now = datetime.now().isoformat()

        # 自动注入字段
        if "createdAt" not in data:
            data["createdAt"] = now
        data["updatedAt"] = now

        # 禁止手动设置 id（create 时）
        # （createRecord 会处理）
        return data

    def _validate_entity_specific(self, entity: str, data: dict):
        """实体特定校验"""
        if entity == "patients":
            if data.get("gender") and data["gender"] not in VALID_GENDERS:
                raise ValidationError(f"Invalid gender: {data['gender']}")
            if data.get("birthDate"):
                try:
                    datetime.strptime(data["birthDate"][:10], "%Y-%m-%d")
                except ValueError:
                    raise ValidationError(f"Invalid birthDate format: {data['birthDate']}")

        elif entity == "diseases":
            if data.get("status") and data["status"] not in VALID_DISEASE_STATUS:
                raise ValidationError(f"Invalid disease status: {data['status']}")
            if data.get("severity") and data["severity"] not in VALID_SEVERITIES:
                raise ValidationError(f"Invalid severity: {data['severity']}")

        elif entity == "exams":
            if data.get("examType") and data["examType"] not in VALID_EXAM_TYPES:
                # 非严格，仅警告
                pass
            if "items" in data and (not data["items"] or not isinstance(data["items"], list)):
                raise ValidationError("exams.items must be a non-empty array")

        elif entity == "medications":
            if data.get("dosageForm") and data["dosageForm"] not in VALID_DOSAGE_FORMS:
                raise ValidationError(f"Invalid dosageForm: {data['dosageForm']}")
            if data.get("route") and data["route"] not in VALID_ROUTES:
                raise ValidationError(f"Invalid route: {data['route']}")

        elif entity == "hospitalizations":
            if data.get("admissionType") and data["admissionType"] not in VALID_ADMISSION_TYPES:
                raise ValidationError(f"Invalid admissionType: {data['admissionType']}")
            if data.get("dischargeStatus") and data["dischargeStatus"] not in VALID_DISCHARGE_STATUS:
                raise ValidationError(f"Invalid dischargeStatus: {data['dischargeStatus']}")

        elif entity == "tasks":
            if data.get("taskType") and data["taskType"] not in VALID_TASK_TYPES:
                raise ValidationError(f"Invalid taskType: {data['taskType']}")
            if data.get("status") and data["status"] not in VALID_TASK_STATUS:
                raise ValidationError(f"Invalid task status: {data['status']}")

        elif entity == "events":
            if data.get("eventType") and data["eventType"] not in VALID_EVENT_TYPES:
                raise ValidationError(f"Invalid eventType: {data['eventType']}")
            if data.get("sourceType") and data["sourceType"] not in VALID_SOURCE_TYPES:
                raise ValidationError(f"Invalid sourceType: {data['sourceType']}")
            if data.get("severity") and data["severity"] not in VALID_EVENT_SEVERITIES:
                raise ValidationError(f"Invalid severity: {data['severity']}")

    # ── CRUD ──

    def createRecord(self, entity: str, data: dict, auto_id: bool = True) -> dict:
        self._validate_entity(entity)
        self._validate_readonly(entity)
        self._validate_required(entity, data)
        data = dict(data)  # 浅拷贝避免修改传入对象

        # 自动生成 ID
        if auto_id and "id" not in data and entity != "events":
            data["id"] = str(uuid.uuid4())
        if entity == "events" and "eventId" not in data:
            raise ValidationError("events requires eventId")

        self._validate_generic(entity, data)
        self._validate_entity_specific(entity, data)

        with self._file_lock(entity):
            records = self._read_file(entity)
            records.append(data)
            self._write_file(entity, records)

        # 后置钩子
        hooks = self._run_post_hooks("create", entity, data)

        return {
            "success": True,
            "entity": entity,
            "record": data,
            "hooks": hooks,
        }

    def getRecord(self, entity: str, record_id: str) -> dict:
        self._validate_entity(entity)
        with self._file_lock(entity):
            records = self._read_file(entity)

        # timeline 和 events 按不同字段查找
        if entity == "timeline":
            record = next((r for r in records if r.get("patientId") == record_id), None)
        elif entity == "events":
            record = next((r for r in records if r.get("eventId") == record_id), None)
        else:
            record = next((r for r in records if r.get("id") == record_id), None)

        return {
            "success": True,
            "entity": entity,
            "record": record,
        }

    def updateRecord(self, entity: str, record_id: str, updates: dict, merge: bool = True) -> dict:
        self._validate_entity(entity)
        self._validate_readonly(entity)

        # 禁止修改关键字段
        for locked in ("id", "patientId"):
            if locked in updates:
                raise FieldLockedError(f"Field '{locked}' is locked and cannot be modified")

        with self._file_lock(entity):
            records = self._read_file(entity)
            if entity == "events":
                idx = next((i for i, r in enumerate(records) if r.get("eventId") == record_id), None)
            else:
                idx = next((i for i, r in enumerate(records) if r.get("id") == record_id), None)

            if idx is None:
                raise RecordNotFoundError(f"Record '{record_id}' not found in {entity}")

            before = copy.deepcopy(records[idx])

            if merge:
                records[idx].update(updates)
            else:
                records[idx] = updates

            records[idx]["updatedAt"] = datetime.now().isoformat()
            changed = self._detect_changes(before, records[idx])
            self._write_file(entity, records)

        hooks = self._run_post_hooks("update", entity, records[idx])

        return {
            "success": True,
            "entity": entity,
            "record_id": record_id,
            "before": before,
            "after": records[idx],
            "changed_fields": changed,
            "hooks": hooks,
        }

    def deleteRecord(self, entity: str, record_id: str, cascade: bool = True) -> dict:
        self._validate_entity(entity)
        self._validate_readonly(entity)

        deleted_info = {"primary": None, "cascade": {}}

        with self._file_lock(entity):
            records = self._read_file(entity)
            if entity == "events":
                idx = next((i for i, r in enumerate(records) if r.get("eventId") == record_id), None)
            else:
                idx = next((i for i, r in enumerate(records) if r.get("id") == record_id), None)

            if idx is None:
                raise RecordNotFoundError(f"Record '{record_id}' not found in {entity}")

            deleted_info["primary"] = copy.deepcopy(records[idx])
            records.pop(idx)
            self._write_file(entity, records)

        # 级联删除
        if cascade:
            cascade_counts = self._do_cascade_delete(entity, deleted_info["primary"])
            deleted_info["cascade"] = cascade_counts

        hooks = self._run_post_hooks("delete", entity, deleted_info["primary"])

        return {
            "success": True,
            "entity": entity,
            "deleted": deleted_info,
            "hooks": hooks,
        }

    def queryRecords(self, entity: str, filters: dict = None,
                     sort: str = "date", order: str = "desc",
                     limit: int = 100, offset: int = 0) -> dict:
        self._validate_entity(entity)
        filters = filters or {}

        # 对于 events 查询，如果 events.json 不存在则从 timeline 摊平
        if entity == "events":
            if not os.path.exists(self._filepath("events")):
                self._rebuild_events_from_timeline()

        with self._file_lock(entity):
            records = self._read_file(entity)

        # 应用过滤器
        filtered = self._apply_filters(entity, records, filters)

        # 排序
        reverse = order == "desc"
        if sort in ("date", "createdAt", "updatedAt", "examDate", "admissionDate", "dueDate", "startDate"):
            filtered.sort(key=lambda r: r.get(sort, ""), reverse=reverse)
        elif sort in ("severity", "priority", "eventType"):
            filtered.sort(key=lambda r: r.get(sort, ""), reverse=reverse)

        total = len(filtered)
        paged = filtered[offset:offset + limit]

        # 统计
        stats = self._compute_stats(entity, filtered)

        return {
            "success": True,
            "entity": entity,
            "total": total,
            "limit": limit,
            "offset": offset,
            "records": paged,
            "stats": stats,
        }

    # ── 过滤器 ──

    def _apply_filters(self, entity: str, records: list, filters: dict) -> list:
        result = list(records)

        # 精确匹配
        for key in ("patientId", "eventType", "category", "severity",
                     "sourceType", "status", "examType", "taskType", "isKeyEvent"):
            if key in filters:
                result = [r for r in result if r.get(key) == filters[key]]

        # IN 查询
        for key in ("patientIds", "eventTypes"):
            if key in filters and isinstance(filters[key], list):
                field = key[:-1] if key.endswith("s") else key
                result = [r for r in result if r.get(field) in filters[key]]

        # 时间范围
        if "startDate" in filters:
            sd = filters["startDate"]
            result = [r for r in result if (r.get("date") or r.get("examDate") or r.get("admissionDate") or "") >= sd]
        if "endDate" in filters:
            ed = filters["endDate"]
            result = [r for r in result if (r.get("date") or r.get("examDate") or r.get("admissionDate") or "") <= ed]

        # 模糊搜索
        if "search" in filters and filters["search"]:
            q = filters["search"].lower()
            result = [
                r for r in result
                if q in (r.get("title", "") + r.get("description", "") + r.get("name", "") +
                         r.get("diseaseName", "") + r.get("medicationName", "")).lower()
            ]

        # 标签包含
        if "tags" in filters and isinstance(filters["tags"], list):
            for tag in filters["tags"]:
                result = [r for r in result if tag in r.get("tags", [])]

        # 模糊字段
        for key in ("sourceDoctor", "sourceInstitution"):
            if key in filters and filters[key]:
                q = filters[key].lower()
                result = [r for r in result if q in r.get(key, "").lower()]

        return result

    def _compute_stats(self, entity: str, records: list) -> dict:
        stats = {}
        if entity == "events":
            from collections import Counter
            stats["byType"] = dict(Counter(r.get("eventType", "") for r in records).most_common(20))
            stats["bySeverity"] = dict(Counter(r.get("severity", "info") for r in records))
        elif entity in ("exams",):
            stats["total_exams"] = len(records)
        elif entity in ("medications",):
            stats["ongoing"] = len([r for r in records if r.get("isOngoing", True)])
            stats["stopped"] = len([r for r in records if not r.get("isOngoing", True)])
        return stats

    # ── 级联删除 ──

    def _do_cascade_delete(self, entity: str, record: dict) -> dict:
        """执行级联删除，返回各实体删除计数"""
        counts = {}
        patient_id = record.get("patientId", "")

        if entity == "patients":
            targets = ["diseases", "exams", "medications", "hospitalizations", "tasks", "events"]
            if os.path.exists(self._filepath("timeline")):
                targets.append("timeline")
            for target in targets:
                try:
                    with self._file_lock(target):
                        recs = self._read_file(target)
                        before = len(recs)
                        recs = [r for r in recs if r.get("patientId") != patient_id]
                        counts[target] = before - len(recs)
                        self._write_file(target, recs)
                except Exception:
                    counts[target] = -1  # 失败

        elif entity == "hospitalizations":
            hid = record.get("id", "")
            # 清理引用
            for ref_entity in ["exams", "diseases"]:
                try:
                    with self._file_lock(ref_entity):
                        recs = self._read_file(ref_entity)
                        modified = 0
                        for r in recs:
                            if r.get("relatedHospitalizationId") == hid:
                                del r["relatedHospitalizationId"]
                                modified += 1
                            if ref_entity == "diseases":
                                for ep in r.get("episodes", []):
                                    if ep.get("hospitalizationId") == hid:
                                        ep["hospitalizationId"] = ""
                                        modified += 1
                        if modified:
                            self._write_file(ref_entity, recs)
                        counts[f"{ref_entity}_refs_cleared"] = modified
                except Exception:
                    pass

        return counts

    # ── 后置钩子 ──

    def _run_post_hooks(self, action: str, entity: str, record: dict) -> list:
        """执行后置钩子，返回触发的钩子列表"""
        hooks = []
        patient_id = record.get("patientId", "")

        # 触发聚合
        trigger_entities = {"exams", "medications", "hospitalizations", "diseases", "tasks"}
        if entity in trigger_entities and patient_id:
            self._trigger_aggregate(patient_id)
            hooks.append(f"aggregate_timeline({patient_id})")

        # 同步 events.json
        if entity in trigger_entities and action == "create" and patient_id:
            self._trigger_events_sync()
            hooks.append("events_sync")

        return hooks

    def _trigger_aggregate(self, patient_id: str):
        """异步触发时间轴聚合"""
        import subprocess
        try:
            script = os.path.join(SCRIPT_DIR, "aggregate_timeline.py")
            subprocess.Popen(
                [sys.executable, script, patient_id, "--data-dir", self.data_dir],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    def _trigger_events_sync(self):
        """同步 events.json（全量重建）"""
        self._rebuild_events_from_timeline()

    def _rebuild_events_from_timeline(self):
        """从 timeline.json 重建 events.json"""
        timeline_path = self._filepath("timeline")
        if not os.path.exists(timeline_path):
            return
        try:
            with open(timeline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            timelines = data if isinstance(data, list) else [data]
            events = []
            for tl in timelines:
                patient_id = tl.get("patientId", "")
                for ev in tl.get("events", []):
                    event = dict(ev)
                    event["patientId"] = patient_id
                    event["createdAt"] = tl.get("generatedAt", "")
                    event["updatedAt"] = tl.get("generatedAt", "")
                    events.append(event)
            with open(self._filepath("events"), "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 工具 ──

    def _detect_changes(self, before: dict, after: dict) -> list:
        changes = []
        for key in after:
            if key in before:
                if json.dumps(before[key], sort_keys=True, default=str) != \
                   json.dumps(after[key], sort_keys=True, default=str):
                    changes.append(key)
            else:
                changes.append(key)
        return changes


# ============================================================
# CLI 入口
# ============================================================

def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <entity> <action> [args...]")
        print(f"实体: {', '.join(sorted(ENTITIES))}")
        print(f"动作: create | get | update | delete | query")
        print(f"")
        print(f"示例:")
        print(f"  {sys.argv[0]} patients create '{{\"name\":\"张三\",\"gender\":\"male\",\"birthDate\":\"1980-03-15\"}}'")
        print(f"  {sys.argv[0]} patients get <uuid>")
        print(f"  {sys.argv[0]} events query '{{\"patientId\":\"uuid\",\"eventType\":\"surgery\"}}'")
        sys.exit(1)

    entity = sys.argv[1]
    action = sys.argv[2]
    data_dir = SCHEMA_DIR

    # 解析 --data-dir
    extra_args = sys.argv[3:]
    filtered_args = []
    for i, arg in enumerate(extra_args):
        if arg == "--data-dir" and i + 1 < len(extra_args):
            data_dir = extra_args[i + 1]
        else:
            filtered_args.append(arg)
    args = filtered_args

    mm = MemoryManager(data_dir)

    try:
        if action == "create":
            if not args:
                print("用法: memory_manager.py <entity> create '<json>'")
                sys.exit(1)
            data = json.loads(args[0])
            result = mm.createRecord(entity, data)
            print_json(result)

        elif action == "get":
            if not args:
                print("用法: memory_manager.py <entity> get <id>")
                sys.exit(1)
            result = mm.getRecord(entity, args[0])
            print_json(result)

        elif action == "update":
            if len(args) < 2:
                print("用法: memory_manager.py <entity> update <id> '<updates_json>' [--merge true|false]")
                sys.exit(1)
            record_id = args[0]
            updates = json.loads(args[1])
            merge = "--no-merge" not in args
            result = mm.updateRecord(entity, record_id, updates, merge=merge)
            print_json(result)

        elif action == "delete":
            if not args:
                print("用法: memory_manager.py <entity> delete <id> [--no-cascade]")
                sys.exit(1)
            cascade = "--no-cascade" not in args
            result = mm.deleteRecord(entity, args[0], cascade=cascade)
            print_json(result)

        elif action == "query":
            filters = json.loads(args[0]) if args else {}
            limit = 100
            offset = 0
            if "--limit" in args:
                limit = int(args[args.index("--limit") + 1])
            if "--offset" in args:
                offset = int(args[args.index("--offset") + 1])
            result = mm.queryRecords(entity, filters, limit=limit, offset=offset)
            print_json(result)

        else:
            print(f"未知动作: {action} (可选: create, get, update, delete, query)")
            sys.exit(1)

    except (EntityNotFoundError, RecordNotFoundError, ValidationError,
            FieldLockedError, FileLockError, QueryError, ReadOnlyEntityError) as e:
        print_json({"success": False, "error": {"type": type(e).__name__, "message": str(e)}})
        sys.exit(1)
    except json.JSONDecodeError as e:
        print_json({"success": False, "error": {"type": "JSONParseError", "message": str(e)}})
        sys.exit(1)


if __name__ == "__main__":
    main()

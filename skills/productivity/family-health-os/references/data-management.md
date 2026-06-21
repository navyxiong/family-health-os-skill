# Data Management Reference

## Directory Structure

```
<profile-root>/
├── memory/
│   ├── schemas/        ← JSON Schema 定义 (draft-07，仅结构)
│   └── data/           ← 实际数据 (JSON 数组格式)
├── skills/
│   └── productivity/
│       └── family-health-os/
│           └── scripts/ ← 所有脚本
```

## Path Resolution

所有脚本从 `scripts/` 目录出发，到 `memory/data/` 需要 4 级 `..`：

```
scripts/
→ family-health-os (skill name dir)
→ productivity
→ skills
→ family-health-os (profile root) ← 到这里 4 级
→ memory/data/
```

**代码惯例：**
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "memory", "data")
```

**验证方法：**
```python
import os
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "memory", "data")
assert os.path.exists(DATA_DIR), f"DATA_DIR not found: {DATA_DIR}"
```

## File Lock Mechanism

所有 CRUD 操作通过 `memory_manager.py` 的统一文件锁机制：

```python
def _file_lock(self, entity):
    lock_path = self._filepath(entity) + ".lock"
    fd = open(lock_path, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # ... 操作 ...
    fcntl.flock(fd, fcntl.LOCK_UN)
```

| 属性 | 值 |
|------|------|
| 锁类型 | `fcntl.LOCK_EX` (排他锁) |
| 锁文件 | `<entity>.json.lock` |
| 超时 | 5 秒 |
| 死锁预防 | 按文件名排序获取锁 |

## Data File Format

**标准数组格式（所有原始数据表）：**
```json
[
  { "id": "uuid", "patientId": "uuid", ... },
  { "id": "uuid", "patientId": "uuid", ... }
]
```

**timeline.json 特殊格式（单对象 dict 包装）：**
```json
{
  "timeline": {
    "id": "uuid",
    "patientId": "uuid",
    "events": [...],
    ...
  }
}
```

**tool_layer.py 的 `_load()` 必须同时处理两种格式：**

```python
def _load(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Handle {"timeline": {...}} wrapper
        if "timeline" in data:
            return [data["timeline"]]
        # Single object with id/patientId
        if data.get("id") or data.get("patientId"):
            return [data]
    return []
```

## Field Name Consistency Check

**exams.json items 字段命名约定：**

| 用途 | 字段名 | 说明 |
|------|--------|------|
| 检查项名称 | `itemName` | ✅ 标准名 |
| 检查项名称 | `name` | ❌ 已废弃，保留 fallback 兼容 |
| 检查值 | `value` | ✅ |
| 单位 | `unit` | ✅ |
| 参考范围 | `referenceLow` / `referenceHigh` | ✅ |
| 异常标记 | `flag` | `normal / high / low / criticalHigh / criticalLow / abnormal` |
| 展示符号 | `displayFlag` | `↑` `↓` `↑↑` `↓↓` |

**聚合引擎兼容性写法：**
```python
item_name = item.get('itemName') or item.get('name', '')
```

## Write Hook Chain

```
createRecord("exams", data)
  ├── file lock
  ├── write to exams.json
  ├── file unlock
  └── post-hooks:
       ├── aggregate_timeline(patientId)  ← 异步 subprocess.Popen
       └── events_sync                   ← 全量从 timeline 摊平
```

**注意：** aggregate_timeline.py 输出到 stdout，**不自动写入文件**。必须通过 shell 重定向保存：
```bash
python3 scripts/aggregate_timeline.py <patientId> > memory/data/timeline.json
```

## CRUD 校验规则速查

| 实体 | 必填字段 | 枚举校验 |
|------|---------|---------|
| patients | name, gender, birthDate | gender ∈ {male, female, other} |
| diseases | patientId, diseaseName, diagnosedDate, status | status ∈ 6种；severity ∈ 4种 |
| exams | patientId, examDate, examType, items | examType ∈ 21种 |
| medications | patientId, medicationName, startDate | dosageForm ∈ 10种；route ∈ 12种 |
| hospitalizations | patientId, admissionDate, hospital, department, admittingDiagnosis | admissionType ∈ 4种；dischargeStatus ∈ 7种 |
| tasks | patientId, taskType, title, dueDate | taskType ∈ 16种；status ∈ 6种 |
| events | patientId, eventType, date | eventType ∈ 29种；severity ∈ 4种 |
| timeline | — | 只读，不允许直接 CRUD |

## Cascade Deletion

| 删除目标 | 级联影响 |
|---------|---------|
| patients | 全部关联表: diseases, exams, medications, hospitalizations, tasks, timeline, events |
| hospitalizations | exams.relatedHospitalizationId 清除；diseases.episodes[].hospitalizationId 清除 |
| diseases/exams/medications | 仅清理 timeline/events 中的引用标记 |

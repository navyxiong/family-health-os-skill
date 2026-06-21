# Memory Manager V1

**职责：** 统一管理 Family Health OS 所有数据文件的 CRUD + 查询操作。
**架构位置：** Layer 0.5 — 原始数据文件之上的统一访问层。

```
                     ┌─────────────────────────────────────┐
                     │    上层消费者                        │
                     │  Report Analyzer · Timeline Builder  │
                     │  Summary Generator · User Queries    │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │     Memory Manager V1                │
                     │     memory_manager.py                │
                     │                                     │
                     │  createRecord / updateRecord         │
                     │  deleteRecord / getRecord            │
                     │  queryRecords                        │
                     │                                     │
                     │  + 文件锁 · Schema校验 · 级联        │
                     │  + 后置钩子 · 时间戳 · 事件发布       │
                     └──────┬──────────┬──────────┬────────┘
                            │          │          │
               ┌────────────┘          │          └────────────┐
               ▼                       ▼                       ▼
     ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
     │ 原始数据文件       │   │ 聚合数据          │   │ 事件查询        │
     │ patients.json     │   │ timeline.json    │   │ events.json     │
     │ diseases.json     │   │                  │   │ (可查询视图)     │
     │ exams.json        │   │                  │   │                 │
     │ medications.json  │   │                  │   │                 │
     │ hospitalizations  │   │                  │   │                 │
     │ tasks.json        │   │                  │   │                 │
     └─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## 1. 8 个数据文件

| # | 文件 | 类型 | 角色 | 主键 | 必填字段 |
|---|------|------|------|------|---------|
| 1 | `patients.json` | 原始 | 患者档案 | `id` | name, gender, birthDate |
| 2 | `diseases.json` | 原始 | 疾病档案 | `id` | patientId, diseaseName, diagnosedDate, status |
| 3 | `exams.json` | 原始 | 检查报告 | `id` | patientId, examDate, examType, items |
| 4 | `medications.json` | 原始 | 用药记录 | `id` | patientId, medicationName, startDate |
| 5 | `hospitalizations.json` | 原始 | 住院档案 | `id` | patientId, admissionDate, hospital, department, admittingDiagnosis |
| 6 | `tasks.json` | 原始 | 任务提醒 | `id` | patientId, taskType, title, dueDate |
| 7 | `timeline.json` | 聚合 | 时间轴 | `patientId` | patientId, events |
| 8 | `events.json` | 查询 | 可查询事件视图 | `eventId` | patientId, eventType, date |

### 1.1 events.json — 新增文件

`events.json` 是 `timeline.json` 的扁平化可查询版本，专为 queryRecords 优化：

**设计目的**：timeline.json 按 patientId 索引（一个患者一条），events.json 将事件摊平为独立记录，支持跨患者查询、按任意字段过滤。

```json
[
  {
    "eventId": "evt-exam-20250613-a3f8",
    "patientId": "550e8400-e29b-41d4-a716-446655440000",
    "date": "2025-06-13T09:30:00",
    "eventType": "exam_result",
    "category": "diagnostic",
    "title": "检查结果：血常规",
    "description": "白细胞计数：11.2×10⁹/L↑",
    "severity": "warning",
    "isKeyEvent": false,
    "sourceType": "exam",
    "sourceId": "550e8400-e29b-41d4-a716-446655440001",
    "sourceDoctor": "张医生",
    "sourceInstitution": "北京大学第三医院",
    "tags": ["abnormal"],
    "affectedBodySite": "",
    "metadata": {
      "value": "11.2",
      "unit": "10⁹/L",
      "flag": "↑"
    },
    "relatedEntityIds": ["550e8400-e29b-41d4-a716-446655440002"],
    "createdAt": "2026-06-13T19:23:00",
    "updatedAt": "2026-06-13T19:23:00"
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eventId` | string | ✓ | 同 timeline.eventId |
| `patientId` | string(uuid) | ✓ | 关联患者 |
| `date` | date-time | ✓ | 事件发生时间 |
| `eventType` | enum | ✓ | 29种事件类型 |
| `category` | enum | | 9种分类 |
| `title` | string | ✓ | 事件标题 |
| `description` | string | | 详细描述 |
| `severity` | enum | | info/warning/critical/normal |
| `isKeyEvent` | boolean | | 是否里程碑事件 |
| `sourceType` | enum | | hospitalization/exam/medication/disease/task/manual |
| `sourceId` | string | | 来源数据记录ID |
| `sourceDoctor` | string | | 医生 |
| `sourceInstitution` | string | | 机构 |
| `tags` | string[] | | 标签 |
| `affectedBodySite` | string | | 部位 |
| `metadata` | object | | 扩展数据 |
| `relatedEntityIds` | string[] | | 关联记录ID |
| `createdAt` | date-time | | 记录创建时间 |
| `updatedAt` | date-time | | 记录更新时间 |

---

## 2. API 设计

### 2.1 统一接口

所有操作通过 `MemoryManager` 类统一调用：

```python
mm = MemoryManager(data_dir="memory/schemas/")

# CRUD
mm.createRecord("exams", record_data)
mm.getRecord("exams", record_id)
mm.updateRecord("exams", record_id, update_data)
mm.deleteRecord("exams", record_id)

# 查询
mm.queryRecords("exams", filters={...})
```

### 2.2 createRecord

**签名：**
```python
def createRecord(
    entity: str,         # 实体名（文件去掉.json）
    data: dict,          # 记录数据
    auto_id: bool = True # 是否自动生成UUID
) -> dict:
```

**行为：**
1. 校验 `entity` 是否合法（在支持的 8 个实体中）
2. 自动注入 `id`（UUID v4）+ `createdAt` + `updatedAt`
3. 验证必填字段是否存在（按实体规则）
4. 写入文件（追加）
5. 执行后置钩子（post-hooks）
6. 返回完整记录

**自动注入字段：**

| 实体 | 自动注入 | 必填校验 |
|------|---------|---------|
| patients | id, createdAt, updatedAt | name, gender, birthDate |
| diseases | id, createdAt, updatedAt | patientId, diseaseName, diagnosedDate, status |
| exams | id, createdAt, updatedAt | patientId, examDate, examType, items |
| medications | id, createdAt, updatedAt | patientId, medicationName, startDate |
| hospitalizations | id, createdAt, updatedAt | patientId, admissionDate, hospital, department, admittingDiagnosis |
| tasks | id, createdAt, updatedAt | patientId, taskType, title, dueDate |
| timeline | — | 禁止直接创建（仅由聚合引擎写入） |
| events | eventId, createdAt, updatedAt | patientId, eventType, date |

**返回示例：**
```json
{
  "success": true,
  "entity": "exams",
  "record": { /* 完整写入记录 */ },
  "hooks": ["aggregate_timeline triggered"]
}
```

---

### 2.3 getRecord

**签名：**
```python
def getRecord(
    entity: str,    # 实体名
    record_id: str  # 记录ID
) -> dict:
```

**行为：**
1. 读取文件，按 `id` 查找
2. 不存在 → 返回 `None`
3. timeline 和 events 按 `patientId` 查找（因为一个患者一条）

**返回：**
```json
{
  "success": true,
  "entity": "exams",
  "record": { /* 完整记录或 null */ }
}
```

---

### 2.4 updateRecord

**签名：**
```python
def updateRecord(
    entity: str,       # 实体名
    record_id: str,    # 记录ID
    updates: dict,     # 要更新的字段
    merge: bool = True # True=合并, False=替换
) -> dict:
```

**行为：**
1. 查找记录，不存在 → 抛 `RecordNotFoundError`
2. `merge=True`（默认）：只更新传入的字段，保留其他字段
3. `merge=False`：用 `updates` 完全替换整条记录
4. 自动更新 `updatedAt` 为当前时间
5. 禁止修改 `id` 和 `patientId`
6. 写入后执行后置钩子

**返回：**
```json
{
  "success": true,
  "entity": "exams",
  "record_id": "uuid",
  "before": { /* 更新前 */ },
  "after": { /* 更新后 */ },
  "changed_fields": ["conclusion", "items[2].flag"],
  "hooks": ["aggregate_timeline triggered"]
}
```

---

### 2.5 deleteRecord

**签名：**
```python
def deleteRecord(
    entity: str,         # 实体名
    record_id: str,      # 记录ID
    cascade: bool = True # 是否级联删除关联数据
) -> dict:
```

**行为：**
1. 删除主记录
2. `cascade=True`：删除关联记录（见级联规则）
3. 触发后置钩子

**级联删除规则：**

| 删除实体 | 级联影响 |
|---------|---------|
| patients | → 该患者的所有 diseases / exams / medications / hospitalizations / tasks / timeline / events |
| diseases | → exams 中该 diseaseId 的条目（仅清除 relatedDiseaseIds 引用，不删记录） |
| hospitalizations | → 关联的 exams 清除 relatedHospitalizationId，关联的 diseases 清除 episode hospitalizationId |
| exam / medication / task | → 仅清理 timeline 和 events 中的引用标记 |
| timeline | → 同步清理 events.json 中对应事件 |
| events | → 不影响 timeline.json（events 是查询视图） |

**返回：**
```json
{
  "success": true,
  "entity": "patients",
  "deleted": {
    "primary": { "id": "uuid", "name": "张三" },
    "cascade": {
      "diseases": 3,
      "exams": 12,
      "medications": 5,
      "hospitalizations": 2,
      "tasks": 4,
      "timeline": 1,
      "events": 42
    }
  },
  "hooks": ["timeline rebuilt"]
}
```

---

### 2.6 queryRecords

**签名：**
```python
def queryRecords(
    entity: str,                          # 实体名
    filters: dict,                        # 过滤条件
    sort: str = "date",                   # 排序字段
    order: str = "desc",                  # asc / desc
    limit: int = 100,                     # 返回条数
    offset: int = 0                       # 分页偏移
) -> dict:
```

**filters 支持：**

| 过滤条件 | 类型 | 示例 | 说明 |
|---------|------|------|------|
| `patientId` | string | `"uuid"` | 精确匹配 |
| `patientIds` | list | `["uuid1","uuid2"]` | IN 查询 |
| `eventType` | string | `"surgery"` | 精确匹配事件类型 |
| `eventTypes` | list | `["surgery","admission"]` | IN 查询 |
| `category` | string | `"surgical"` | 分类过滤 |
| `startDate` | string(ISO) | `"2025-01-01"` | 起始日期 |
| `endDate` | string(ISO) | `"2025-12-31"` | 截止日期 |
| `severity` | string | `"critical"` | 严重度过滤 |
| `isKeyEvent` | boolean | `true` | 关键事件 |
| `sourceType` | string | `"hospitalization"` | 来源类型 |
| `sourceDoctor` | string | `"张医生"` | 医生名（模糊） |
| `sourceInstitution` | string | `"北京大学"` | 机构名（模糊） |
| `tags` | list | `["abnormal"]` | 标签包含（AND） |
| `search` | string | `"肺炎"` | 全文搜索 title+description |
| `status` | string | `"active"` | 状态（diseases/tasks 专用） |
| `examType` | string | `"ct"` | 检查类型（exams 专用） |
| `taskType` | string | `"followUp"` | 任务类型（tasks 专用） |

**查询目标文件路由：**

| 查询目标 | 实际读取的文件 | 说明 |
|---------|--------------|------|
| `patients` | patients.json | 直接读取 |
| `diseases` | diseases.json | 直接读取 |
| `exams` | exams.json | 直接读取 |
| `medications` | medications.json | 直接读取 |
| `hospitalizations` | hospitalizations.json | 直接读取 |
| `tasks` | tasks.json | 直接读取 |
| `timeline` | timeline.json | 直接读取（返回完整结构） |
| `events` | events.json | 扁平化事件，最佳查询性能 |
| `events`（回退） | timeline.json → 摊平 | 若 events.json 不存在则自动生成 |

**默认按事件类型查询规则：**
- `queryRecords("events", filters={"eventType": "surgery"})` → 读 events.json，按 eventType 过滤
- `queryRecords("events", filters={"patientId": "uuid", "startDate": "...", "endDate": "..."})` → 时间范围过滤

**返回：**
```json
{
  "success": true,
  "entity": "events",
  "total": 42,
  "limit": 100,
  "offset": 0,
  "records": [ /* 事件列表 */ ],
  "stats": {
    "byType": { "surgery": 2, "exam_result": 15, ... },
    "bySeverity": { "critical": 3, "warning": 8, "info": 31 }
  }
}
```

---

## 3. 数据流图

### 3.1 写入流

```
上层调用
    │
    ▼
createRecord("exams", {...})
    │
    ├─→ ① 参数校验：entity 是否合法
    ├─→ ② 必填字段校验（按实体规则）
    ├─→ ③ 生成 id（UUID v4）
    ├─→ ④ 注入 createdAt / updatedAt
    ├─→ ⑤ 获取文件锁
    ├─→ ⑥ 读取现有数据（JSON parse）
    ├─→ ⑦ append 新记录
    ├─→ ⑧ 写回文件（JSON serialize）
    ├─→ ⑨ 释放文件锁
    │
    └─→ ⑩ 后置钩子执行
         ├── exams/create → aggregate_timeline(<patientId>)
         ├── exams/create → events.json 同步插入
         └── exams/create → 日志记录
```

### 3.2 更新流

```
updateRecord("diseases", "uuid", {"status": "controlled"})
    │
    ├─→ ① 查找记录 → 不存在则抛 RecordNotFoundError
    ├─→ ② 合并/替换字段
    ├─→ ③ 禁止修改 id / patientId
    ├─→ ④ 更新 updatedAt
    ├─→ ⑤ 获取文件锁 → 写入 → 释放锁
    │
    └─→ ⑥ 后置钩子
         ├── diseases/update → aggregate_timeline(<patientId>)
         ├── diseases/update → events.json 同步更新引用事件
         └── diseases/update → 日志
```

### 3.3 删除流

```
deleteRecord("patients", "uuid", cascade=True)
    │
    ├─→ ① 查找记录
    ├─→ ② cascade=True → 扫描所有文件找出关联记录
    │       ┌────────────────────────────────────────────┐
    │       │ 级联扫描                                     │
    │       │ diseases  WHERE patientId = target          │
    │       │ exams     WHERE patientId = target          │
    │       │ medications WHERE patientId = target        │
    │       │ hospitalizations WHERE patientId = target   │
    │       │ tasks     WHERE patientId = target          │
    │       │ timeline  WHERE patientId = target          │
    │       │ events    WHERE patientId = target          │
    │       └────────────────────────────────────────────┘
    ├─→ ③ 逐文件加锁 → 删除记录 → 释放锁
    └─→ ④ 后置钩子：日志
```

### 3.4 查询流

```
queryRecords("events", filters={
    "patientId": "uuid",
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "eventType": "surgery"
})
    │
    ├─→ ① 确定目标文件（events → events.json）
    ├─→ ② 文件存在？ → 是：直接读取
    │                 └→ 否：从 timeline.json 摊平生成
    ├─→ ③ 应用过滤器链
    │       filter_by_patientId() → filter_by_date() →
    │       filter_by_eventType() → ...
    ├─→ ④ 排序 → 分页 → 统计
    └─→ ⑤ 返回结果
```

---

## 4. 错误处理规则

### 4.1 错误类型

| 错误类型 | 触发条件 | HTTP类比 | 示例消息 |
|---------|---------|---------|---------|
| `EntityNotFoundError` | entity 不存在 | 404 | `"Entity 'xxx' not found. Supported: patients, diseases, exams, medications, hospitalizations, tasks, timeline, events"` |
| `RecordNotFoundError` | record_id 不存在 | 404 | `"Record 'uuid' not found in exams"` |
| `ValidationError` | 必填字段缺失/格式错误 | 422 | `"Missing required field(s): patientId, examDate"` |
| `FieldLockedError` | 尝试修改 id/patientId | 403 | `"Field 'id' is locked and cannot be modified"` |
| `FileLockError` | 文件被其他进程锁定 | 409 | `"File exams.json is locked by another process"` |
| `CascadeError` | 级联操作部分失败 | 500 | `"Cascade delete partially failed on diseases: timeout"` |
| `QueryError` | 过滤条件无效 | 400 | `"Invalid filter: unknownField. Supported filters: patientId, eventType, ..."` |

### 4.2 校验规则

**通用校验（所有实体）：**
- `id` 必须是 UUID v4 格式（如果传入）
- `patientId` 必须是 UUID v4 格式
- 日期字段必须是 ISO 8601（`YYYY-MM-DD` 或 `YYYY-MM-DDTHH:mm:ss`）
- 禁止传入 `createdAt` / `updatedAt`（由系统自动生成）

**按实体校验：**

| 实体 | 额外校验 |
|------|---------|
| patients | gender ∈ {male, female, other}；birthDate 必须为有效日期 |
| diseases | status ∈ {active, remission, controlled, resolved, recovered, chronic}；severity ∈ {mild, moderate, severe, critical} |
| exams | examType 必须为已知类型（ct/cta/ultrasound/pathology/bloodTest...）；items 至少 1 条 |
| medications | dosageForm ∈ 已知剂型枚举；route ∈ 已知途径枚举 |
| hospitalizations | admissionDate 必须 ≤ dischargeDate（如果提供）；admissionType ∈ 已知类型 |
| tasks | taskType ∈ 16 种已知类型；status ∈ {pending, inProgress, completed, cancelled, overdue, deferred} |
| timeline | 禁止直接创建/修改（仅由聚合引擎写入） |
| events | eventType ∈ 29 种已知类型；category 从 eventType 自动推断 |

### 4.3 错误返回格式

```json
{
  "success": false,
  "error": {
    "type": "ValidationError",
    "message": "Missing required field(s): patientId, examDate",
    "details": {
      "missing_fields": ["patientId", "examDate"],
      "entity": "exams"
    }
  }
}
```

---

## 5. 冲突处理规则

### 5.1 文件级锁

由于底层使用 JSON 文件，不支持事务。冲突通过**文件锁 (file lock)** 解决：

```python
import fcntl  # Unix
# 或使用 portalocker（跨平台）

def with_file_lock(filepath, timeout=5):
    """获取文件锁，timeout秒后超时"""
    lockfile = filepath + ".lock"
    fd = open(lockfile, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # 锁获取成功
        yield
    except IOError:
        raise FileLockError(f"File {filepath} is locked")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
```

**锁粒度：** 每个文件独立锁（细粒度）。
**写操作序列：** 读取 → 加锁 → 修改 → 写回 → 解锁。
**超时：** 5 秒后抛 `FileLockError`。

### 5.2 写冲突时序

```
进程A: read exams.json  →  [锁获取]  →  append → write → [释放锁]
进程B:                     [等待锁]                           →  read → write
```

如果进程 B 等待超过 5 秒 → 抛 `FileLockError`。

### 5.3 级联操作中的锁

级联删除/更新需要按固定顺序获取锁，避免死锁：

```
锁顺序（按文件名排序）：
1. diseases.json.lock
2. events.json.lock
3. exams.json.lock
4. hospitalizations.json.lock
5. medications.json.lock
6. patients.json.lock
7. tasks.json.lock
8. timeline.json.lock
```

所有级联操作必须按此顺序获取锁，获取失败则释放已持有的锁并重试。

### 5.4 部分失败回滚

当级联操作部分失败时（如删除了 5 个文件中的 3 个后第 4 个失败）：

```python
def delete_with_rollback(self, entity, record_id, cascade=True):
    completed = []
    try:
        for action in cascade_actions:
            action.execute()
            completed.append(action)
    except Exception as e:
        # 回滚已执行的操作
        for action in reversed(completed):
            try:
                action.rollback()
            except Exception:
                pass  # 记录日志但继续
        raise CascadeError(f"Operation rolled back: {e}")
```

**回滚日志：** 每次写操作前记录 `before` 快照，回滚时还原。

---

## 6. 后置钩子系统

写操作后自动触发：

| 写操作 | 触发钩子 |
|--------|---------|
| patients/create | 无 |
| patients/update | 无 |
| patients/delete | cascade 清理 |
| **exams/create** | → aggregate_timeline(patientId) + events.json 同步 |
| **exams/update** | → aggregate_timeline(patientId) + events.json 同步更新 |
| **exams/delete** | → aggregate_timeline(patientId) + events.json 同步删除 |
| **diseases/create** | → events.json 同步（diagnosis 事件） |
| **diseases/update** | → events.json 同步 |
| **diseases/delete** | → 清理关联引用 |
| **medications/create** | → aggregate_timeline(patientId) |
| **medications/update** | → aggregate_timeline(patientId) |
| **medications/delete** | → aggregate_timeline(patientId) |
| **hospitalizations/create** | → aggregate_timeline(patientId) |
| **hospitalizations/update** | → aggregate_timeline(patientId) |
| **hospitalizations/delete** | → aggregate_timeline(patientId) + 清理引用 |
| **tasks/create** | → aggregate_timeline(patientId) |
| **tasks/update** | → aggregate_timeline(patientId) |
| **tasks/delete** | → aggregate_timeline(patientId) |
| **timeline/** | 禁止直接写 |
| **events/create** | 无（events 是查询视图） |
| **events/update** | 无 |
| **events/delete** | 无 |

---

## 7. 文件格式规范

### 7.1 存储格式

所有 JSON 文件统一使用以下格式：

```python
# 写入参数
json.dump(data, f, ensure_ascii=False, indent=2)
```

### 7.2 patients.json 格式

```json
[
  {
    "id": "uuid",
    "name": "张三",
    "gender": "male",
    ...其他字段...
    "createdAt": "2026-01-01T00:00:00",
    "updatedAt": "2026-06-13T19:23:00"
  }
]
```

### 7.3 timeline.json 格式

```json
[
  {
    "id": "uuid",
    "patientId": "uuid",
    "generatedAt": "...",
    "generatedBy": "auto",
    "events": [...],
    "monthlyGroups": {...},
    "summary": "...",
    "eventCount": 42,
    "dateRange": {...},
    "version": 1
  }
]
```

### 7.4 events.json 格式（新增）

```json
[
  {
    "eventId": "evt-exam-20250613-a3f8",
    "patientId": "uuid",
    "date": "2025-06-13T09:30:00",
    "eventType": "exam_result",
    "category": "diagnostic",
    "title": "...",
    ...其他字段...
    "createdAt": "...",
    "updatedAt": "..."
  }
]
```

---

## 8. 前端使用示例

```python
from memory_manager import MemoryManager

mm = MemoryManager(data_dir="memory/schemas/")

# 创建患者
patient = mm.createRecord("patients", {
    "name": "张三",
    "gender": "male",
    "birthDate": "1980-03-15",
    "bloodType": "A+",
})

# 创建检查记录
exam = mm.createRecord("exams", {
    "patientId": patient["record"]["id"],
    "examDate": "2026-06-13T09:00:00",
    "examType": "ct",
    "examName": "胸部CT平扫",
    "hospital": {"name": "北京大学第三医院", "level": "tertiary"},
    "items": [
        {"name": "肺部", "value": "右肺上叶磨玻璃结节",
         "flag": "abnormal", "displayFlag": "↑"}
    ],
    "conclusion": "右肺上叶磨玻璃结节，建议随访",
})
# → 自动触发 aggregate_timeline + events 同步

# 查询最近的手术事件
results = mm.queryRecords("events", filters={
    "patientId": patient["record"]["id"],
    "eventType": "surgery",
    "startDate": "2025-01-01",
    "endDate": "2026-12-31",
})

# 更新用药记录
mm.updateRecord("medications", med_id, {
    "dosage": {"amount": 1000, "unit": "mg"},
    "endDate": "2026-07-01",
    "reasonForStop": "剂量调整",
})

# 删除疾病记录（含级联）
mm.deleteRecord("diseases", disease_id, cascade=True)

# 删除患者（含全级联）
result = mm.deleteRecord("patients", patient_id, cascade=True)
print(f"已删除 {result['deleted']['cascade']['exams']} 条检查记录")
```

---

## 9. 与已有脚本的集成

```python
# memory_manager.py 作为统一入口，内部调用已有脚本

class MemoryManager:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    def _trigger_aggregate(self, patient_id):
        """触发时间轴聚合"""
        import subprocess
        script = os.path.join(SCRIPT_DIR, "aggregate_timeline.py")
        subprocess.Popen(
            [sys.executable, script, patient_id, "--data-dir", self.data_dir]
        )

    def _sync_events(self, action, event_data):
        """同步 events.json"""
        # 增量维护 events.json，不做全量重建
        events_path = os.path.join(self.data_dir, "events.json")
        with self._file_lock(events_path):
            events = self._read_file(events_path) or []
            if action == "create":
                events.append(event_data)
            elif action == "update":
                self._update_in_list(events, "eventId", event_data)
            elif action == "delete":
                events = [e for e in events if e["eventId"] != event_data["eventId"]]
            self._write_file(events_path, events)
```

---

## 10. 限制与注意事项

| 限制 | 说明 |
|------|------|
| **无真实事务** | JSON 文件不支持 ACID 事务。文件锁减轻但无法完全避免并发问题 |
| **events.json 维护成本** | 每次写操作需同步更新 events.json，增加 IO 开销 |
| **大文件性能** | 文件过大时（>100MB），全量读取+写回模式会有性能瓶颈 |
| **回滚能力有限** | 仅记录 `before` 快照，不支持复杂事务回滚 |
| **不支持并发写同一条** | 同时修改同一条记录，后写者覆盖前者（无冲突检测） |

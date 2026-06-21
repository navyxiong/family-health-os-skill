# 家庭健康档案管家 — Hermes Agent Skill

> 让 Hermes Agent 变身**家庭终身医疗档案管理员**。结构化信息管理枢纽，**不做诊断或治疗建议**。

[English](README.md) · [更新日志](CHANGELOG.md) · [快速开始](#快速开始) · [架构](#架构) · [常见问题](#常见问题)

---

## 解决什么问题

家有老人/慢病患者，最大痛点不是缺一个 App，而是**信息散落**：
- 化验单塞满抽屉
- 住院病程记不住
- 不同医院、不同医生说法不同
- 想给子女交代病史时大脑一片空白

这个 skill 让你的 Hermes Agent 变成一个**沉默的档案员**：
- 看见病历图片 → 自动 OCR + 结构化入库
- 看见化验数值 → 自动对比参考范围标 ↑↓
- 看见住院记录 → 自动聚合到时间轴
- 看见"该复查了" → 自动设置提醒
- 看见"奶奶最近怎么样" → 自动生成 8 节结构化叙事

---

## 快速开始

### 一行安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/navyxiong/family-health-os-skill/main/install.sh | bash
```

### 手动安装

```bash
# 1. 确认已装 Hermes Agent（≥0.5）
#    https://hermes-agent.nousresearch.com/docs

# 2. 克隆本仓库
git clone https://github.com/navyxiong/family-health-os-skill.git

# 3. 复制到你的 profile
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE_NAME="${1:-family-health-os}"
mkdir -p "$HERMES_HOME/profiles/$PROFILE_NAME/skills"
cp -R family-health-os-skill/skills/. "$HERMES_HOME/profiles/$PROFILE_NAME/skills/"

# 4. 创建空的数据目录
mkdir -p "$HERMES_HOME/profiles/$PROFILE_NAME/memory/data"

# 5. 激活 profile
hermes profile use $PROFILE_NAME
```

### 第一次使用

发给你的 agent：

> *"给奶奶建一份档案：姓名乐天福，女，1948年5月30日出生，过敏青霉素，家族高血压。"*

agent 会自动建档，输出：

```
已录入。患者档案 | 乐天福 | 1事件
```

---

## 核心能力

### 1. 五大基础任务（开箱即用）

| 任务 | 触发词 | 实际动作 |
|------|--------|----------|
| 成员管理 | "建档"/"查档案"/"改档案" | 增/查/改 patients.json |
| 检查记录 | "录化验"/"标记异常" | exams.json + flag 自动计算 |
| 住院跟踪 | "入院"/"病程"/"出院" | 完整 5 环节住院档案 |
| 提醒任务 | "该复查了"/"每月监测" | tasks.json + 重复规则 |
| 摘要生成 | "病史摘要"/"会诊摘要" | 4 种叙事模板 |

### 2. 报告图片自动录入

发任意病历图片给 agent（化验单 / CT 报告 / 出院小结 / 病理报告），agent 会：
1. `vision_analyze` 提取文字
2. 解析为结构化 JSON
3. 校验后写入对应表
4. 自动触发时间轴聚合
5. 一行输出确认

### 3. 七技能自动路由

| 你说 | agent 自动调用 | 输出 |
|------|---------------|------|
| "看看血脂趋势" | health-trend-analyzer | 趋势图 + 异常提示 |
| "我们家有遗传风险吗" | family-health-analyzer | 风险评分 + 家谱 |
| "PE 最新研究" | pubmed-search | 论文清单 |
| "睡眠怎么样" | sleep-analyzer | 睡眠质量报告 |
| "饮食评估" | nutrition-analyzer | 营养缺口分析 |
| "锻炼记录" | fitness-analyzer | 训练进展 |
| 描述症状 | medical-entity-extractor | 实体抽取 → 写入档案 |

### 4. 零确认（强制规则）

**录入了就是录入了**，不会反复问"是否确认"。所有操作静默执行，最后只输出一行关键信息：

```
已录入。血常规 2026-05-26 | 湘雅医院老年医学科 | 52事件
```

---

## 架构

五层数据流：

```
Schema 定义层    memory/schemas/*.json   7 个 JSON Schema
      ↓
数据管理层       scripts/memory_manager.py  CRUD + 文件锁 + 校验
      ↓
原始数据层       memory/data/*.json         8 个实体
      ↓
聚合层           scripts/aggregate_timeline.py  → timeline.json
      ↓
查询渲染层       scripts/build_timeline.py        3 种视图
      ↓
摘要合成层       scripts/generate_summary.py      4 种叙事
```

Agent 通过 `scripts/tool_layer.py` 这个语义化 API 调用，**不用直接操作 JSON 文件**。

---

## 目录结构

```
family-health-os-skill/
├── README.md              # 英文门面
├── README.zh-CN.md        # 本文件（中文详细）
├── LICENSE                # MIT + 医疗免责
├── CHANGELOG.md           # 版本变更
├── CONTRIBUTING.md        # 贡献指南
├── requirements.txt       # Python 依赖
├── install.sh             # 一键安装
├── skills/
│   └── productivity/
│       └── family-health-os/
│           ├── SKILL.md              # 必读：主入口
│           ├── scripts/              # 6 个 Python 引擎
│           │   ├── tool_layer.py          # 语义化 API（agent 调这个）
│           │   ├── memory_manager.py      # CRUD + 锁
│           │   ├── aggregate_timeline.py  # 聚合
│           │   ├── build_timeline.py      # 查询/渲染
│           │   ├── generate_summary.py    # 摘要合成
│           │   └── smoke_test.py          # 冒烟测试
│           ├── references/           # 8 篇深度文档
│           ├── workflows/            # 4 篇流程文档
│           ├── templates/            # 转院交接模板
│           └── docs/                 # event-schema 技术参考
└── examples/
    ├── basic-usage.md        # 3 个真实场景
    └── sample-data/          # 脱敏样本数据
```

---

## 数据格式

所有数据都是标准 JSON，无加密，无压缩。**`cat memory/data/patients.json` 就能直接读**。

### 患者档案示例
```json
{
  "id": "70520347-1234-5678-9abc-def012345678",
  "name": "乐天福",
  "gender": "female",
  "birthDate": "1948-05-30",
  "allergies": [
    {"allergen": "青霉素", "severity": "severe", "reaction": "皮疹"}
  ],
  "familyHistory": ["hypertension", "diabetes"]
}
```

### 检验报告示例
```json
{
  "id": "uuid-xxx",
  "patientId": "70520347-...",
  "examName": "血常规",
  "examDate": "2026-05-26",
  "institution": "湘雅医院老年医学科",
  "items": [
    {
      "itemName": "白细胞",
      "value": 12.5,
      "unit": "10^9/L",
      "referenceRange": "4-10",
      "flag": "high",
      "displayFlag": "↑"
    }
  ]
}
```

完整 Schema 见 `skills/productivity/family-health-os/references/schema-guide.md`。

---

## 常见问题

### Q1: 安装后 agent 不识别这个 skill？
**检查路径**：必须是 `~/.hermes/profiles/<profile>/skills/productivity/family-health-os/SKILL.md`，三层目录缺一不可。

### Q2: 写入时报 `FileNotFoundError`？
**手动建数据目录**：
```bash
mkdir -p ~/.hermes/profiles/<profile>/memory/data
```

### Q3: 写入时数据跑到了别的 profile？
**确认激活的 profile**：
```bash
hermes profile use family-health-os
```

### Q4: `timeline.json` 损坏（JSON 解析报错）？
**删除并重建**（timeline.json 是聚合产物，可重生成）：
```bash
rm ~/.hermes/profiles/<profile>/memory/data/timeline.json
```
然后给 agent 发任意一条指令，它会自动重新聚合。

### Q5: 体检报告怎么批量录入？
**直接拍照连发**给 agent，每张图片会静默入库，最后输出一行总结。

### Q6: 能不能多人共享一个 profile？
可以，但所有写操作需串行（file lock 保护）。建议**一个家庭一个 profile**，用 `familyHistory` 字段关联血缘。

### Q7: 数据会泄露吗？
不会。所有数据存在你本地，没有云同步。**只要你不 `git push`，数据就不会离开你的电脑**。

### Q8: 能不能导入医院 HIS 系统导出的 Excel？
可以。Excel → CSV → JSON 后用 `tool_layer.py` 的 `bulk_import` 接口（v1.4.0 规划中）。

---

## 医疗免责

本软件**不是医疗器械**。它不提供诊断、治疗、预后或临床决策支持。
所有存入的医疗信息须由具备资质的医疗专业人员审阅和行动。
详见 [LICENSE](LICENSE) 中的医疗免责声明。

---

## 贡献

欢迎贡献 schema 字段、工作流模板、新的分析技能。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

[MIT](LICENSE) © 2026 家庭健康档案管家贡献者

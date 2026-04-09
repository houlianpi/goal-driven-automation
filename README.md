# Goal-Driven Automation

> Agent-First Automation Pipeline: Goal → Plan IR → fsq-mac CLI → Evidence → Repair

## 🎯 项目定位

**这是什么：** Agent-First 自动化系统，人类定义目标，Agent 生成执行计划。

**这不是什么：** 传统的测试脚本集合或 BDD step 定义。

## 📊 当前状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0 | 🔄 进行中 | Reset baseline |
| Phase 1 | ⏳ 待开始 | Core schemas |
| Phase 2 | ⏳ 待开始 | Capability Registry |
| Phase 3 | ⏳ 待开始 | Compiler + Executor |
| Phase 4 | ⏳ 待开始 | Evidence Layer |
| Phase 5 | ⏳ 待开始 | Evaluator + Classifier |
| Phase 6 | ⏳ 待开始 | Repair/Replan Loop |
| Phase 7 | ⏳ 待开始 | Memory + Evolution |
| Phase 8 | ⏳ 待开始 | E2E Validation |
| Phase 9 | ⏳ 待开始 | Credible POC |

### 能力成熟度

| 能力 | 状态 | 说明 |
|------|------|------|
| Goal 定义 | 💡 Idea | Schema 待定义 |
| Plan IR | 💡 Idea | Schema 待定义 |
| Executor | 💡 Idea | 统一执行器待实现 |
| Evidence | 💡 Idea | 证据采集待实现 |

## 🏗️ 架构

```
Human Goal
  ↓
Goal Interpreter
  ↓
Plan IR
  ↓
Capability Compiler
  ↓
fsq-mac CLI
  ↓
Evidence Collector
  ↓
Evaluator / Repair Loop
  ↓
Human Review
```

## 📁 目录结构

```
goal-driven-automation/
├── docs/             # 文档
│   └── IMPLEMENTATION_PLAN.md
├── goals/            # 人类定义的目标 (YAML)
│   ├── schema.yaml   # Goal schema
│   └── examples/     # 示例目标
├── plans/            # Agent 生成的执行计划 (JSON)
│   ├── schema.json   # Plan IR schema
│   ├── generated/    # 生成的计划
│   └── templates/    # 计划模板
├── registry/         # Capability Registry
│   ├── actions.yaml  # Action 注册表
│   └── schema.yaml   # Registry schema
├── runs/             # 执行记录和证据 (gitignore)
├── memory/           # Memory 层
│   ├── cases/        # 可复用模式
│   └── rules/        # 稳定规则
├── src/              # 核心代码
│   ├── goal_interpreter/
│   ├── planner/
│   ├── compiler/
│   ├── executor/
│   ├── evaluator/
│   ├── repair/
│   └── schemas/
└── tests/            # 测试
```

## 🚀 快速开始

（Phase 8 完成后补充）

## 📖 文档

- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)

## 技术栈

- Python
- fsq-mac CLI
- Appium Mac2
- YAML (Goals)
- JSON (Plan IR, Evidence)

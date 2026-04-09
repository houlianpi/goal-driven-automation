# Goal-Driven Automation Plan

## Phase 0: 基础架构

### 目标
1. 定义 Plan IR Schema
2. 定义 Evidence Schema
3. 实现 Goal -> Plan 转换
4. 实现 Plan -> fsq-mac 执行

### 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Goal (自然语言)                       │
│  "在 Edge 浏览器中打开新标签页并导航到 github.com"        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Plan IR (JSON)                        │
│  {                                                       │
│    "goal": "...",                                        │
│    "steps": [                                            │
│      { "action": "launch", "params": {"app": "Edge"} }, │
│      { "action": "shortcut", "params": {"keys": ["command", "t"]} }, │
│      { "action": "type", "params": {"text": "github.com"} }, │
│      { "action": "shortcut", "params": {"keys": ["return"]} } │
│    ]                                                     │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│         Compiler -> Capability Registry -> fsq-mac CLI   │
│  launch   -> launch_app    -> mac app launch <bundle>    │
│  shortcut -> hotkey        -> mac input hotkey ...       │
│  type     -> type_text     -> mac input type ...         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Evidence (JSON)                       │
│  {                                                       │
│    "steps": [                                            │
│      { "status": "success", "screenshot": "..." },       │
│      { "status": "success", "screenshot": "..." },       │
│      ...                                                 │
│    ],                                                    │
│    "overall": "success"                                  │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Repair (如果失败)                     │
│  Agent 分析 Evidence，生成修复方案，重新执行             │
└─────────────────────────────────────────────────────────┘
```

## Phase 1: 核心功能

### 目标
1. 实现 Plan Executor
2. 实现 Evidence Collector
3. 实现基础 Repair 策略

## Phase 2: 高级功能

### 目标
1. 支持条件分支
2. 支持循环
3. 支持并行执行
4. 智能 Repair 策略

# Goal-Driven Automation

AI Agent 驱动的 macOS 自动化测试框架。

## 架构

```
Goal (自然语言目标)
    ↓
Plan IR (结构化计划)
    ↓
fsq-mac CLI (执行)
    ↓
Evidence (执行结果)
    ↓
Repair (自动修复)
```

## 目录结构

```
goal-driven-automation/
├── docs/           # 设计文档
├── schemas/        # JSON Schema 定义
├── src/            # 源代码
└── tests/          # 测试用例
```

## 团队

- **康夫** - 项目经理 (Claude Code)
- **Mattt** - 技术架构师 (Claude Code)
- **机器猫** - 开发者 (Codex)

## 相关项目

- [fsq-mac](https://github.com/houlianpi/fsq-mac) - Agent-first macOS automation CLI
- [fsq-test-pilot](https://github.com/houlianpi/fsq-test-pilot) - POC 验证项目

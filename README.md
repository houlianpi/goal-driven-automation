# Goal-Driven Automation

AI Agent 驱动的 macOS 自动化测试框架。

## 环境要求

- Python `3.13+`

## 安装

安装运行依赖：

```bash
pip install -e .
```

安装开发依赖：

```bash
pip install -e .[dev]
```

## 开发验证

运行全量测试：

```bash
pytest -q
```

执行一个 dry-run 示例：

```bash
python -m src.cli run "Open Edge and create new tab" --dry-run
```

如果 dry-run 命令失败，请将其视为单独的 CLI 问题进行记录；非主线 hygiene 工作默认不在这里修复 CLI 行为。

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

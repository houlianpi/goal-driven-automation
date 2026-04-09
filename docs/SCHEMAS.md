# Schemas 设计

## Plan IR Schema

定义 Goal 到执行计划的中间表示。

### 核心字段

| 字段 | 类型 | 描述 |
|------|------|------|
| goal | string | 原始目标（自然语言） |
| app | string | 目标应用 |
| steps | Step[] | 执行步骤列表 |
| metadata | object | 元数据 |

### Step 类型

| Action | 参数 | 描述 |
|--------|------|------|
| launch | app | 启动应用 |
| shortcut | keys | 发送快捷键 |
| type | text | 输入文本 |
| click | selector/coords | 点击元素 |
| wait | seconds/condition | 等待 |
| assert | condition | 断言验证 |

## Evidence Schema

记录执行结果和证据。

### 核心字段

| 字段 | 类型 | 描述 |
|------|------|------|
| planId | string | 关联的 Plan ID |
| steps | StepResult[] | 每步执行结果 |
| overall | string | 整体状态 |
| duration | number | 总耗时(ms) |

### StepResult 字段

| 字段 | 类型 | 描述 |
|------|------|------|
| index | number | 步骤索引 |
| status | string | success/failure/skipped |
| screenshot | string | 截图 base64 |
| error | string | 错误信息（如有） |
| duration | number | 步骤耗时(ms) |

## Repair Schema

记录修复策略和结果。

### 核心字段

| 字段 | 类型 | 描述 |
|------|------|------|
| evidenceId | string | 关联的 Evidence ID |
| failedStep | number | 失败步骤索引 |
| strategy | string | 修复策略 |
| newPlan | Plan | 修复后的计划 |
| result | string | 修复结果 |

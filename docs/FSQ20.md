FSQ 2.0 升级的一些探索和想法：

FSQ 2.0 升级主要目的： 更少的人参与，更多的AI自主。

然后有了这样一个架构：

```
Goal (自然语言目标) 主角: 人
    ↓
Plan IR (结构化计划) 主角: Agent
    ↓
Automation Tools (执行) 主角: Agent
    ↓
Evidence (执行结果) 主角: Agent
    ↓
Repair (自动修复) 主角: Agent
```

我主要调研的方式是：

```
Automation Tools (执行) 主角: Agent
    ↓
Evidence (执行结果) 主角: Agent
    ↓
Repair (自动修复) 主角: Agent
```

主要思路： 补齐 agent friendly 的能力，让Agent自己去干。

形式上来说主要有三种：

- MCP： FSQ 使用的主要方式， Appium 3.x 也支持了这种方式： https://appium.io/docs/en/3.1/guides/migrating-2-to-3/
- CLI： 主要参考 Playwright CLI : https://github.com/microsoft/playwright-cli
- 直接走协议： 主要参考  https://github.com/browser-use/browser-harness-js
- 视觉识别： 主要参考 https://github.com/web-infra-dev/midscene

感觉都差不多。都是让Agent来做。 需要扣一些细节。主要在这里： https://github.com/houlianpi/Android_Harness/blob/main/docs/agent-friendly-bilingual.md

--------------

一个对 Agent 友好的系统，不是由它使用 JSON、CLI 还是服务器来定义的。那些只是实现层面的选择。

真正的目标是让系统更容易被 Agent 使用，减少不确定性。

一个对 Agent 友好的系统能给模型带来：

- less guessing / 更少的猜测
- less ambiguity / 更少的歧义
- fewer formatting errors / 更少的格式错误
- easier next-step planning / 更容易规划下一步

这就是核心思想。


什么是 agent-friendly（UI 自动化）

  对 Agent 来说，好的自动化系统应满足：

  1. 可观测：状态是结构化的（DOM/AX tree/窗口树），不是只看截图。
  2. 可定位：优先语义定位（role/name/id），而不是坐标点。
  3. 可恢复：错误是机器可判定的（error code + retryable + next action）。
  4. 可重放：操作可记录/回放/对比（trace、snapshot、diff）。
  5. 可组合：命令接口稳定、参数明确、输出统一。

  为什么 Playwright / CDP 更 agent-friendly

  - Playwright
    - locator 语义强（role/name/text/testid）
    - auto-wait 减少时序抖动
    - trace/screenshot/video 证据链完整
    - 错误信息较结构化，便于 agent 决策
  - CDP
    - 协议层可编排（Runtime/DOM/Network/Input 等域）
    - 状态读取和操作都“可程序化”
    - 更容易做闭环：观察→决策→执行→验证

  为什么很多“client 型”UI 自动化不友好

  常见问题：

  - 强依赖本地驱动和环境状态（黑盒）
  - 输出偏人类日志，不是结构化结果
  - 大量坐标点击/图像匹配，语义信息弱
  - 错误语义不统一（重试策略难自动化）
  - 元素引用易失效但缺少标准恢复路径


AutoGenesis 的分析

| 维度 | 分数(0-2) | 结论 |
  |---|---:|---|
  | 语义定位能力 | 2 | 支持 ACCESSIBILITY_ID/NAME/ID/XPATH 等多策略，定位能力比纯坐标方案强 |
  | 结构化状态读取 | 2 | 工具返回有统一 status/data/error 结构，且支持 page source 摘要/文件输出 |
  | 错误码+恢复建议 | 1 | 有错误信息，但缺少标准化 error_code/retryable/next_action 契约 |
  | Trace/回放/差异 | 1 | 有执行流程与代码生成链路，但缺少独立 trace/replay/diff 体系 |
  | 幂等/可重试设计 | 1 | 文档/skill 强调重试，但主要靠上层流程约束，底层契约不够强 |
  | 输出一致性 | 2 | 两个 MCP server 都有 response_format 统一封装 |
  | 会话生命周期 | 2 | 有 session/app lifecycle（启动、关闭、连接管理） |
  | 跨平台一致性 | 2 | Windows/macOS/iOS/Android 全覆盖 |
  | 时序稳定机制 | 1 | 有 WebDriverWait，但也有固定 sleep，稳定性中等 |
  | 安全分级 | 0 | 未看到 SAFE/GUARDED/DANGEROUS 之类分级治理 |
  | **总分** | **14** | |






一些AI 分析的issues：
- https://github.com/houlianpi/fsq-mac/issues/11
- https://github.com/houlianpi/fsq-mac/issues/12
- https://github.com/houlianpi/goal-driven-automation/issues



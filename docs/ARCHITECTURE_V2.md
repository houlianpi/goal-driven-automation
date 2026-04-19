# GDA v2 架构设计

> 基于 Issue #49 和 #50，借鉴 Midscene.js 的架构重构

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  gda "goal"  |  gda record  |  gda run  |  gda fix         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Core Engine                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Planner │→ │Executor │→ │Recorder │→ │  Cache  │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│       ↑            │            │                           │
│       └────────────┴────────────┘                           │
│              Re-planning Loop                               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Action Layer (fsq-mac)                    │
│  Tap | Input | Hotkey | Launch | Assert | Screenshot       │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Case YAML 格式

```yaml
# cases/github/login.yaml
meta:
  goal: "登录 GitHub"
  app: "Safari"
  created: "2026-04-19T14:30:00Z"
  tags: ["auth", "smoke"]
  variables:
    - USERNAME
    - PASSWORD

steps:
  - action: launch
    target: com.apple.Safari
    
  - action: input
    target: "地址栏"
    value: "github.com"
    
  - action: tap
    target: "Sign in"
    
  - action: input
    target: "Username or email"
    value: "${USERNAME}"
    
  - action: input
    target: "Password"  
    value: "${PASSWORD}"
    
  - action: tap
    target: "Sign in"

postconditions:
  - assert: "contains"
    target: "window.title"
    value: "GitHub"
```

### 2. Action Space 定义

```python
# src/actions/action_space.py
ACTION_SPACE = [
    {
        "name": "launch",
        "description": "Launch an application",
        "params": {"target": "bundle_id"},
        "fsq_cmd": "mac app launch {target}"
    },
    {
        "name": "tap",
        "description": "Click/tap an element",
        "params": {"target": "element_description"},
        "fsq_cmd": "mac element click \"{target}\""
    },
    {
        "name": "input",
        "description": "Type text into an element",
        "params": {"target": "element", "value": "text"},
        "fsq_cmd": "mac element type \"{target}\" --text \"{value}\""
    },
    {
        "name": "hotkey",
        "description": "Press keyboard shortcut",
        "params": {"keys": "key_combo"},
        "fsq_cmd": "mac input hotkey \"{keys}\""
    },
    {
        "name": "assert",
        "description": "Verify a condition",
        "params": {"type": "assertion_type", "target": "element", "value": "expected"},
        "fsq_cmd": "mac assert {type} \"{target}\" \"{value}\""
    },
    {
        "name": "wait",
        "description": "Wait for condition or time",
        "params": {"target": "condition_or_ms"},
        "fsq_cmd": "mac wait {target}"
    }
]
```

### 3. Planning Loop

```python
# src/engine/planner.py
class PlanningLoop:
    def __init__(self, goal: str, max_cycles: int = 10):
        self.goal = goal
        self.max_cycles = max_cycles
        self.history = []  # Conversation history
        self.steps = []    # Recorded steps
        
    def run(self) -> CaseFile:
        cycle = 0
        done = False
        
        while not done and cycle < self.max_cycles:
            # 1. Get current state
            screenshot = self.capture_screenshot()
            ui_tree = self.get_accessibility_tree()
            
            # 2. Ask LLM for next action
            response = self.llm.plan(
                goal=self.goal,
                screenshot=screenshot,
                ui_tree=ui_tree,
                history=self.history[-5:],  # Last 5 turns
                action_space=ACTION_SPACE
            )
            
            # 3. Parse LLM response (XML format)
            action = self.parse_xml_response(response)
            
            # 4. Execute action
            result = self.executor.execute(action)
            
            # 5. Record step (边执行边记录)
            self.steps.append({
                "action": action.name,
                "target": action.target,
                "value": action.value,
                "result": result.status,
                "timestamp": now()
            })
            
            # 6. Update history
            self.history.append({
                "action": action,
                "result": result,
                "screenshot_summary": self.summarize_screenshot(screenshot)
            })
            
            # 7. Check completion
            if action.type == "done" or result.goal_achieved:
                done = True
            
            cycle += 1
        
        return self.to_case_yaml()
```

### 4. LLM XML Response Format

```xml
<response>
  <thought>用户想要登录 GitHub，当前在登录页面，需要点击 Sign in 按钮</thought>
  <log>Clicking Sign in button</log>
  <action>
    <type>tap</type>
    <target>Sign in</target>
  </action>
  <should_continue>true</should_continue>
</response>
```

### 5. Cache 机制

```python
# src/cache/case_cache.py
class CaseCache:
    """
    首次执行：LLM 规划 → 执行 → 存缓存
    再次执行：命中缓存 → 直接回放，跳过 LLM
    """
    
    def __init__(self, cache_dir: str = ".gda/cache"):
        self.cache_dir = Path(cache_dir)
        
    def get_cache_key(self, goal: str, app: str) -> str:
        return hashlib.md5(f"{goal}:{app}".encode()).hexdigest()
    
    def get(self, goal: str, app: str) -> Optional[CaseFile]:
        key = self.get_cache_key(goal, app)
        cache_file = self.cache_dir / f"{key}.yaml"
        if cache_file.exists():
            return CaseFile.load(cache_file)
        return None
    
    def put(self, goal: str, app: str, case: CaseFile):
        key = self.get_cache_key(goal, app)
        case.save(self.cache_dir / f"{key}.yaml")
```

### 6. CLI 命令

```bash
# P0: 即时执行
gda "打开 Safari 搜索天气"
gda "登录 GitHub"  # 自动生成 Case 到 .gda/cache/

# P1: 录制
gda record "登录 GitHub" -o cases/github/login.yaml
gda record --app Safari -o cases/safari/search.yaml

# P1: 回放
gda run cases/github/login.yaml
gda run cases/  # 运行目录下所有 Case

# P2: 修复
gda fix cases/github/login.yaml  # 运行失败的 Case，LLM 尝试修复

# P2: 报告
gda run cases/ --report html --output report.html
```

## 目录结构

```
goal-driven-automation/
├── src/
│   ├── cli/               # CLI 入口
│   │   ├── __init__.py
│   │   ├── main.py        # gda 命令入口
│   │   ├── run.py         # gda run
│   │   ├── record.py      # gda record
│   │   └── fix.py         # gda fix
│   ├── engine/            # 核心引擎
│   │   ├── planner.py     # Planning Loop
│   │   ├── executor.py    # Action 执行器
│   │   └── recorder.py    # 边执行边记录
│   ├── actions/           # Action 定义
│   │   ├── action_space.py
│   │   └── fsq_adapter.py # fsq-mac 适配器
│   ├── cache/             # 缓存机制
│   │   └── case_cache.py
│   ├── llm/               # LLM 交互
│   │   ├── prompt.py      # Prompt 模板
│   │   └── parser.py      # XML 解析
│   ├── case/              # Case 文件处理
│   │   ├── schema.py      # Case YAML Schema
│   │   ├── loader.py      # 加载 Case
│   │   └── writer.py      # 写入 Case
│   └── report/            # 报告生成
│       └── html.py
├── cases/                 # Case 文件目录
├── tests/
└── pyproject.toml
```

## 开发任务拆分

### Phase 0: 基础设施 (1-2 天)
- [ ] T1: 定义 Case YAML Schema (`src/case/schema.py`)
- [ ] T2: 实现 Case Loader/Writer (`src/case/`)
- [ ] T3: 定义 Action Space (`src/actions/action_space.py`)

### Phase 1: Core Engine (3-4 天)
- [ ] T4: 实现 fsq-mac Adapter (`src/actions/fsq_adapter.py`)
- [ ] T5: 实现 LLM Prompt + XML Parser (`src/llm/`)
- [ ] T6: 实现 Planning Loop (`src/engine/planner.py`)
- [ ] T7: 实现 Recorder - 边执行边记录 (`src/engine/recorder.py`)

### Phase 2: CLI P0 (1-2 天)
- [ ] T8: 实现 `gda "goal"` 即时执行 (`src/cli/main.py`)
- [ ] T9: 实现 Cache 机制 (`src/cache/`)

### Phase 3: CLI P1 (2 天)
- [ ] T10: 实现 `gda record` 录制命令
- [ ] T11: 实现 `gda run` 回放命令

### Phase 4: CLI P2 (2 天)
- [ ] T12: 实现 `gda fix` 修复命令
- [ ] T13: 实现 HTML Report 生成

### 依赖关系

```
T1 ─┬→ T2 ─┬→ T8 → T9
    │      │
T3 ─┴→ T4 ─┼→ T6 → T7 → T10 → T11 → T12
           │
T5 ────────┘
                        T13 (独立)
```

## 风险点

1. **LLM 上下文爆炸** — 需要压缩历史，只保留最近 N 步
2. **Accessibility 元素匹配** — fsq-mac 可能找不到元素，需要 fallback
3. **缓存失效** — UI 变化后 Case 可能失效，需要 `gda fix`

## 参考

- Midscene.js: https://github.com/web-infra-dev/midscene
- Issue #49: 架构设计
- Issue #50: 产品形态

# Standalone AI Product Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform GDA from a rule-based pipeline into a standalone AI-powered macOS GUI testing product with built-in multi-LLM support, YAML goal files, and progressive AI injection.

**Architecture:** Keep the existing 7-stage pipeline intact. Add an LLM abstraction layer (`src/llm/`), a goal file loader, and progressively replace rule-based stages with LLM-driven equivalents. Each phase is independently deliverable. Fallback to rule engine when LLM is unavailable.

**Tech Stack:** Python 3.13+, PyYAML, jsonschema, anthropic SDK, openai SDK, Pillow

---

## Task 1: Add LLM SDK Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update pyproject.toml with new dependencies**

Add `anthropic` and `openai` as optional dependencies so the core still works without them.

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]
llm = ["anthropic>=0.40", "openai>=1.50"]
all = ["anthropic>=0.40", "openai>=1.50"]
```

**Step 2: Install dependencies**

Run: `pip install -e ".[llm,dev]"`

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add anthropic and openai as optional LLM deps"
```

---

## Task 2: Create LLM Provider Base Class

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/providers/__init__.py`
- Create: `src/llm/providers/base.py`
- Test: `tests/unit/test_llm_provider.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_provider.py
"""Unit tests for LLM provider base class."""
import pytest
from src.llm.providers.base import LLMProvider, LLMResponse


class TestLLMProviderContract:
    def test_llm_response_has_required_fields(self):
        resp = LLMResponse(text="hello", usage={"input_tokens": 10, "output_tokens": 5})
        assert resp.text == "hello"
        assert resp.usage["input_tokens"] == 10

    def test_llm_response_default_usage(self):
        resp = LLMResponse(text="hello")
        assert resp.usage == {}

    def test_provider_is_abstract(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_provider_subclass_must_implement_complete(self):
        class Incomplete(LLMProvider):
            @property
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            Incomplete()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_provider.py -v`
Expected: FAIL (import error, module does not exist)

**Step 3: Write minimal implementation**

```python
# src/llm/__init__.py
```

```python
# src/llm/providers/__init__.py
```

```python
# src/llm/providers/base.py
"""Base class for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    text: str
    usage: Dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'claude', 'openai')."""
        ...

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        """Send a text prompt and return a text response."""
        ...

    @abstractmethod
    def complete_with_images(
        self, prompt: str, images: List[Path], system: Optional[str] = None
    ) -> LLMResponse:
        """Send a prompt with images and return a text response."""
        ...

    @abstractmethod
    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a prompt and return a JSON object matching the given schema."""
        ...
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm/ tests/unit/test_llm_provider.py
git commit -m "feat: add LLM provider base class and LLMResponse"
```

---

## Task 3: Create Claude Provider

**Files:**
- Create: `src/llm/providers/claude.py`
- Test: `tests/unit/test_llm_claude.py`

**Step 1: Write the failing test**

The test mocks the Anthropic SDK so it runs without an API key.

```python
# tests/unit/test_llm_claude.py
"""Unit tests for Claude LLM provider."""
import json
import pytest
from unittest.mock import patch, MagicMock
from src.llm.providers.claude import ClaudeProvider


class TestClaudeProvider:
    def test_name_is_claude(self):
        with patch("src.llm.providers.claude.anthropic"):
            provider = ClaudeProvider(api_key="test-key")
            assert provider.name == "claude"

    def test_complete_calls_anthropic_api(self):
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        with patch("src.llm.providers.claude.anthropic", mock_anthropic):
            provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
            result = provider.complete("Say hello")

        assert result.text == "Hello from Claude"
        assert result.usage["input_tokens"] == 10

    def test_complete_structured_parses_json(self):
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"name": "test", "value": 42}')]
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 10
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        with patch("src.llm.providers.claude.anthropic", mock_anthropic):
            provider = ClaudeProvider(api_key="test-key")
            result = provider.complete_structured("Return JSON", schema={"type": "object"})

        assert result == {"name": "test", "value": 42}

    def test_raises_import_error_without_anthropic(self):
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(ImportError, match="anthropic"):
                ClaudeProvider(api_key="test-key")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_claude.py -v`
Expected: FAIL (import error)

**Step 3: Write minimal implementation**

```python
# src/llm/providers/claude.py
"""Claude (Anthropic) LLM provider."""
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider, LLMResponse

try:
    import anthropic
except ImportError:
    anthropic = None


class ClaudeProvider(LLMProvider):
    """LLM provider using the Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        if anthropic is None:
            raise ImportError(
                "anthropic package is required for Claude provider. "
                "Install with: pip install 'goal-driven-automation[llm]'"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "claude"

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        kwargs = {"model": self._model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return LLMResponse(
            text=response.content[0].text,
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
        )

    def complete_with_images(
        self, prompt: str, images: List[Path], system: Optional[str] = None
    ) -> LLMResponse:
        content = []
        for img_path in images:
            data = Path(img_path).read_bytes()
            suffix = Path(img_path).suffix.lower()
            media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(
                suffix.lstrip("."), "image/png"
            )
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}})
        content.append({"type": "text", "text": prompt})

        kwargs = {"model": self._model, "max_tokens": 4096, "messages": [{"role": "user", "content": content}]}
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return LLMResponse(
            text=response.content[0].text,
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None
    ) -> Dict[str, Any]:
        structured_prompt = f"{prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        response = self.complete(structured_prompt, system=system)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_claude.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm/providers/claude.py tests/unit/test_llm_claude.py
git commit -m "feat: add Claude LLM provider"
```

---

## Task 4: Create OpenAI Provider

**Files:**
- Create: `src/llm/providers/openai_provider.py`
- Test: `tests/unit/test_llm_openai.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_openai.py
"""Unit tests for OpenAI LLM provider."""
import pytest
from unittest.mock import patch, MagicMock
from src.llm.providers.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    def test_name_is_openai(self):
        with patch("src.llm.providers.openai_provider.openai"):
            provider = OpenAIProvider(api_key="test-key")
            assert provider.name == "openai"

    def test_complete_calls_openai_api(self):
        mock_openai = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from GPT"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response

        with patch("src.llm.providers.openai_provider.openai", mock_openai):
            provider = OpenAIProvider(api_key="test-key")
            result = provider.complete("Say hello")

        assert result.text == "Hello from GPT"
        assert result.usage["input_tokens"] == 10

    def test_raises_import_error_without_openai(self):
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai"):
                OpenAIProvider(api_key="test-key")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_openai.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/llm/providers/openai_provider.py
"""OpenAI LLM provider."""
import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider, LLMResponse

try:
    import openai
except ImportError:
    openai = None


class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if openai is None:
            raise ImportError(
                "openai package is required for OpenAI provider. "
                "Install with: pip install 'goal-driven-automation[llm]'"
            )
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(model=self._model, messages=messages)
        return LLMResponse(
            text=response.choices[0].message.content,
            usage={"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens},
        )

    def complete_with_images(
        self, prompt: str, images: List[Path], system: Optional[str] = None
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        content = []
        for img_path in images:
            data = base64.b64encode(Path(img_path).read_bytes()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}})
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})
        response = self._client.chat.completions.create(model=self._model, messages=messages)
        return LLMResponse(
            text=response.choices[0].message.content,
            usage={"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens},
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None
    ) -> Dict[str, Any]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": f"{prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"})
        response = self._client.chat.completions.create(
            model=self._model, messages=messages, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_openai.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm/providers/openai_provider.py tests/unit/test_llm_openai.py
git commit -m "feat: add OpenAI LLM provider"
```

---

## Task 5: Create LLM Configuration Loader

**Files:**
- Create: `src/llm/config.py`
- Test: `tests/unit/test_llm_config.py`

The config loader reads `gda.config.yaml` and resolves environment variables in API keys.

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_config.py
"""Unit tests for LLM configuration loader."""
import os
import tempfile
import pytest
from pathlib import Path
from src.llm.config import LLMConfig, load_llm_config


class TestLLMConfig:
    def test_load_minimal_config(self, tmp_path):
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: sk-test-123
      model: claude-sonnet-4-6
""")
        config = load_llm_config(config_file)
        assert config.default_provider == "claude"
        assert config.providers["claude"]["api_key"] == "sk-test-123"
        assert config.providers["claude"]["model"] == "claude-sonnet-4-6"

    def test_resolves_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "sk-from-env")
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: ${TEST_API_KEY}
""")
        config = load_llm_config(config_file)
        assert config.providers["claude"]["api_key"] == "sk-from-env"

    def test_returns_none_when_no_config(self, tmp_path):
        config = load_llm_config(tmp_path / "nonexistent.yaml")
        assert config is None

    def test_returns_none_when_no_llm_section(self, tmp_path):
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("pipeline:\n  mode: rules\n")
        config = load_llm_config(config_file)
        assert config is None

    def test_has_provider_check(self, tmp_path):
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: sk-test
""")
        config = load_llm_config(config_file)
        assert config.has_provider("claude") is True
        assert config.has_provider("openai") is False

    def test_routing_defaults_to_default_provider(self, tmp_path):
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: sk-test
""")
        config = load_llm_config(config_file)
        assert config.get_provider_for_task("goal_parsing") == "claude"
        assert config.get_provider_for_task("visual_verification") == "claude"

    def test_routing_overrides(self, tmp_path):
        config_file = tmp_path / "gda.config.yaml"
        config_file.write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: sk-test
    openai:
      api_key: sk-openai
  routing:
    visual_verification: openai
""")
        config = load_llm_config(config_file)
        assert config.get_provider_for_task("goal_parsing") == "claude"
        assert config.get_provider_for_task("visual_verification") == "openai"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_config.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/llm/config.py
"""LLM configuration loader."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class LLMConfig:
    """Parsed LLM configuration."""
    default_provider: str
    providers: Dict[str, Dict[str, Any]]
    routing: Dict[str, str] = field(default_factory=dict)

    def has_provider(self, name: str) -> bool:
        return name in self.providers

    def get_provider_for_task(self, task: str) -> str:
        return self.routing.get(task, self.default_provider)


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    def replacer(match):
        var = match.group(1)
        return os.environ.get(var, match.group(0))
    return re.sub(r"\$\{(\w+)\}", replacer, value)


def _resolve_env_in_dict(d: Dict) -> Dict:
    """Recursively resolve env vars in dict values."""
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_env_in_dict(v)
        else:
            result[k] = v
    return result


def load_llm_config(config_path: Path) -> Optional[LLMConfig]:
    """Load LLM config from a YAML file. Returns None if not found or no llm section."""
    if not config_path.exists():
        return None

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data or "llm" not in data:
        return None

    llm = data["llm"]
    providers = _resolve_env_in_dict(llm.get("providers", {}))

    return LLMConfig(
        default_provider=llm.get("default_provider", "claude"),
        providers=providers,
        routing=llm.get("routing", {}),
    )
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm/config.py tests/unit/test_llm_config.py
git commit -m "feat: add LLM config loader with env var resolution"
```

---

## Task 6: Create LLMClient (Unified Interface)

**Files:**
- Create: `src/llm/client.py`
- Test: `tests/unit/test_llm_client.py`

The `LLMClient` is the single entry point used by all pipeline stages. It reads the config, instantiates providers, and routes requests.

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_client.py
"""Unit tests for LLMClient."""
import pytest
from unittest.mock import MagicMock, patch
from src.llm.client import LLMClient
from src.llm.config import LLMConfig
from src.llm.providers.base import LLMResponse


class TestLLMClient:
    def _make_config(self, **overrides):
        defaults = {
            "default_provider": "claude",
            "providers": {
                "claude": {"api_key": "sk-test", "model": "claude-sonnet-4-6"},
            },
            "routing": {},
        }
        defaults.update(overrides)
        return LLMConfig(**defaults)

    def test_create_from_config(self):
        config = self._make_config()
        with patch("src.llm.client.ClaudeProvider") as mock_cls:
            client = LLMClient(config)
            mock_cls.assert_called_once_with(api_key="sk-test", model="claude-sonnet-4-6")

    def test_complete_delegates_to_default_provider(self):
        config = self._make_config()
        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(text="result")

        with patch("src.llm.client.ClaudeProvider", return_value=mock_provider):
            client = LLMClient(config)
            result = client.complete("hello")

        assert result.text == "result"
        mock_provider.complete.assert_called_once_with("hello", system=None)

    def test_complete_routes_to_task_specific_provider(self):
        config = self._make_config(
            providers={
                "claude": {"api_key": "sk-a", "model": "claude-sonnet-4-6"},
                "openai": {"api_key": "sk-b", "model": "gpt-4o"},
            },
            routing={"visual_verification": "openai"},
        )
        mock_claude = MagicMock()
        mock_openai = MagicMock()
        mock_openai.complete.return_value = LLMResponse(text="from openai")

        with patch("src.llm.client.ClaudeProvider", return_value=mock_claude):
            with patch("src.llm.client.OpenAIProvider", return_value=mock_openai):
                client = LLMClient(config)
                result = client.complete("check image", task="visual_verification")

        assert result.text == "from openai"
        mock_openai.complete.assert_called_once()

    def test_is_available_true_when_config_present(self):
        config = self._make_config()
        with patch("src.llm.client.ClaudeProvider"):
            client = LLMClient(config)
            assert client.is_available() is True

    def test_create_returns_none_for_none_config(self):
        client = LLMClient.create(None)
        assert client is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_client.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/llm/client.py
"""Unified LLM client that routes requests to configured providers."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.config import LLMConfig
from src.llm.providers.base import LLMProvider, LLMResponse

# Lazy imports to avoid hard dependency
try:
    from src.llm.providers.claude import ClaudeProvider
except ImportError:
    ClaudeProvider = None

try:
    from src.llm.providers.openai_provider import OpenAIProvider
except ImportError:
    OpenAIProvider = None


PROVIDER_CLASSES = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


class LLMClient:
    """Unified LLM client. Routes requests to configured providers."""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._providers: Dict[str, LLMProvider] = {}
        for name, settings in config.providers.items():
            cls = PROVIDER_CLASSES.get(name)
            if cls is not None:
                self._providers[name] = cls(
                    api_key=settings.get("api_key", ""),
                    model=settings.get("model", ""),
                )

    @classmethod
    def create(cls, config: Optional[LLMConfig]) -> Optional["LLMClient"]:
        """Create a client from config, returning None if config is None."""
        if config is None:
            return None
        return cls(config)

    def is_available(self) -> bool:
        return len(self._providers) > 0

    def _get_provider(self, task: Optional[str] = None) -> LLMProvider:
        name = self._config.get_provider_for_task(task) if task else self._config.default_provider
        provider = self._providers.get(name)
        if provider is None:
            raise RuntimeError(f"LLM provider '{name}' is not configured or not installed")
        return provider

    def complete(self, prompt: str, system: Optional[str] = None, task: Optional[str] = None) -> LLMResponse:
        return self._get_provider(task).complete(prompt, system=system)

    def complete_with_images(
        self, prompt: str, images: List[Path], system: Optional[str] = None, task: Optional[str] = None
    ) -> LLMResponse:
        return self._get_provider(task).complete_with_images(prompt, images, system=system)

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None, task: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._get_provider(task).complete_structured(prompt, schema=schema, system=system)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm/client.py tests/unit/test_llm_client.py
git commit -m "feat: add unified LLMClient with task-based routing"
```

---

## Task 7: Create Goal File Loader

**Files:**
- Create: `src/goal_loader.py`
- Test: `tests/unit/test_goal_loader.py`

Loads `.goal.yaml` files and `.suite.yaml` files from disk.

**Step 1: Write the failing test**

```python
# tests/unit/test_goal_loader.py
"""Unit tests for goal file loader."""
import pytest
from pathlib import Path
from src.goal_loader import GoalFile, SuiteFile, load_goal_file, load_suite_file, discover_goal_files


class TestGoalFileLoader:
    def test_load_minimal_goal(self, tmp_path):
        f = tmp_path / "test.goal.yaml"
        f.write_text("goal: Open Edge and create new tab\n")
        goal = load_goal_file(f)
        assert goal.goal == "Open Edge and create new tab"
        assert goal.name is None
        assert goal.tags == []

    def test_load_full_goal(self, tmp_path):
        f = tmp_path / "test.goal.yaml"
        f.write_text("""
name: Edge New Tab
app: Microsoft Edge
tags: [smoke, edge]
priority: high
goal: |
  Open Edge browser, create a new tab.
config:
  timeout_ms: 60000
""")
        goal = load_goal_file(f)
        assert goal.name == "Edge New Tab"
        assert goal.app == "Microsoft Edge"
        assert goal.tags == ["smoke", "edge"]
        assert goal.priority == "high"
        assert "Open Edge" in goal.goal
        assert goal.config["timeout_ms"] == 60000

    def test_discover_goal_files_in_directory(self, tmp_path):
        (tmp_path / "a.goal.yaml").write_text("goal: test a\n")
        (tmp_path / "b.goal.yaml").write_text("goal: test b\n")
        (tmp_path / "not-a-goal.yaml").write_text("other: data\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.goal.yaml").write_text("goal: test c\n")

        files = discover_goal_files(tmp_path)
        names = [f.name for f in files]
        assert "a.goal.yaml" in names
        assert "b.goal.yaml" in names
        assert "c.goal.yaml" in names
        assert "not-a-goal.yaml" not in names

    def test_discover_accepts_single_file(self, tmp_path):
        f = tmp_path / "test.goal.yaml"
        f.write_text("goal: test\n")
        files = discover_goal_files(f)
        assert len(files) == 1

    def test_filter_by_tags(self, tmp_path):
        (tmp_path / "a.goal.yaml").write_text("goal: a\ntags: [smoke]\n")
        (tmp_path / "b.goal.yaml").write_text("goal: b\ntags: [regression]\n")
        files = discover_goal_files(tmp_path, tags=["smoke"])
        assert len(files) == 1


class TestSuiteFileLoader:
    def test_load_suite(self, tmp_path):
        f = tmp_path / "smoke.suite.yaml"
        f.write_text("""
name: Smoke Tests
include:
  - tests/a.goal.yaml
  - tags: [smoke]
exclude:
  - tags: [flaky]
""")
        suite = load_suite_file(f)
        assert suite.name == "Smoke Tests"
        assert len(suite.include) == 2
        assert len(suite.exclude) == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_goal_loader.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/goal_loader.py
"""Loader for .goal.yaml and .suite.yaml files."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


@dataclass
class GoalFile:
    """Parsed .goal.yaml file."""
    goal: str
    path: Path
    name: Optional[str] = None
    app: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    priority: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteFile:
    """Parsed .suite.yaml file."""
    name: str
    path: Path
    include: List[Union[str, Dict]] = field(default_factory=list)
    exclude: List[Union[str, Dict]] = field(default_factory=list)
    description: Optional[str] = None
    schedule: Optional[str] = None


def load_goal_file(path: Path) -> GoalFile:
    """Load a single .goal.yaml file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return GoalFile(
        goal=data["goal"].strip(),
        path=path,
        name=data.get("name"),
        app=data.get("app"),
        tags=data.get("tags", []),
        priority=data.get("priority"),
        config=data.get("config", {}),
    )


def load_suite_file(path: Path) -> SuiteFile:
    """Load a .suite.yaml file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return SuiteFile(
        name=data["name"],
        path=path,
        include=data.get("include", []),
        exclude=data.get("exclude", []),
        description=data.get("description"),
        schedule=data.get("schedule"),
    )


def discover_goal_files(
    path: Path, tags: Optional[List[str]] = None
) -> List[Path]:
    """Find all .goal.yaml files under a path. Optionally filter by tags."""
    if path.is_file():
        return [path]

    files = sorted(path.rglob("*.goal.yaml"))

    if tags:
        filtered = []
        for f in files:
            goal = load_goal_file(f)
            if any(t in goal.tags for t in tags):
                filtered.append(f)
        return filtered

    return files
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_goal_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/goal_loader.py tests/unit/test_goal_loader.py
git commit -m "feat: add goal file and suite file loader"
```

---

## Task 8: Create LLM Goal Interpreter

**Files:**
- Create: `src/goal_interpreter/llm_interpreter.py`
- Create: `src/goal_interpreter/prompts/goal_to_plan.py`
- Modify: `src/goal_interpreter/__init__.py` (currently empty)
- Test: `tests/unit/test_llm_interpreter.py`

This is the core Phase 1 component. It uses an LLM to convert natural language goals into Plan IR.

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_interpreter.py
"""Unit tests for LLM goal interpreter."""
import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path
from src.goal_interpreter.llm_interpreter import LLMGoalInterpreter


class TestLLMGoalInterpreter:
    def _make_mock_client(self, plan_response: dict):
        client = MagicMock()
        client.complete_structured.return_value = plan_response
        return client

    def _make_registry_text(self):
        return """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
  hotkey:
    args:
      combo: {type: string, required: true}
    compile_to: mac input hotkey {combo}
"""

    def test_interpret_returns_valid_plan_ir(self):
        plan = {
            "plan_id": "plan-test",
            "version": "1.0.0",
            "goal": "Open Edge and create new tab",
            "app": "Microsoft Edge",
            "steps": [
                {"step_id": "s1", "action": "launch", "params": {"app": "Microsoft Edge"}},
                {"step_id": "s2", "action": "shortcut", "params": {"keys": ["command", "t"]}},
            ],
        }
        client = self._make_mock_client(plan)
        interpreter = LLMGoalInterpreter(client, registry_text=self._make_registry_text())

        result = interpreter.interpret("Open Edge and create new tab")

        assert result["plan_id"].startswith("plan-")
        assert result["goal"] == "Open Edge and create new tab"
        assert len(result["steps"]) >= 1
        client.complete_structured.assert_called_once()

    def test_prompt_includes_registry_actions(self):
        client = self._make_mock_client({"plan_id": "p", "steps": []})
        registry = self._make_registry_text()
        interpreter = LLMGoalInterpreter(client, registry_text=registry)

        interpreter.interpret("Open Edge")

        call_args = client.complete_structured.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1]["prompt"]
        assert "launch_app" in prompt
        assert "hotkey" in prompt

    def test_prompt_includes_plan_ir_schema(self):
        client = self._make_mock_client({"plan_id": "p", "steps": []})
        interpreter = LLMGoalInterpreter(client, registry_text=self._make_registry_text())
        interpreter.interpret("Open Edge")

        call_args = client.complete_structured.call_args
        schema = call_args[1].get("schema") or call_args[0][1]
        assert "plan_id" in json.dumps(schema)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_llm_interpreter.py -v`
Expected: FAIL

**Step 3: Create the prompt template**

```python
# src/goal_interpreter/prompts/goal_to_plan.py
"""Prompt template for goal-to-plan conversion."""

SYSTEM_PROMPT = """You are a macOS GUI automation planner. Given a user's goal in natural language, generate a structured Plan IR (Intermediate Representation) that can be compiled into executable CLI commands.

You have access to these automation capabilities (from the action registry):

{registry}

Rules:
1. Each step must use an action that maps to a registry capability.
2. Use step_id format: s1, s2, s3, etc.
3. Always start with a "launch" step if the goal involves opening an app.
4. Use "shortcut" for keyboard shortcuts (e.g., Cmd+T for new tab).
5. Use "assert" to verify expected outcomes.
6. Set on_fail to "abort" for critical steps (like launch), "continue" for non-critical ones.
7. Include evidence capture settings: screenshot_after for visual verification steps.
8. Use retry_policy for flaky operations (element clicks, assertions).
9. The plan_id should be "plan-" followed by a short kebab-case identifier.
10. version should always be "1.0.0".
"""

USER_PROMPT = """Generate a Plan IR for this goal:

{goal}

Return a JSON object with this structure:
- plan_id: string (e.g., "plan-edge-new-tab")
- version: "1.0.0"
- goal: the original goal text
- app: the target application name
- steps: array of step objects, each with:
  - step_id: "s1", "s2", etc.
  - action: one of [launch, shortcut, type, click, wait, assert, capture]
  - params: action-specific parameters
  - evidence: {{screenshot_after: bool, ui_tree_after: bool}} (optional)
  - retry_policy: {{max_attempts: int, backoff: string, delay_ms: int}} (optional)
  - on_fail: one of [abort, skip, continue, retry, human_review]
"""
```

**Step 4: Create the interpreter**

```python
# src/goal_interpreter/llm_interpreter.py
"""LLM-driven goal interpreter that converts natural language to Plan IR."""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.llm.client import LLMClient
from src.goal_interpreter.prompts.goal_to_plan import SYSTEM_PROMPT, USER_PROMPT


# Minimal Plan IR schema for structured output
PLAN_IR_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["plan_id", "version", "goal", "app", "steps"],
    "properties": {
        "plan_id": {"type": "string"},
        "version": {"type": "string"},
        "goal": {"type": "string"},
        "app": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["step_id", "action", "params"],
                "properties": {
                    "step_id": {"type": "string"},
                    "action": {"type": "string"},
                    "params": {"type": "object"},
                    "evidence": {"type": "object"},
                    "retry_policy": {"type": "object"},
                    "on_fail": {"type": "string"},
                },
            },
        },
    },
}


class LLMGoalInterpreter:
    """Interprets natural language goals into Plan IR using an LLM."""

    def __init__(self, llm_client: LLMClient, registry_text: Optional[str] = None, registry_path: Optional[Path] = None):
        self._client = llm_client
        if registry_text is not None:
            self._registry = registry_text
        elif registry_path is not None:
            self._registry = registry_path.read_text()
        else:
            self._registry = ""

    def interpret(self, goal_text: str) -> Dict[str, Any]:
        """Convert a natural language goal into a Plan IR dict."""
        system = SYSTEM_PROMPT.format(registry=self._registry)
        prompt = USER_PROMPT.format(goal=goal_text)

        plan = self._client.complete_structured(
            prompt, schema=PLAN_IR_OUTPUT_SCHEMA, system=system, task="goal_parsing"
        )

        # Ensure required fields
        if "goal" not in plan or plan["goal"] != goal_text:
            plan["goal"] = goal_text
        if "version" not in plan:
            plan["version"] = "1.0.0"

        return plan
```

Also update the init:

```python
# src/goal_interpreter/__init__.py
```

**Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_llm_interpreter.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/goal_interpreter/ tests/unit/test_llm_interpreter.py
git commit -m "feat: add LLM goal interpreter with prompt templates"
```

---

## Task 9: Create Rule-Based Interpreter Wrapper

**Files:**
- Create: `src/goal_interpreter/rule_interpreter.py`
- Test: `tests/unit/test_rule_interpreter.py`

Wraps the existing `GoalParser` + `PlanGenerator` behind the same interface as `LLMGoalInterpreter`.

**Step 1: Write the failing test**

```python
# tests/unit/test_rule_interpreter.py
"""Unit tests for rule-based interpreter wrapper."""
import pytest
from src.goal_interpreter.rule_interpreter import RuleInterpreter


class TestRuleInterpreter:
    def test_interpret_returns_plan_ir(self):
        interpreter = RuleInterpreter()
        result = interpreter.interpret("Open Edge and create new tab")

        assert "plan_id" in result
        assert result["goal"] == "Open Edge and create new tab"
        assert result["app"] == "Microsoft Edge"
        assert len(result["steps"]) >= 2

    def test_interpret_launch_only(self):
        interpreter = RuleInterpreter()
        result = interpreter.interpret("Open Safari")

        assert result["app"] == "Safari"
        actions = [s["action"] for s in result["steps"]]
        assert "launch" in actions
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_rule_interpreter.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/goal_interpreter/rule_interpreter.py
"""Rule-based interpreter wrapping existing GoalParser + PlanGenerator."""
from typing import Any, Dict

from src.pipeline.goal_parser import GoalParser
from src.pipeline.plan_generator import PlanGenerator


class RuleInterpreter:
    """Interprets goals using the existing regex + template engine."""

    def __init__(self):
        self._parser = GoalParser()
        self._generator = PlanGenerator()

    def interpret(self, goal_text: str) -> Dict[str, Any]:
        """Convert a natural language goal into a Plan IR dict."""
        goal = self._parser.parse(goal_text)
        return self._generator.generate(goal)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_rule_interpreter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/goal_interpreter/rule_interpreter.py tests/unit/test_rule_interpreter.py
git commit -m "feat: add rule-based interpreter wrapper"
```

---

## Task 10: Wire Interpreter into Pipeline with Fallback

**Files:**
- Modify: `src/pipeline/pipeline.py` (lines ~93-105 for __init__, ~107-131 for run)
- Test: `tests/unit/test_pipeline_interpreter.py`

This is the key integration task. The Pipeline should use `LLMGoalInterpreter` when available, fall back to `RuleInterpreter`, and remain backward compatible.

**Step 1: Write the failing test**

```python
# tests/unit/test_pipeline_interpreter.py
"""Tests for Pipeline interpreter integration."""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.pipeline.pipeline import Pipeline


def _write_registry(base_dir):
    registry_dir = base_dir / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "actions.yaml").write_text("""
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
    expected_evidence: [process_running]
    default_retry: {max: 1}
  hotkey:
    args:
      combo: {type: string, required: true}
    compile_to: mac input hotkey {combo}
    expected_evidence: [command_output]
    default_retry: {max: 1}
""")


class TestPipelineInterpreterIntegration:
    def test_pipeline_uses_rule_interpreter_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            _write_registry(base_dir)
            pipeline = Pipeline(base_dir=base_dir)
            result = pipeline.run("Open Edge", dry_run=True)

            assert result.success is True
            assert result.plan is not None
            assert result.plan["app"] == "Microsoft Edge"

    def test_pipeline_uses_llm_interpreter_when_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            _write_registry(base_dir)

            # Write config enabling LLM
            (base_dir / "gda.config.yaml").write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: test-key
pipeline:
  goal_interpreter: llm
""")

            llm_plan = {
                "plan_id": "plan-from-llm",
                "version": "1.0.0",
                "goal": "Open Edge",
                "app": "Microsoft Edge",
                "steps": [{"step_id": "s1", "action": "launch", "params": {"app": "Microsoft Edge"}}],
            }

            with patch("src.pipeline.pipeline.LLMGoalInterpreter") as mock_cls:
                mock_cls.return_value.interpret.return_value = llm_plan
                with patch("src.pipeline.pipeline.LLMClient") as mock_client_cls:
                    mock_client_cls.return_value.is_available.return_value = True
                    with patch("src.pipeline.pipeline.load_llm_config") as mock_load:
                        mock_load.return_value = MagicMock()
                        pipeline = Pipeline(base_dir=base_dir)
                        result = pipeline.run("Open Edge", dry_run=True)

            assert result.plan["plan_id"] == "plan-from-llm"

    def test_pipeline_falls_back_to_rules_on_llm_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            _write_registry(base_dir)

            (base_dir / "gda.config.yaml").write_text("""
llm:
  default_provider: claude
  providers:
    claude:
      api_key: test-key
pipeline:
  goal_interpreter: auto
""")

            with patch("src.pipeline.pipeline.LLMGoalInterpreter") as mock_cls:
                mock_cls.return_value.interpret.side_effect = RuntimeError("LLM API error")
                with patch("src.pipeline.pipeline.LLMClient") as mock_client_cls:
                    mock_client_cls.return_value.is_available.return_value = True
                    with patch("src.pipeline.pipeline.load_llm_config") as mock_load:
                        mock_load.return_value = MagicMock()
                        pipeline = Pipeline(base_dir=base_dir)
                        result = pipeline.run("Open Edge", dry_run=True)

            # Should fall back to rule interpreter and succeed
            assert result.success is True
            assert result.plan["app"] == "Microsoft Edge"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_pipeline_interpreter.py -v`
Expected: FAIL

**Step 3: Modify Pipeline.__init__ and Pipeline.run**

In `src/pipeline/pipeline.py`, add imports at the top (after existing imports, around line 15):

```python
import logging
import yaml

from src.llm.config import load_llm_config
from src.llm.client import LLMClient
from src.goal_interpreter.llm_interpreter import LLMGoalInterpreter
from src.goal_interpreter.rule_interpreter import RuleInterpreter

logger = logging.getLogger(__name__)
```

Replace the `__init__` method (currently at lines ~93-105) to add interpreter setup:

```python
def __init__(self, base_dir: Optional[Path] = None, mac_cli: str = "mac"):
    self.base_dir = base_dir or Path(__file__).parent.parent.parent
    self.goal_parser = GoalParser()
    self.plan_generator = PlanGenerator()
    self.compiler = Compiler(self.base_dir / "registry" / "actions.yaml")
    self.executor = Executor()
    self.evidence_storage = EvidenceStorage(self.base_dir / "data" / "runs")
    self.evaluator = Evaluator()
    self.repair_loop = RepairLoop()
    self.evolution = EvolutionEngine(self.base_dir)

    # Interpreter setup
    self._rule_interpreter = RuleInterpreter()
    self._llm_interpreter = None
    self._llm_client = None
    self._interpreter_mode = "rules"  # default
    self._init_llm(self.base_dir)

def _init_llm(self, base_dir: Path):
    """Initialize LLM if configured."""
    config_path = base_dir / "gda.config.yaml"
    if not config_path.exists():
        return

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        return

    self._interpreter_mode = raw.get("pipeline", {}).get("goal_interpreter", "auto")

    llm_config = load_llm_config(config_path)
    if llm_config is None:
        return

    try:
        self._llm_client = LLMClient(llm_config)
        registry_path = base_dir / "registry" / "actions.yaml"
        self._llm_interpreter = LLMGoalInterpreter(
            self._llm_client,
            registry_path=registry_path if registry_path.exists() else None,
        )
    except Exception as e:
        logger.warning("Failed to initialize LLM: %s", e)
```

Replace the PARSE_GOAL + GENERATE_PLAN stages in `run()` (currently lines ~124-135) with a single interpret call:

```python
# In run(), replace PARSE_GOAL and GENERATE_PLAN stages with:
plan = self._interpret_goal(goal_text)
# (keep existing stage recording but merge the two stages)
```

Add the `_interpret_goal` method:

```python
def _interpret_goal(self, goal_text: str) -> dict:
    """Interpret goal using LLM or rule engine based on config."""
    if self._interpreter_mode == "llm" and self._llm_interpreter:
        return self._llm_interpreter.interpret(goal_text)

    if self._interpreter_mode == "auto" and self._llm_interpreter:
        try:
            return self._llm_interpreter.interpret(goal_text)
        except Exception as e:
            logger.warning("LLM interpretation failed, falling back to rules: %s", e)

    return self._rule_interpreter.interpret(goal_text)
```

**Important:** Keep the existing `goal_parser` and `plan_generator` attributes on Pipeline so that existing tests (like `TestGoalParser` and `TestPlanGenerator` in `tests/unit/test_pipeline.py`) continue to work. They test those components directly, not through the pipeline.

**Step 4: Run ALL tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (existing 111 tests + new tests)

**Step 5: Commit**

```bash
git add src/pipeline/pipeline.py tests/unit/test_pipeline_interpreter.py
git commit -m "feat: wire LLM interpreter into Pipeline with auto-fallback"
```

---

## Task 11: Create New CLI Entry Point

**Files:**
- Modify: `src/cli.py` (lines ~18-63 for cmd_run)
- Test: `tests/unit/test_cli.py`

Add support for running `.goal.yaml` files and directories, and `--tags` filtering.

**Step 1: Write the failing test**

```python
# tests/unit/test_cli.py
"""Unit tests for CLI."""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.cli import build_parser


class TestCLI:
    def test_run_accepts_goal_file(self):
        parser = build_parser()
        args = parser.parse_args(["run", "tests/edge.goal.yaml"])
        assert args.goal == "tests/edge.goal.yaml"

    def test_run_accepts_directory(self):
        parser = build_parser()
        args = parser.parse_args(["run", "tests/"])
        assert args.goal == "tests/"

    def test_run_accepts_tags(self):
        parser = build_parser()
        args = parser.parse_args(["run", "tests/", "--tags", "smoke,edge"])
        assert args.tags == "smoke,edge"

    def test_run_accepts_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["run", "tests/edge.goal.yaml", "--dry-run"])
        assert args.dry_run is True
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_cli.py -v`
Expected: FAIL (no `build_parser` function)

**Step 3: Refactor cli.py**

Extract `build_parser()` from the current `main()` function in `src/cli.py`. Add `--tags` argument to the `run` subparser. Add logic to detect whether the `goal` argument is a `.goal.yaml` file/directory or a plain text goal string.

Key changes to `cmd_run` (currently at line 18):
1. Check if `args.goal` is a path to a `.goal.yaml` file or directory
2. If yes, use `discover_goal_files` + `load_goal_file` to load goals
3. If no (plain string), run as before
4. Support `--tags` filtering

```python
def build_parser():
    parser = argparse.ArgumentParser(description="Goal-Driven Automation CLI")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("goal", help="Goal text, .goal.yaml file, or directory")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--json", action="store_true")
    run_parser.add_argument("--tags", default=None, help="Comma-separated tag filter")

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("plan_file")

    return parser
```

In `cmd_run`, add path detection:

```python
from src.goal_loader import load_goal_file, discover_goal_files

def cmd_run(args):
    path = Path(args.goal)
    if path.exists() and (path.suffix in ('.yaml', '.yml') or path.is_dir()):
        tags = args.tags.split(",") if args.tags else None
        files = discover_goal_files(path, tags=tags)
        goals = [load_goal_file(f) for f in files]
    else:
        # Plain text goal (backward compatible)
        goals = [type('Goal', (), {'goal': args.goal, 'name': None, 'config': {}})()]

    pipeline = Pipeline(base_dir=Path("."))
    for goal_file in goals:
        result = pipeline.run(goal_file.goal, dry_run=args.dry_run)
        _print_result(result, json_output=args.json)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_cli.py -v`
Expected: PASS

**Step 5: Verify all existing tests still pass**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/cli.py tests/unit/test_cli.py
git commit -m "feat: CLI supports .goal.yaml files, directories, and --tags filter"
```

---

## Task 12: Add gda.config.yaml to .gitignore and Create Example

**Files:**
- Modify: `.gitignore`
- Create: `gda.config.example.yaml`

**Step 1: Add to .gitignore**

Append to `.gitignore`:
```
# GDA config (may contain API keys)
gda.config.yaml
```

**Step 2: Create example config**

```yaml
# gda.config.example.yaml
# Copy to gda.config.yaml and fill in your API keys.

llm:
  default_provider: claude

  providers:
    claude:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-6
    # openai:
    #   api_key: ${OPENAI_API_KEY}
    #   model: gpt-4o

  # Optional: route specific tasks to different providers
  # routing:
  #   visual_verification: openai

pipeline:
  goal_interpreter: auto   # auto | llm | rules
```

**Step 3: Commit**

```bash
git add .gitignore gda.config.example.yaml
git commit -m "chore: add gda.config.example.yaml and gitignore gda.config.yaml"
```

---

## Task 13: Create Sample Goal Files

**Files:**
- Create: `data/cases/edge-new-tab.goal.yaml`
- Create: `data/cases/safari-navigate.goal.yaml`
- Create: `data/cases/finder-new-folder.goal.yaml`
- Create: `data/cases/suites/smoke.suite.yaml`

**Step 1: Create case directory and files**

```yaml
# data/cases/edge-new-tab.goal.yaml
name: Edge New Tab
app: Microsoft Edge
tags: [smoke, edge, tab]

goal: |
  Open Microsoft Edge browser and create a new tab.
  Verify that a new empty tab appears.
```

```yaml
# data/cases/safari-navigate.goal.yaml
name: Safari URL Navigation
app: Safari
tags: [smoke, safari, navigation]

goal: |
  Open Safari browser, click the address bar,
  type "github.com" and press Enter.
  Verify the page loads successfully.
```

```yaml
# data/cases/finder-new-folder.goal.yaml
name: Finder New Folder
app: Finder
tags: [smoke, finder, file]

goal: |
  Open Finder, navigate to the Desktop,
  create a new folder named "test-folder".
  Verify the folder appears in the file list.
```

```yaml
# data/cases/suites/smoke.suite.yaml
name: Smoke Tests
description: Quick validation of core app interactions

include:
  - tags: [smoke]
```

**Step 2: Commit**

```bash
git add data/cases/
git commit -m "feat: add sample goal YAML files and smoke suite"
```

---

## Task 14: Run Full Test Suite and Verify

This is the final validation for Phase 0 + Phase 1.

**Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Verify CLI works with goal files (dry run)**

Run: `python3 -m src.cli run data/cases/edge-new-tab.goal.yaml --dry-run`
Expected: Prints plan stages (using rule interpreter since no LLM configured)

Run: `python3 -m src.cli run data/cases/ --dry-run`
Expected: Runs all 3 goal files in dry-run mode

Run: `python3 -m src.cli run data/cases/ --dry-run --tags smoke`
Expected: Same 3 files (all tagged smoke)

**Step 3: Verify backward compatibility**

Run: `python3 -m src.cli run "Open Edge and create new tab" --dry-run`
Expected: Works exactly as before (plain text goal)

**Step 4: Final commit**

If any adjustments were needed during verification:

```bash
git add -A
git commit -m "fix: adjustments from integration testing"
```

---

## Future Tasks (Phase 2-4, not in this plan)

The following phases build on this foundation but are separate implementation plans:

### Phase 2: Visual Verification
- Create `src/evaluator/visual_verifier.py`
- LLM analyzes screenshots to determine pass/fail
- Wire into Evaluator as an additional verification step

### Phase 3: Smart Repair
- Create `src/repair/llm_repair.py`
- LLM analyzes failure context (stderr + screenshot + UI tree)
- Generates targeted repair plans
- Wire into RepairLoop as a strategy

### Phase 4: Runtime Decisions
- Create `src/executor/adaptive_executor.py`
- LLM observes state after each step
- Decides whether to continue, adapt, or abort
- Most complex phase, depends on Phase 2 + 3

---

Plan complete and saved to `docs/plans/2026-04-10-standalone-ai-product-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?

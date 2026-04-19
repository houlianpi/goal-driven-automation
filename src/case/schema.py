"""Dataclasses for case YAML documents."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CaseMeta:
    """Metadata describing a recorded case."""

    goal: str
    app: str
    created: str
    tags: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)


@dataclass
class Step:
    """One executable step in a case."""

    action: str
    target: str | None = None
    value: str | None = None
    result: str | None = None
    timestamp: str | None = None


@dataclass
class Postcondition:
    """A condition that must hold after steps complete."""

    assert_type: str
    target: str
    value: str | None = None


@dataclass
class CaseFile:
    """Full case document loaded from or saved to YAML."""

    meta: CaseMeta
    steps: list[Step] = field(default_factory=list)
    postconditions: list[Postcondition] = field(default_factory=list)

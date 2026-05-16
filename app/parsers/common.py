"""Utilidades compartidas entre analizadores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParseNode:
    symbol: str
    children: List["ParseNode"] = field(default_factory=list)
    value: Optional[str] = None  # para terminales

    def to_dict(self) -> dict:
        if self.children:
            return {
                "symbol": self.symbol,
                "children": [c.to_dict() for c in self.children],
            }
        return {"symbol": self.symbol, "value": self.value or self.symbol}

    @property
    def is_terminal(self) -> bool:
        return not self.children and self.value is not None


@dataclass
class ParseStep:
    step: int
    action: str
    description: str
    stack: List[str] = field(default_factory=list)
    input_remaining: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "action": self.action,
            "description": self.description,
            "stack": self.stack,
            "input_remaining": self.input_remaining,
            **self.extra,
        }


@dataclass
class ParseResult:
    accepted: bool
    steps: List[ParseStep]
    tree: Optional[ParseNode] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "error": self.error,
            "steps": [s.to_dict() for s in self.steps],
            "tree": self.tree.to_dict() if self.tree else None,
            "metadata": self.metadata,
        }

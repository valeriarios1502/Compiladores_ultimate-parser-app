"""Ítems LR(0) y LR(1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Set, Tuple

from app.grammar.grammar import Grammar, Production


@dataclass(frozen=True)
class LR0Item:
    prod_index: int
    dot: int

    def core_key(self) -> Tuple[int, int]:
        return (self.prod_index, self.dot)


@dataclass(frozen=True)
class LR1Item:
    prod_index: int
    dot: int
    lookahead: str

    def lr0_core(self) -> LR0Item:
        return LR0Item(self.prod_index, self.dot)

    def core_key(self) -> Tuple[int, int]:
        return (self.prod_index, self.dot)


def item_display(item: LR0Item, grammar: Grammar) -> str:
    p = grammar.productions[item.prod_index]
    rhs = list(p.rhs)
    rhs.insert(item.dot, "•")
    body = " ".join(rhs) if rhs else "•"
    return f"{p.lhs} → {body}"


def lr1_item_display(item: LR1Item, grammar: Grammar) -> str:
    return f"[{item_display(item.lr0_core(), grammar)}, {item.lookahead}]"

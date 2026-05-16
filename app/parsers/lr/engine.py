"""Motor LR: autómata, tablas ACTION/GOTO y análisis paso a paso."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from app.grammar.first_follow import compute_first, compute_follow
from app.grammar.grammar import END_MARKER, EPSILON, Grammar, Production
from app.parsers.common import ParseNode, ParseResult, ParseStep
from app.parsers.lr.items import LR0Item, LR1Item, item_display, lr1_item_display


class ParserType(str, Enum):
    LR0 = "lr0"
    SLR1 = "slr1"
    LR1 = "lr1"
    LALR1 = "lalr1"


@dataclass
class LRAction:
    kind: str  # shift, reduce, accept, error
    value: Optional[int] = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value}


@dataclass
class LRTables:
    action: Dict[Tuple[int, str], LRAction]
    goto: Dict[Tuple[int, str], int]
    states: List[Set[LR0Item]]
    state_labels: List[str]
    transitions: Dict[Tuple[int, str], int] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": {f"{s},{a}": v.to_dict() for (s, a), v in sorted(self.action.items())},
            "goto": {f"{s},{a}": v for (s, a), v in sorted(self.goto.items())},
            "num_states": len(self.states),
            "state_items": self.state_labels,
            "transitions": {f"{s},{x}": j for (s, x), j in sorted(self.transitions.items())},
            "conflicts": self.conflicts,
        }


class LRParser:
    def __init__(self, grammar: Grammar, parser_type: ParserType):
        self.original = grammar
        self.grammar = grammar.augmented()
        self.parser_type = parser_type
        self.first = compute_first(self.original)
        self.follow = compute_follow(self.original, self.first)
        self._lr1_states: List[Set[LR1Item]] = []
        self._lr1_transitions: Dict[Tuple[int, str], int] = {}
        self.tables = self._build_tables()

    def build_info(self) -> dict:
        return {
            "parser": self.parser_type.value,
            "augmented_start": self.grammar.start_symbol,
            "productions": [str(p) for p in self.grammar.productions],
            "follow": {k: sorted(v) for k, v in self.follow.items()},
            "tables": self.tables.to_dict(),
            "automaton": self.automaton_to_dict(),
        }

    # ---------- LR(0) ----------

    def _closure0(self, items: Set[LR0Item]) -> Set[LR0Item]:
        result = set(items)
        changed = True
        while changed:
            changed = False
            for it in list(result):
                p = self.grammar.productions[it.prod_index]
                if it.dot >= len(p.rhs):
                    continue
                b = p.rhs[it.dot]
                if b not in self.grammar.nonterminals:
                    continue
                for prod in self.grammar.productions:
                    if prod.lhs != b:
                        continue
                    idx = self.grammar.production_index(prod)
                    new = LR0Item(idx, 0)
                    if new not in result:
                        result.add(new)
                        changed = True
        return result

    def _goto0(self, items: Set[LR0Item], symbol: str) -> Set[LR0Item]:
        moved = {
            LR0Item(it.prod_index, it.dot + 1)
            for it in items
            if it.dot < len(self.grammar.productions[it.prod_index].rhs)
            and self.grammar.productions[it.prod_index].rhs[it.dot] == symbol
        }
        return self._closure0(moved) if moved else set()

    def _canonical_lr0(self) -> Tuple[List[Set[LR0Item]], Dict[Tuple[int, str], int]]:
        i0 = self._closure0({LR0Item(0, 0)})
        states = [i0]
        transitions: Dict[Tuple[int, str], int] = {}
        symbols = sorted(self.grammar.terminals | self.grammar.nonterminals - {EPSILON})
        queue = [0]
        while queue:
            s = queue.pop(0)
            for sym in symbols:
                g = self._goto0(states[s], sym)
                if not g:
                    continue
                if g in states:
                    j = states.index(g)
                else:
                    j = len(states)
                    states.append(g)
                    queue.append(j)
                transitions[(s, sym)] = j
        return states, transitions

    # ---------- LR(1) ----------

    def _closure1(self, items: Set[LR1Item]) -> Set[LR1Item]:
        result = set(items)
        changed = True
        while changed:
            changed = False
            for it in list(result):
                p = self.grammar.productions[it.prod_index]
                if it.dot >= len(p.rhs):
                    continue
                b = p.rhs[it.dot]
                if b not in self.grammar.nonterminals:
                    continue
                for la in self._first_after_dot(p, it.dot, it.lookahead):
                    for prod in self.grammar.productions:
                        if prod.lhs != b:
                            continue
                        idx = self.grammar.production_index(prod)
                        new = LR1Item(idx, 0, la)
                        if new not in result:
                            result.add(new)
                            changed = True
        return result

    def _first_after_dot(self, prod: Production, dot: int, lookahead: str) -> Set[str]:
        beta = list(prod.rhs[dot + 1 :])
        if not beta:
            return {lookahead}
        out: Set[str] = set()
        for i, sym in enumerate(beta):
            if sym in self.grammar.terminals:
                out.add(sym)
                return out
            out |= self.first.get(sym, set()) - {EPSILON}
            if EPSILON not in self.first.get(sym, set()):
                return out
            if i == len(beta) - 1:
                out.add(lookahead)
        return out

    def _goto1(self, items: Set[LR1Item], symbol: str) -> Set[LR1Item]:
        moved = {
            LR1Item(it.prod_index, it.dot + 1, it.lookahead)
            for it in items
            if it.dot < len(self.grammar.productions[it.prod_index].rhs)
            and self.grammar.productions[it.prod_index].rhs[it.dot] == symbol
        }
        return self._closure1(moved) if moved else set()

    def _canonical_lr1(self) -> Tuple[List[Set[LR1Item]], Dict[Tuple[int, str], int]]:
        start = self._closure1({LR1Item(0, 0, END_MARKER)})
        states = [start]
        transitions: Dict[Tuple[int, str], int] = {}
        symbols = sorted(self.grammar.terminals | self.grammar.nonterminals - {EPSILON})
        queue = [0]
        while queue:
            s = queue.pop(0)
            for sym in symbols:
                g = self._goto1(states[s], sym)
                if not g:
                    continue
                if g in states:
                    j = states.index(g)
                else:
                    j = len(states)
                    states.append(g)
                    queue.append(j)
                transitions[(s, sym)] = j
        return states, transitions

    def _merge_lalr(
        self, lr1_states: List[Set[LR1Item]], lr1_trans: Dict[Tuple[int, str], int]
    ) -> Tuple[List[Set[LR1Item]], Dict[Tuple[int, str], int]]:
        core_groups: Dict[frozenset, List[int]] = {}
        for i, st in enumerate(lr1_states):
            core = frozenset(it.core_key() for it in st)
            core_groups.setdefault(core, []).append(i)

        merged: List[Set[LR1Item]] = []
        old_to_new: Dict[int, int] = {}
        for members in core_groups.values():
            combined: Set[LR1Item] = set()
            for m in members:
                combined |= lr1_states[m]
                old_to_new[m] = len(merged)
            merged.append(combined)

        symbols = sorted(self.grammar.terminals | self.grammar.nonterminals - {EPSILON})
        new_trans: Dict[Tuple[int, str], int] = {}
        for i, st in enumerate(merged):
            for sym in symbols:
                g = self._goto1(st, sym)
                if not g:
                    continue
                core = frozenset(x.core_key() for x in g)
                for j, st2 in enumerate(merged):
                    if frozenset(x.core_key() for x in st2) == core:
                        new_trans[(i, sym)] = j
                        break
        return merged, new_trans

    def _labels_lr0(self, states: List[Set[LR0Item]]) -> List[str]:
        return [
            "\n".join(
                item_display(it, self.grammar)
                for it in sorted(st, key=lambda x: (x.prod_index, x.dot))
            )
            for st in states
        ]

    def _labels_lr1(self, states: List[Set[LR1Item]]) -> List[str]:
        return [
            "\n".join(
                lr1_item_display(it, self.grammar)
                for it in sorted(st, key=lambda x: (x.prod_index, x.dot, x.lookahead))
            )
            for st in states
        ]

    def _set_action(
        self,
        action: Dict[Tuple[int, str], LRAction],
        conflicts: List[str],
        i: int,
        a: str,
        act: LRAction,
    ) -> None:
        key = (i, a)
        if key in action and action[key].kind != act.kind:
            conflicts.append(
                f"Estado {i}, '{a}': {action[key].kind} (prod {action[key].value}) "
                f"vs {act.kind} (prod {act.value})"
            )
        elif key in action and action[key].kind == "reduce" and act.kind == "reduce":
            if action[key].value != act.value:
                conflicts.append(
                    f"Reduce-reduce en estado {i}, '{a}': "
                    f"prod {action[key].value} vs {act.value}"
                )
        action[key] = act

    def _build_tables(self) -> LRTables:
        action: Dict[Tuple[int, str], LRAction] = {}
        goto: Dict[Tuple[int, str], int] = {}
        conflicts: List[str] = []
        terminals = sorted(self.grammar.terminals)

        if self.parser_type in (ParserType.LR1, ParserType.LALR1):
            lr1_states, trans = self._canonical_lr1()
            self._lr1_states = lr1_states
            if self.parser_type == ParserType.LALR1:
                lr1_states, trans = self._merge_lalr(lr1_states, trans)
            state_items_lr1 = lr1_states
            labels = self._labels_lr1(lr1_states)
            lr0_states = [{it.lr0_core() for it in st} for st in lr1_states]
        else:
            lr0_states, trans = self._canonical_lr0()
            state_items_lr1 = None
            labels = self._labels_lr0(lr0_states)

        for (i, sym), j in trans.items():
            if sym in self.grammar.terminals:
                self._set_action(action, conflicts, i, sym, LRAction("shift", j))
            elif sym in self.grammar.nonterminals:
                goto[(i, sym)] = j

        for i in range(len(lr0_states)):
            lr0_items = lr0_states[i]
            lr1_items = state_items_lr1[i] if state_items_lr1 else None

            for it in lr0_items:
                p = self.grammar.productions[it.prod_index]
                if it.dot < len(p.rhs):
                    continue
                if p.lhs == self.grammar.start_symbol:
                    self._set_action(action, conflicts, i, END_MARKER, LRAction("accept"))
                    continue

                if self.parser_type == ParserType.LR0:
                    for a in terminals:
                        self._set_action(
                            action, conflicts, i, a, LRAction("reduce", it.prod_index)
                        )
                elif self.parser_type == ParserType.SLR1:
                    for a in self.follow.get(p.lhs, set()) | {END_MARKER}:
                        if a in terminals or a == END_MARKER:
                            self._set_action(
                                action, conflicts, i, a, LRAction("reduce", it.prod_index)
                            )
                else:
                    for it1 in lr1_items or []:
                        if it1.prod_index == it.prod_index and it1.dot == it.dot:
                            self._set_action(
                                action,
                                conflicts,
                                i,
                                it1.lookahead,
                                LRAction("reduce", it.prod_index),
                            )

        return LRTables(
            action=action,
            goto=goto,
            states=lr0_states,
            state_labels=labels,
            transitions=trans,
            conflicts=conflicts,
        )

    def automaton_to_dict(self) -> dict:
        edges = [
            {
                "from": s,
                "to": j,
                "symbol": sym,
                "type": "shift" if sym in self.grammar.terminals else "goto",
            }
            for (s, sym), j in self.tables.transitions.items()
        ]
        return {"states": self.tables.state_labels, "edges": edges}

    def parse(self, tokens: List[str]) -> ParseResult:
        input_tokens = tokens + [END_MARKER]
        stack: List[int] = [0]
        index = 0
        steps: List[ParseStep] = []
        step_n = 0
        node_stack: List[ParseNode] = []

        while True:
            step_n += 1
            state = stack[-1]
            current = input_tokens[index]
            act = self.tables.action.get((state, current))
            stack_repr = [str(s) for s in stack]
            remaining = input_tokens[index:]

            if act is None:
                steps.append(
                    ParseStep(
                        step_n,
                        "error",
                        f"Sin acción en estado {state} con lookahead '{current}'",
                        stack_repr,
                        remaining,
                    )
                )
                return ParseResult(
                    False,
                    steps,
                    None,
                    f"Error sintáctico en '{current}'",
                    metadata=self.build_info(),
                )

            if act.kind == "shift":
                steps.append(
                    ParseStep(
                        step_n,
                        "shift",
                        f"Desplazar '{current}' → estado {act.value}",
                        stack_repr + [current, str(act.value)],
                        remaining[1:],
                    )
                )
                node_stack.append(ParseNode(current, value=current))
                stack.append(act.value)
                index += 1

            elif act.kind == "reduce":
                prod = self.grammar.productions[act.value]
                rhs_len = len(prod.rhs)
                steps.append(
                    ParseStep(
                        step_n,
                        "reduce",
                        f"Reducir por {prod}",
                        stack_repr,
                        remaining,
                        extra={"production": str(prod), "index": act.value},
                    )
                )
                children: List[ParseNode] = []
                for _ in range(rhs_len):
                    stack.pop()
                    if node_stack:
                        children.insert(0, node_stack.pop())
                if rhs_len == 0:
                    children = [ParseNode(EPSILON, value=EPSILON)]
                node_stack.append(ParseNode(prod.lhs, children=children))
                top = stack[-1]
                g = self.tables.goto.get((top, prod.lhs))
                if g is None:
                    return ParseResult(
                        False,
                        steps,
                        None,
                        f"GOTO[{top}, {prod.lhs}] indefinido",
                        metadata=self.build_info(),
                    )
                stack.append(g)

            elif act.kind == "accept":
                steps.append(
                    ParseStep(
                        step_n,
                        "accept",
                        "Cadena aceptada",
                        stack_repr,
                        remaining,
                    )
                )
                tree = node_stack[0] if node_stack else None
                return ParseResult(True, steps, tree, metadata=self.build_info())

            else:
                return ParseResult(
                    False, steps, None, "Acción de error", metadata=self.build_info()
                )

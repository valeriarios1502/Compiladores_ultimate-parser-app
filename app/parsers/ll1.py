"""Analizador predictivo LL(1)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from app.grammar.first_follow import compute_first, compute_follow, first_string, is_ll1
from app.grammar.grammar import EPSILON, END_MARKER, Grammar, Production
from app.parsers.common import ParseNode, ParseResult, ParseStep


class LL1Parser:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self.first = compute_first(grammar)
        self.follow = compute_follow(grammar, self.first)
        self.table = self._build_table()
        self.ll1_ok, self.conflicts = is_ll1(grammar, self.first, self.follow)

    def _build_table(self) -> Dict[Tuple[str, str], Production]:
        table: Dict[Tuple[str, str], Production] = {}
        for p in self.grammar.productions:
            if not p.rhs:
                for a in self.follow[p.lhs]:
                    key = (p.lhs, a)
                    if key in table and table[key] != p:
                        pass  # conflicto registrado en is_ll1
                    table[key] = p
            else:
                f = first_string(list(p.rhs), self.grammar, self.first)
                for a in f - {EPSILON}:
                    table[(p.lhs, a)] = p
                if EPSILON in f:
                    for a in self.follow[p.lhs]:
                        table[(p.lhs, a)] = p
        return table

    def table_to_dict(self) -> dict:
        entries = []
        for (nt, term), prod in sorted(self.table.items()):
            entries.append({
                "nonterminal": nt,
                "terminal": term,
                "production": str(prod),
                "rhs": list(prod.rhs),
            })
        return {
            "is_ll1": self.ll1_ok,
            "conflicts": self.conflicts,
            "entries": entries,
        }

    def build_info(self) -> dict:
        return {
            "parser": "ll1",
            "first": {k: sorted(v) for k, v in self.first.items()},
            "follow": {k: sorted(v) for k, v in self.follow.items()},
            "table": self.table_to_dict(),
        }

    def parse(self, tokens: List[str]) -> ParseResult:
        stack: List[str] = [END_MARKER, self.grammar.start_symbol]
        input_tokens = tokens + [END_MARKER]
        index = 0
        steps: List[ParseStep] = []
        step_n = 0
        tree_stack: List[ParseNode] = []

        while stack:
            step_n += 1
            top = stack[-1]
            current = input_tokens[index] if index < len(input_tokens) else END_MARKER

            if top in self.grammar.terminals or top == END_MARKER:
                if top == current:
                    stack.pop()
                    if top != END_MARKER:
                        tree_stack.append(ParseNode(top, value=current))
                        index += 1
                    steps.append(
                        ParseStep(
                            step_n,
                            "match",
                            f"Coincidir '{top}'",
                            stack=list(stack),
                            input_remaining=input_tokens[index:],
                        )
                    )
                    if top == END_MARKER:
                        return ParseResult(
                            True,
                            steps,
                            tree_stack[0] if tree_stack else None,
                            metadata=self.build_info(),
                        )
                else:
                    steps.append(
                        ParseStep(
                            step_n,
                            "error",
                            f"Error: se esperaba '{top}', se encontró '{current}'",
                            stack=list(stack),
                            input_remaining=input_tokens[index:],
                        )
                    )
                    return ParseResult(
                        False,
                        steps,
                        None,
                        f"Error en '{current}'",
                        metadata=self.build_info(),
                    )
            else:
                prod = self.table.get((top, current))
                if prod is None:
                    steps.append(
                        ParseStep(
                            step_n,
                            "error",
                            f"Sin entrada en tabla M[{top}, {current}]",
                            stack=list(stack),
                            input_remaining=input_tokens[index:],
                        )
                    )
                    return ParseResult(
                        False,
                        steps,
                        None,
                        f"Entrada vacía en tabla para ({top}, {current})",
                        metadata=self.build_info(),
                    )
                stack.pop()
                if prod.rhs:
                    for sym in reversed(prod.rhs):
                        stack.append(sym)
                steps.append(
                    ParseStep(
                        step_n,
                        "expand",
                        f"Aplicar {prod}",
                        stack=list(stack),
                        input_remaining=input_tokens[index:],
                        extra={"production": str(prod)},
                    )
                )

        return ParseResult(False, steps, None, "Pila vacía inesperadamente", metadata=self.build_info())

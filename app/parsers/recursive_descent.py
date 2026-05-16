"""Analizador por descenso recursivo predictivo (usa FIRST)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from app.grammar.first_follow import compute_first, compute_follow, first_string
from app.grammar.grammar import EPSILON, END_MARKER, Grammar, Production
from app.parsers.common import ParseNode, ParseResult, ParseStep


class RecursiveDescentParser:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self.first = compute_first(grammar)
        self.follow = compute_follow(grammar, self.first)

    def build_info(self) -> dict:
        return {
            "parser": "recursive_descent",
            "first": {k: sorted(v) for k, v in self.first.items()},
            "follow": {k: sorted(v) for k, v in self.follow.items()},
            "productions": [str(p) for p in self.grammar.productions],
        }

    def parse(self, tokens: List[str]) -> ParseResult:
        self._tokens = tokens + [END_MARKER]
        self._pos = 0
        self._steps: List[ParseStep] = []
        self._step_num = 0

        try:
            tree = self._parse_nonterminal(self.grammar.start_symbol)
            if self._current() == END_MARKER:
                self._record("accept", "Cadena aceptada", tree=tree)
                return ParseResult(True, self._steps, tree, metadata=self.build_info())
            self._record("error", f"Entrada sobrante: {self._remaining()}")
            return ParseResult(False, self._steps, tree, "Entrada no consumida completamente")
        except SyntaxError as e:
            return ParseResult(False, self._steps, None, str(e), metadata=self.build_info())

    def _current(self) -> str:
        if self._pos >= len(self._tokens):
            return END_MARKER
        return self._tokens[self._pos]

    def _remaining(self) -> List[str]:
        return self._tokens[self._pos:]

    def _advance(self) -> str:
        tok = self._current()
        self._pos += 1
        return tok

    def _record(self, action: str, desc: str, **extra) -> None:
        self._step_num += 1
        self._steps.append(
            ParseStep(
                self._step_num,
                action,
                desc,
                stack=[self.grammar.start_symbol],
                input_remaining=self._remaining(),
                extra=extra,
            )
        )

    def _parse_nonterminal(self, nt: str) -> ParseNode:
        lookahead = self._current()
        chosen: Optional[Production] = None

        for prod in self.grammar.productions_for(nt):
            if not prod.rhs:
                if lookahead in self.follow[nt] or lookahead == END_MARKER:
                    chosen = prod
                    break
                continue
            f = first_string(list(prod.rhs), self.grammar, self.first)
            if lookahead in f or (EPSILON in f and lookahead in self.follow[nt]):
                chosen = prod
                break

        if chosen is None:
            raise SyntaxError(
                f"No hay producción para {nt} con lookahead '{lookahead}' "
                f"(entrada restante: {self._remaining()})"
            )

        self._record(
            "expand",
            f"Expandir {nt} → {' '.join(chosen.rhs) if chosen.rhs else EPSILON}",
            nonterminal=nt,
            production=str(chosen),
        )

        children: List[ParseNode] = []
        for sym in chosen.rhs:
            if sym in self.grammar.terminals or sym == EPSILON:
                if sym == EPSILON:
                    children.append(ParseNode(EPSILON, value=EPSILON))
                    continue
                if self._current() != sym:
                    raise SyntaxError(
                        f"Se esperaba '{sym}', se encontró '{self._current()}'"
                    )
                tok = self._advance()
                self._record("match", f"Coincidir terminal '{sym}'", token=sym)
                children.append(ParseNode(sym, value=tok))
            else:
                children.append(self._parse_nonterminal(sym))

        if not chosen.rhs:
            return ParseNode(nt, children=[ParseNode(EPSILON, value=EPSILON)])
        if len(children) == 1:
            return ParseNode(nt, children=children)
        return ParseNode(nt, children=children)

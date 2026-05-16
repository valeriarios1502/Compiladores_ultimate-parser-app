"""Conjuntos FIRST y FOLLOW."""

from __future__ import annotations

from typing import Dict, List, Set

from app.grammar.grammar import EPSILON, END_MARKER, Grammar, Production


def compute_first(grammar: Grammar) -> Dict[str, Set[str]]:
    first: Dict[str, Set[str]] = {
        nt: set() for nt in grammar.nonterminals
    }
    for t in grammar.terminals:
        first[t] = {t}

    changed = True
    while changed:
        changed = False
        for p in grammar.productions:
            lhs = p.lhs
            before = len(first[lhs])
            if not p.rhs:
                first[lhs].add(EPSILON)
            else:
                first[lhs] |= _first_of_sequence(p.rhs, grammar, first)
            if len(first[lhs]) != before:
                changed = True
    return first


def _first_of_sequence(
    symbols: tuple,
    grammar: Grammar,
    first: Dict[str, Set[str]],
) -> Set[str]:
    result: Set[str] = set()
    if not symbols:
        result.add(EPSILON)
        return result

    for i, sym in enumerate(symbols):
        if sym in grammar.terminals or sym == EPSILON:
            result.add(sym)
            break
        sym_first = first.get(sym, set())
        result |= sym_first - {EPSILON}
        if EPSILON not in sym_first:
            break
        if i == len(symbols) - 1:
            result.add(EPSILON)
    return result


def first_string(
    symbols: List[str],
    grammar: Grammar,
    first: Dict[str, Set[str]],
) -> Set[str]:
    return _first_of_sequence(tuple(symbols), grammar, first)


def compute_follow(grammar: Grammar, first: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    follow: Dict[str, Set[str]] = {nt: set() for nt in grammar.nonterminals}
    follow[grammar.start_symbol].add(END_MARKER)

    changed = True
    while changed:
        changed = False
        for p in grammar.productions:
            for i, sym in enumerate(p.rhs):
                if sym not in grammar.nonterminals:
                    continue
                beta = list(p.rhs[i + 1 :])
                before = len(follow[sym])
                if beta:
                    fb = first_string(beta, grammar, first)
                    follow[sym] |= fb - {EPSILON}
                    if EPSILON in fb:
                        follow[sym] |= follow[p.lhs]
                else:
                    follow[sym] |= follow[p.lhs]
                if len(follow[sym]) != before:
                    changed = True
    return follow


def is_ll1(grammar: Grammar, first: Dict[str, Set[str]], follow: Dict[str, Set[str]]) -> tuple[bool, List[str]]:
    """Comprueba condiciones LL(1); devuelve (ok, conflictos)."""
    conflicts: List[str] = []
    for nt in grammar.nonterminals:
        prods = grammar.productions_for(nt)
        for i in range(len(prods)):
            fi = first_string(list(prods[i].rhs), grammar, first) if prods[i].rhs else {EPSILON}
            for j in range(i + 1, len(prods)):
                fj = first_string(list(prods[j].rhs), grammar, first) if prods[j].rhs else {EPSILON}
                inter = fi & fj
                if EPSILON in inter:
                    inter = (inter - {EPSILON}) | (fi & fj & follow[nt])
                if inter:
                    conflicts.append(
                        f"Conflicto LL(1) en {nt}: {prods[i]} vs {prods[j]} en FIRST∩ = {sorted(inter)}"
                    )
    return len(conflicts) == 0, conflicts

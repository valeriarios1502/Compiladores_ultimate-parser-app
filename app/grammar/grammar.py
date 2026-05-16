"""Representación y análisis de gramáticas libres de contexto."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

EPSILON = "ε"
END_MARKER = "$"


@dataclass(frozen=True)
class Production:
    lhs: str
    rhs: Tuple[str, ...]

    def __str__(self) -> str:
        body = " ".join(self.rhs) if self.rhs else EPSILON
        return f"{self.lhs} → {body}"


@dataclass
class Grammar:
    start_symbol: str
    productions: List[Production]
    terminals: Set[str] = field(default_factory=set)
    nonterminals: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.terminals or not self.nonterminals:
            self._infer_symbols()

    def _infer_symbols(self) -> None:
        nts: Set[str] = set()
        syms: Set[str] = set()
        for p in self.productions:
            nts.add(p.lhs)
            syms.update(p.rhs)
        self.nonterminals = nts
        self.terminals = syms - nts - {EPSILON}

    @property
    def augmented_start(self) -> str:
        return f"{self.start_symbol}'"

    def augmented(self) -> Grammar:
        """Gramática aumentada S' → S para analizadores LR."""
        aug_start = self.augmented_start
        new_prods = [
            Production(aug_start, (self.start_symbol,)),
            *self.productions,
        ]
        return Grammar(
            start_symbol=aug_start,
            productions=new_prods,
            terminals=self.terminals | {END_MARKER},
            nonterminals=self.nonterminals | {aug_start},
        )

    def productions_for(self, lhs: str) -> List[Production]:
        return [p for p in self.productions if p.lhs == lhs]

    def production_index(self, prod: Production) -> int:
        for i, p in enumerate(self.productions):
            if p.lhs == prod.lhs and p.rhs == prod.rhs:
                return i
        raise ValueError(f"Producción no encontrada: {prod}")

    def to_dict(self) -> dict:
        grouped: Dict[str, List[List[str]]] = {}
        for p in self.productions:
            grouped.setdefault(p.lhs, []).append(list(p.rhs))
        return {
            "start_symbol": self.start_symbol,
            "productions": grouped,
            "terminals": sorted(self.terminals),
            "nonterminals": sorted(self.nonterminals),
        }


def parse_grammar_text(text: str, start_symbol: Optional[str] = None) -> Grammar:
    """
    Parsea gramática en formato:
        S -> a S | b
        E -> E + T | T
    Símbolos: identificadores alfanuméricos o literales entre comillas.
    ε, epsilon, e se interpretan como cadena vacía.
    """
    productions: List[Production] = []
    first_lhs: Optional[str] = None
    line_re = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:->|→)\s*(.+?)\s*$"
    )

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = line_re.match(line)
        if not m:
            raise ValueError(f"Línea de gramática inválida: {raw_line!r}")
        lhs = m.group(1)
        if first_lhs is None:
            first_lhs = lhs
        alts = re.split(r"\s*\|\s*", m.group(2))
        for alt in alts:
            rhs = _parse_rhs(alt.strip())
            productions.append(Production(lhs, tuple(rhs)))

    if not productions:
        raise ValueError("La gramática no contiene producciones")

    start = start_symbol or first_lhs
    return Grammar(start_symbol=start, productions=productions)


def grammar_from_dict(data: dict) -> Grammar:
    start = data["start_symbol"]
    prods: List[Production] = []
    for lhs, alternatives in data["productions"].items():
        for alt in alternatives:
            rhs = tuple(alt) if alt else ()
            prods.append(Production(lhs, rhs))
    return Grammar(start_symbol=start, productions=prods)


def _parse_rhs(alt: str) -> List[str]:
    if alt.lower() in ("ε", "epsilon", "e", ""):
        return []
    tokens: List[str] = []
    i = 0
    while i < len(alt):
        if alt[i] in " \t":
            i += 1
            continue
        if alt[i] in "'\"":
            quote = alt[i]
            j = i + 1
            while j < len(alt) and alt[j] != quote:
                j += 1
            tokens.append(alt[i + 1 : j])
            i = j + 1
            continue
        m = re.match(r"[A-Za-z0-9_]+", alt[i:])
        if m:
            tokens.append(m.group(0))
            i += len(m.group(0))
        else:
            tokens.append(alt[i])
            i += 1
    return tokens


def tokenize_input(text: str, mode: str = "auto") -> List[str]:
    """
    Tokeniza cadena de entrada.
    - auto: separa por espacios; si no hay espacios, carácter a carácter.
    - whitespace: split por espacios.
    - char: un token por carácter.
    """
    text = text.strip()
    if not text:
        return []
    if mode == "char":
        return list(text.replace(" ", ""))
    if mode == "whitespace":
        return text.split()
    if " " in text or "\t" in text:
        return text.split()
    return list(text)

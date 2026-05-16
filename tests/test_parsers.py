import pytest

from app.grammar.grammar import parse_grammar_text, tokenize_input
from app.parsers.ll1 import LL1Parser
from app.parsers.lr.engine import LRParser, ParserType
from app.parsers.recursive_descent import RecursiveDescentParser

# Gramática de paréntesis balanceados: S -> ( S ) | ε
PARENS = """
S -> ( S ) |
"""

# Gramática aritmética simple LL(1)
# E -> T E'
# E' -> + T E' | ε
# T -> id
EXPR = """
E -> T E1
E1 -> + T E1 |
T -> id
"""


@pytest.fixture
def parens_grammar():
    return parse_grammar_text(PARENS.strip())


@pytest.fixture
def expr_grammar():
    return parse_grammar_text(EXPR.strip())


def test_tokenize_char():
    assert tokenize_input("id+id", "auto") == ["i", "d", "+", "i", "d"] or tokenize_input(
        "a + b", "whitespace"
    ) == ["a", "+", "b"]


def test_ll1_parse_expr(expr_grammar):
    tokens = ["id", "+", "id"]
    p = LL1Parser(expr_grammar)
    r = p.parse(tokens)
    assert r.accepted, r.error


def test_recursive_descent_expr(expr_grammar):
    tokens = ["id", "+", "id"]
    p = RecursiveDescentParser(expr_grammar)
    r = p.parse(tokens)
    assert r.accepted


def test_lr0_parens(parens_grammar):
    """LR(0) en paréntesis tiene conflictos shift/reduce; verificamos autómata y conflictos."""
    p = LRParser(parens_grammar, ParserType.LR0)
    assert len(p.tables.states) > 0
    assert len(p.tables.conflicts) > 0


def test_lr0_simple_accept():
    g = parse_grammar_text("S -> a | b")
    p = LRParser(g, ParserType.LR0)
    assert p.parse(["a"]).accepted
    assert p.parse(["b"]).accepted


def test_slr1_expr(expr_grammar):
    tokens = ["id", "+", "id"]
    p = LRParser(expr_grammar, ParserType.SLR1)
    r = p.parse(tokens)
    assert r.accepted


def test_lalr1_expr(expr_grammar):
    tokens = ["id", "+", "id"]
    p = LRParser(expr_grammar, ParserType.LALR1)
    tables = p.tables
    assert tables.action
    r = p.parse(tokens)
    assert r.accepted


def test_lr1_expr(expr_grammar):
    tokens = ["id", "+", "id"]
    p = LRParser(expr_grammar, ParserType.LR1)
    r = p.parse(tokens)
    assert r.accepted


def test_parse_text_grammar():
    g = parse_grammar_text("S -> a S | b")
    assert g.start_symbol == "S"
    assert len(g.productions) == 2

from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter, HTTPException

from app.grammar.first_follow import compute_first, compute_follow, is_ll1
from app.grammar.grammar import grammar_from_dict, parse_grammar_text, tokenize_input
from app.models.schemas import (
    ApiResponse,
    CompareRequest,
    ExplainErrorRequest,
    GrammarAnalyzeRequest,
    GrammarTextRequest,
    LL1TransformRequest,
    ParseRequest,
)
from app.parsers.ll1 import LL1Parser
from app.parsers.lr.engine import LRParser, ParserType
from app.parsers.recursive_descent import RecursiveDescentParser
from app.services.explain import (
    enhance_with_openai,
    explain_parse_error,
    suggest_ll1_transformations,
)

router = APIRouter(prefix="/api")


def _resolve_grammar(
    grammar: Optional[dict] = None,
    grammar_text: Optional[str] = None,
    start_symbol: Optional[str] = None,
):
    if grammar_text:
        return parse_grammar_text(grammar_text, start_symbol)
    if grammar:
        g = grammar_from_dict(grammar.model_dump() if hasattr(grammar, "model_dump") else grammar)
        if start_symbol:
            g.start_symbol = start_symbol
        return g
    raise HTTPException(400, "Proporciona grammar o grammar_text")


@router.get("/health")
def health():
    return {"status": "ok", "service": "ultimate-parser-backend"}


@router.post("/grammar/parse-text", response_model=ApiResponse)
def parse_text(req: GrammarTextRequest):
    try:
        g = parse_grammar_text(req.grammar_text, req.start_symbol)
        return ApiResponse(success=True, data=g.to_dict())
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/grammar/analyze", response_model=ApiResponse)
def analyze_grammar(req: GrammarAnalyzeRequest):
    try:
        g = _resolve_grammar(req.grammar, req.grammar_text, req.start_symbol)
        first = compute_first(g)
        follow = compute_follow(g, first)
        ll1_ok, conflicts = is_ll1(g, first, follow)
        return ApiResponse(
            success=True,
            data={
                "grammar": g.to_dict(),
                "first": {k: sorted(v) for k, v in first.items()},
                "follow": {k: sorted(v) for k, v in follow.items()},
                "is_ll1": ll1_ok,
                "ll1_conflicts": conflicts,
            },
        )
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))


def _parse_endpoint(parser_factory: Callable, req: ParseRequest, tables_only: bool = False):
    try:
        g = _resolve_grammar(req.grammar, req.grammar_text, req.start_symbol)
        tokens = tokenize_input(req.input_string, req.tokenize_mode)
        parser = parser_factory(g)
        if tables_only:
            info = parser.build_info() if hasattr(parser, "build_info") else {}
            if hasattr(parser, "table_to_dict"):
                info["table"] = parser.table_to_dict()
            return ApiResponse(success=True, data=info)
        result = parser.parse(tokens)
        return ApiResponse(
            success=True,
            data={
                **result.to_dict(),
                "tokens": tokens,
            },
        )
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/parsers/recursive-descent/info")
def rd_info(req: ParseRequest):
    return _parse_endpoint(RecursiveDescentParser, req, tables_only=True)


@router.post("/parsers/recursive-descent/parse")
def rd_parse(req: ParseRequest):
    return _parse_endpoint(RecursiveDescentParser, req)


@router.post("/parsers/ll1/tables")
def ll1_tables(req: ParseRequest):
    return _parse_endpoint(LL1Parser, req, tables_only=True)


@router.post("/parsers/ll1/parse")
def ll1_parse(req: ParseRequest):
    return _parse_endpoint(LL1Parser, req)


def _lr_route(ptype: ParserType, req: ParseRequest, tables_only: bool):
    return _parse_endpoint(lambda g: LRParser(g, ptype), req, tables_only)


@router.post("/parsers/lr0/automaton")
def lr0_automaton(req: ParseRequest):
    return _lr_route(ParserType.LR0, req, True)


@router.post("/parsers/lr0/tables")
def lr0_tables(req: ParseRequest):
    return _lr_route(ParserType.LR0, req, True)


@router.post("/parsers/lr0/parse")
def lr0_parse(req: ParseRequest):
    return _lr_route(ParserType.LR0, req, False)


@router.post("/parsers/slr1/tables")
def slr1_tables(req: ParseRequest):
    return _lr_route(ParserType.SLR1, req, True)


@router.post("/parsers/slr1/parse")
def slr1_parse(req: ParseRequest):
    return _lr_route(ParserType.SLR1, req, False)


@router.post("/parsers/lr1/tables")
def lr1_tables(req: ParseRequest):
    return _lr_route(ParserType.LR1, req, True)


@router.post("/parsers/lr1/parse")
def lr1_parse(req: ParseRequest):
    return _lr_route(ParserType.LR1, req, False)


@router.post("/parsers/lalr1/tables")
def lalr1_tables(req: ParseRequest):
    return _lr_route(ParserType.LALR1, req, True)


@router.post("/parsers/lalr1/parse")
def lalr1_parse(req: ParseRequest):
    return _lr_route(ParserType.LALR1, req, False)


PARSER_MAP = {
    "recursive_descent": RecursiveDescentParser,
    "ll1": LL1Parser,
    "lr0": lambda g: LRParser(g, ParserType.LR0),
    "slr1": lambda g: LRParser(g, ParserType.SLR1),
    "lr1": lambda g: LRParser(g, ParserType.LR1),
    "lalr1": lambda g: LRParser(g, ParserType.LALR1),
}


@router.post("/parsers/compare", response_model=ApiResponse)
def compare_parsers(req: CompareRequest):
    try:
        g = parse_grammar_text(req.grammar_text, req.start_symbol)
        tokens = tokenize_input(req.input_string, req.tokenize_mode)
        results = {}
        for name in req.parsers:
            factory = PARSER_MAP.get(name)
            if not factory:
                results[name] = {"error": f"Parser desconocido: {name}"}
                continue
            parser = factory(g)
            pr = parser.parse(tokens)
            results[name] = {
                "accepted": pr.accepted,
                "error": pr.error,
                "steps_count": len(pr.steps),
            }
        return ApiResponse(success=True, data={"tokens": tokens, "results": results})
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/ai/explain-error", response_model=ApiResponse)
async def explain_error(req: ExplainErrorRequest):
    grammar = None
    if req.grammar_text:
        try:
            grammar = parse_grammar_text(req.grammar_text)
        except ValueError:
            pass
    result = explain_parse_error(req.parser, req.error, req.step, grammar)
    enhanced = await enhance_with_openai(result["explanation"])
    if enhanced:
        result["explanation"] = enhanced
        result["ai_enhanced"] = True
    return ApiResponse(success=True, data=result)


@router.post("/ai/ll1-suggestions", response_model=ApiResponse)
def ll1_suggestions(req: LL1TransformRequest):
    try:
        g = parse_grammar_text(req.grammar_text, req.start_symbol)
        return ApiResponse(success=True, data=suggest_ll1_transformations(g))
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))

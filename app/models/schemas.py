from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GrammarDict(BaseModel):
    start_symbol: str
    productions: Dict[str, List[List[str]]]


class GrammarTextRequest(BaseModel):
    grammar_text: str
    start_symbol: Optional[str] = None


class GrammarAnalyzeRequest(BaseModel):
    grammar: GrammarDict
    grammar_text: Optional[str] = None
    start_symbol: Optional[str] = None


class ParseRequest(BaseModel):
    grammar: Optional[GrammarDict] = None
    grammar_text: Optional[str] = None
    start_symbol: Optional[str] = None
    input_string: str
    tokenize_mode: Literal["auto", "whitespace", "char"] = "auto"


class CompareRequest(BaseModel):
    grammar_text: str
    start_symbol: Optional[str] = None
    input_string: str
    parsers: List[str] = Field(
        default_factory=lambda: [
            "recursive_descent",
            "ll1",
            "lr0",
            "slr1",
            "lalr1",
            "lr1",
        ]
    )
    tokenize_mode: Literal["auto", "whitespace", "char"] = "auto"


class ExplainErrorRequest(BaseModel):
    parser: str
    error: str
    step: Optional[dict] = None
    grammar_text: Optional[str] = None


class LL1TransformRequest(BaseModel):
    grammar_text: str
    start_symbol: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

"""Explicaciones de errores y sugerencias para gramáticas (plantillas + IA opcional)."""

from __future__ import annotations

import os
from typing import List, Optional

from app.grammar.first_follow import compute_first, compute_follow, is_ll1
from app.grammar.grammar import Grammar, parse_grammar_text


def explain_parse_error(
    parser: str,
    error: str,
    step: Optional[dict] = None,
    grammar: Optional[Grammar] = None,
) -> dict:
    """Genera explicación en lenguaje natural de un error sintáctico."""
    parts: List[str] = []
    parts.append(f"El analizador **{parser.upper()}** rechazó la cadena.")
    parts.append(error)

    if step:
        action = step.get("action", "")
        stack = step.get("stack", [])
        remaining = step.get("input_remaining", [])
        if action == "error":
            parts.append(
                f"En el paso {step.get('step', '?')}, la pila era {stack} "
                f"y la entrada restante era {remaining}."
            )
            if remaining:
                parts.append(
                    f"El símbolo '{remaining[0]}' no es válido en este contexto "
                    f"según la tabla o las producciones disponibles."
                )

    suggestions: List[str] = []
    if grammar:
        first = compute_first(grammar)
        follow = compute_follow(grammar, first)
        ok, conflicts = is_ll1(grammar, first, follow)
        if not ok and parser in ("ll1", "recursive_descent"):
            suggestions.append(
                "La gramática no cumple LL(1). Considera eliminar ambigüedad, "
                "factorizar la izquierda o eliminar recursión izquierda."
            )
            suggestions.extend(conflicts[:3])
        if parser.startswith("lr") and "Sin acción" in error:
            suggestions.append(
                "Puede haber conflicto shift/reduce o reduce/reduce. "
                "Prueba SLR(1), LALR(1) o LR(1) si usas LR(0)."
            )

    return {
        "explanation": " ".join(parts),
        "suggestions": suggestions,
        "ai_enhanced": False,
    }


def suggest_ll1_transformations(grammar: Grammar) -> dict:
    """Sugerencias heurísticas para acercar una gramática a LL(1)."""
    tips: List[str] = []
    first = compute_first(grammar)
    follow = compute_follow(grammar, first)
    ok, conflicts = is_ll1(grammar, first, follow)

    left_recursive = []
    for nt in grammar.nonterminals:
        for p in grammar.productions_for(nt):
            if p.rhs and p.rhs[0] == nt:
                left_recursive.append(nt)
                break
    if left_recursive:
        tips.append(
            f"Recursión izquierda en {left_recursive}: reescribe A → Aα | β "
            f"como A → βA' y A' → αA' | ε."
        )

    if not ok:
        tips.append("Conflictos LL(1) detectados — considera factorización izquierda:")
        for c in conflicts[:5]:
            tips.append(c)

    tips.append(
        "Separa operadores por niveles de precedencia (E, T, F) en lugar de "
        "una sola producción ambigua."
    )

    return {
        "is_ll1": ok,
        "conflicts": conflicts,
        "suggestions": tips,
        "first": {k: sorted(v) for k, v in first.items()},
        "follow": {k: sorted(v) for k, v in follow.items()},
    }


async def enhance_with_openai(text: str) -> Optional[str]:
    """Opcional: enriquece explicación con OpenAI si OPENAI_API_KEY está definida."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "Eres un experto en compiladores. Explica errores sintácticos en español, de forma clara y breve.",
                        },
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 400,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None

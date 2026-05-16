"""Ultimate Parser App — API backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes import router

app = FastAPI(
    title="Ultimate Parser API",
    description=(
        "Backend para análisis sintáctico: descenso recursivo, LL(1), "
        "LR(0), SLR(1), LALR(1) y LR(1) con trazas paso a paso y tablas."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Evita 404 cuando el navegador pide el icono por defecto."""
    return Response(status_code=204)


@app.get("/")
def root():
    return {
        "message": "Ultimate Parser API",
        "docs": "/docs",
        "health": "/api/health",
    }

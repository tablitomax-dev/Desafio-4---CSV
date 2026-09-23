"""Regras de dominio sobre as colunas do catalogo (tipos, fuzzy, normalizacao)."""

from __future__ import annotations

from app.catalog.catalog import ColunaDict

TIPOS_IDENTIFICADOR = frozenset({"identificador", "codigo"})
TIPOS_NUMERICOS = frozenset({"numero", "decimal"})
TIPOS_TEMPORAIS = frozenset({"data", "datetime"})


def eh_identificador(coluna: ColunaDict) -> bool:
    """Chaves e identificadores legais (fuzzy proibido, match exato)."""
    return coluna.tipo in TIPOS_IDENTIFICADOR


def permite_fuzzy(coluna: ColunaDict) -> bool:
    """Fuzzy permitido apenas em colunas descritivas marcadas no dicionario."""
    return coluna.fuzzy_permitido and coluna.regra_busca == "fuzzy_controlado"


def normalizacao_para(coluna: ColunaDict) -> str:
    """Estrategia de normalizacao por tipo: numerico | data | identificador | texto."""
    if coluna.tipo in TIPOS_NUMERICOS:
        return "numerico"
    if coluna.tipo in TIPOS_TEMPORAIS:
        return "data"
    if eh_identificador(coluna):
        return "identificador"
    return "texto"

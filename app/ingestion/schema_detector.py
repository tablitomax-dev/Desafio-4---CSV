"""Detecao de schema de um CSV por leitura do cabecalho + dicionario de dados."""

from __future__ import annotations

from app.catalog.catalog import Catalog, TabelaDict

_LIMIAR_CORRESPONDENCIA = 0.5


def detectar_tabela(catalog: Catalog, cabecalhos: list[str]) -> TabelaDict | None:
    """Retorna a tabela do catalogo que melhor corresponde aos cabecalhos do CSV."""
    conjunto = {h.strip().lower() for h in cabecalhos}
    melhor: TabelaDict | None = None
    melhor_score = 0.0
    for tabela in catalog.tabelas:
        origens = {c.origem.strip().lower() for c in tabela.colunas}
        inter = conjunto & origens
        score = len(inter) / max(len(conjunto), 1)
        if score > melhor_score:
            melhor = tabela
            melhor_score = score
    if melhor is not None and melhor_score >= _LIMIAR_CORRESPONDENCIA:
        return melhor
    return None

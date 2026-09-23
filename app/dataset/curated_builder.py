"""Construcao da camada curated: dados tipados e normalizados, prontos para consulta.

Cada coluna canonica gera duas colunas na tabela curated:
- `{canonico}`: valor normalizado/tipado usado pelo agente (busca e agregacao);
- `{canonico}_origem`: valor original do CSV, preservado para apresentacao.

Colunas temporais (data/datetime) sao tipadas como DATE/TIMESTAMP para que o
SQL gerado pelo agente (ex.: `BETWEEN DATE '...'`) funcione.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.catalog.catalog import TabelaDict
from app.catalog.rules import TIPOS_TEMPORAIS
from app.ingestion.normalizer import normalizar_valor


class CuratedBuilder:
    """Cria a tabela `curated.<nome>` a partir do DataFrame bruto e do dicionario."""

    def construir(self, con: Any, df: pd.DataFrame, tabela: TabelaDict) -> None:
        colunas = {c.origem: c for c in tabela.colunas if c.origem in df.columns}
        if not colunas:
            raise ValueError(
                f"Nenhuma coluna do dicionario encontrada para a tabela {tabela.nome}"
            )

        out: dict[str, Any] = {}
        for origem, coluna in colunas.items():
            raw = df[origem]
            out[f"{coluna.canonico}_origem"] = raw
            out[coluna.canonico] = raw.map(lambda v: normalizar_valor(v, coluna))

        novo = pd.DataFrame(out)
        con.register("__curated", novo)

        selecao: list[str] = []
        for coluna in tabela.colunas:
            origem_col = f"{coluna.canonico}_origem"
            if origem_col in novo.columns:
                selecao.append(f'"{origem_col}"')
            if coluna.canonico not in novo.columns:
                continue
            if coluna.tipo in TIPOS_TEMPORAIS:
                tipo = "TIMESTAMP" if coluna.tipo == "datetime" else "DATE"
                selecao.append(f'CAST("{coluna.canonico}" AS {tipo}) AS "{coluna.canonico}"')
            else:
                selecao.append(f'"{coluna.canonico}"')

        con.execute(
            f'CREATE OR REPLACE TABLE "curated"."{tabela.nome}" '
            f'AS SELECT {", ".join(selecao)} FROM __curated'
        )

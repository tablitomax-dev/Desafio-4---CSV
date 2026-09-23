"""Escrita da camada meta: contexto operacional do dataset.

Cria as tabelas `meta.dataset`, `meta.tables`, `meta.columns`,
`meta.relationships`, `meta.quality_metrics` e `meta.ingestion_errors`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.catalog.catalog import Catalog
from app.contracts import Issue, Relationship


class MetadataWriter:
    """Persiste os metadados do dataset na camada `meta`."""

    def escrever(
        self,
        con: Any,
        dataset_id: str,
        content_fingerprint: str,
        catalog: Catalog,
        relationships: list[Relationship],
        issues: list[Issue],
        metricas: dict[str, int | float | str | None],
    ) -> None:
        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."dataset" ('
            "dataset_id VARCHAR, content_fingerprint VARCHAR, "
            "data_processamento VARCHAR, status VARCHAR)"
        )
        con.execute(
            'INSERT INTO "meta"."dataset" VALUES (?, ?, ?, ?)',
            [
                dataset_id,
                content_fingerprint,
                datetime.now().isoformat(timespec="seconds"),
                "ready",
            ],
        )

        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."tables" ('
            "dataset_id VARCHAR, tabela VARCHAR, granularidade VARCHAR, "
            "linhas BIGINT, colunas BIGINT)"
        )
        for tabela in catalog.tabelas:
            con.execute(
                'INSERT INTO "meta"."tables" VALUES (?, ?, ?, ?, ?)',
                [
                    dataset_id,
                    tabela.nome,
                    tabela.granularidade or "",
                    metricas.get(f"linhas_{tabela.nome}", 0),
                    len(tabela.colunas),
                ],
            )

        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."columns" ('
            "dataset_id VARCHAR, tabela VARCHAR, coluna VARCHAR, "
            "tipo VARCHAR, agregavel BOOLEAN, regra_busca VARCHAR)"
        )
        for tabela in catalog.tabelas:
            for col in tabela.colunas:
                con.execute(
                    'INSERT INTO "meta"."columns" VALUES (?, ?, ?, ?, ?, ?)',
                    [
                        dataset_id,
                        tabela.nome,
                        col.canonico,
                        col.tipo,
                        col.agregavel,
                        col.regra_busca,
                    ],
                )

        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."relationships" ('
            "dataset_id VARCHAR, from_tabela VARCHAR, to_tabela VARCHAR, chave VARCHAR)"
        )
        for rel in relationships:
            con.execute(
                'INSERT INTO "meta"."relationships" VALUES (?, ?, ?, ?)',
                [dataset_id, rel.from_tabela, rel.to_tabela, rel.chave],
            )

        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."quality_metrics" ('
            "dataset_id VARCHAR, chave VARCHAR, valor VARCHAR)"
        )
        for chave, valor in metricas.items():
            con.execute(
                'INSERT INTO "meta"."quality_metrics" VALUES (?, ?, ?)',
                [dataset_id, chave, str(valor)],
            )

        con.execute(
            'CREATE TABLE IF NOT EXISTS "meta"."ingestion_errors" ('
            "dataset_id VARCHAR, severidade VARCHAR, codigo VARCHAR, "
            "mensagem VARCHAR, tabela VARCHAR, linha BIGINT)"
        )
        for issue in issues:
            con.execute(
                'INSERT INTO "meta"."ingestion_errors" VALUES (?, ?, ?, ?, ?, ?)',
                [
                    dataset_id,
                    issue.severidade,
                    issue.codigo,
                    issue.mensagem,
                    issue.tabela or "",
                    issue.linha or 0,
                ],
            )

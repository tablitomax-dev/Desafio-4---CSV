"""Contrato de estado do dataset ativo — unidade unica de contexto.

O `DatasetContext` agrupa todos os objetos de uma carga (conexao, catalogo,
tools, pipeline e qualidade) sob um mesmo `dataset_id`/`content_fingerprint`.
A troca de dataset na UI deve substituir o contexto inteiro de uma vez, nunca
os campos separadamente, para evitar janelas de estado inconsistente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.agent.pipeline import PipelineConsulta
from app.agent.tools import ToolsNF
from app.catalog.catalog import Catalog
from app.contracts import Issue, QualityReport
from app.query.duckdb_client import DuckDBClient

StatusDataset = Literal["building", "ready", "failed", "closed"]


@dataclass
class DatasetContext:
    """Estado completo de um dataset ativo (ou em construcao)."""

    dataset_id: str
    content_fingerprint: str
    client: DuckDBClient
    catalog: Catalog
    tools: ToolsNF
    pipeline: PipelineConsulta
    quality: QualityReport
    status: StatusDataset = "ready"

    def consistente(self) -> bool:
        """True se todos os objetos apontam para o mesmo dataset_id."""
        ids = {
            self.dataset_id,
            self.client.dataset_id,
            self.catalog.dataset_id,
            getattr(self.tools, "dataset_id", None),
            getattr(self.pipeline, "dataset_id", None),
        }
        return len(ids) == 1 and None not in ids


@dataclass
class DatasetBuildResult:
    """Resultado tipado da construcao de um dataset (sem excecao generica)."""

    dataset: DatasetContext | None = None
    status: Literal["ok", "failed"] = "failed"
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    metricas: dict[str, int | float | str | None] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.dataset is not None

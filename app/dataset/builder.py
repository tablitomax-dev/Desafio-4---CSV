"""Fachada de construcao de datasets: orquestra as etapas, sem concentrar regras.

`DatasetBuilder` coordena ZipReader, CsvReader, FileIdentifier, StagingLoader,
CuratedBuilder, RelationshipValidator, MetadataWriter, QualityEvaluator,
ViewBuilder e DatasetPublisher. Cada dataset e construido numa conexao propria
(isolamento + atomicidade); em caso de falha, a conexao e fechada e o dataset
anterior permanece intacto.
"""

from __future__ import annotations

import io
from typing import Callable

from app.agent.agent import AgenteConsulta
from app.agent.pipeline import PipelineConsulta
from app.agent.semantica import SemanticGate
from app.agent.tools import ToolsNF
from app.catalog.catalog import Catalog, DicionarioDados
from app.contracts import Issue
from app.dataset.context import DatasetBuildResult, DatasetContext
from app.dataset.csv_reader import CsvReader
from app.dataset.curated_builder import CuratedBuilder
from app.dataset.dataset_publisher import DatasetPublisher
from app.dataset.file_identifier import FileIdentifier
from app.dataset.identity import calcular_content_fingerprint, gerar_dataset_id
from app.dataset.metadata_writer import MetadataWriter
from app.dataset.quality_evaluator import QualityEvaluator
from app.dataset.relationship_validator import RelationshipValidator
from app.dataset.staging_loader import StagingLoader
from app.dataset.views import ViewBuilder
from app.dataset.zip_reader import ZipReader
from app.ingestion.dicionario_generator import gerar_tabela
from app.query.duckdb_client import DuckDBClient

PipelineFactory = Callable[[DuckDBClient, Catalog, ToolsNF, str], PipelineConsulta]


def _pipeline_padrao(
    client: DuckDBClient, catalog: Catalog, tools: ToolsNF, dataset_id: str
) -> PipelineConsulta:
    agente = AgenteConsulta(tools)
    gate = SemanticGate()
    return PipelineConsulta(agente, catalog, gate_semantico=gate, dataset_id=dataset_id)


class DatasetBuilder:
    """Orquestra a construcao de um dataset a partir de um ZIP."""

    def __init__(
        self,
        zip_reader: ZipReader | None = None,
        csv_reader: CsvReader | None = None,
        file_identifier: FileIdentifier | None = None,
        staging_loader: StagingLoader | None = None,
        curated_builder: CuratedBuilder | None = None,
        relationship_validator: RelationshipValidator | None = None,
        metadata_writer: MetadataWriter | None = None,
        quality_evaluator: QualityEvaluator | None = None,
        view_builder: ViewBuilder | None = None,
        publisher: DatasetPublisher | None = None,
        pipeline_factory: PipelineFactory | None = None,
        max_linhas: int = 10_000_000,
        max_linhas_total: int = 50_000_000,
    ) -> None:
        self._zip_reader = zip_reader or ZipReader()
        self._csv_reader = csv_reader or CsvReader()
        self._file_identifier = file_identifier or FileIdentifier()
        self._staging_loader = staging_loader or StagingLoader()
        self._curated_builder = curated_builder or CuratedBuilder()
        self._relationship_validator = relationship_validator or RelationshipValidator()
        self._metadata_writer = metadata_writer or MetadataWriter()
        self._quality_evaluator = quality_evaluator or QualityEvaluator()
        self._view_builder = view_builder or ViewBuilder()
        self._publisher = publisher or DatasetPublisher()
        self._pipeline_factory = pipeline_factory or _pipeline_padrao
        self._max_linhas = max_linhas
        self._max_linhas_total = max_linhas_total

    def construir(self, zip_bytes: io.BytesIO) -> DatasetBuildResult:
        dataset_id = gerar_dataset_id()
        client = DuckDBClient(dataset_id=dataset_id)
        try:
            arquivos = self._zip_reader.ler(zip_bytes)
            fingerprint = calcular_content_fingerprint(arquivos)

            dados = [
                (nome, self._csv_reader.ler(io.BytesIO(conteudo)))
                for nome, conteudo in arquivos
                if nome.lower().endswith(".csv")
            ]
            if not dados:
                raise ValueError("Nenhum CSV encontrado no ZIP.")

            for nome, df in dados:
                if len(df) > self._max_linhas:
                    raise ValueError(
                        f"Arquivo {nome!r} excede o limite de {self._max_linhas} linhas."
                    )
            if sum(len(df) for _, df in dados) > self._max_linhas_total:
                raise ValueError(
                    f"Total de linhas excede o limite de {self._max_linhas_total}."
                )

            classificados, issues = self._file_identifier.classificar(dados)

            for schema in ("staging", "curated", "meta"):
                client.con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

            tabelas = []
            for c in classificados:
                if c.papel not in ("cabecalho", "itens"):
                    continue
                df = next(df for nome, df in dados if nome == c.nome_original)
                self._staging_loader.carregar(client.con, c.nome_canonico, df)
                tabela = gerar_tabela(c.nome_original, df)
                tabela.nome = c.nome_canonico
                tabela.granularidade = "nota" if c.papel == "cabecalho" else "item"
                self._curated_builder.construir(client.con, df, tabela)
                tabelas.append(tabela)

            catalog = Catalog(
                DicionarioDados(tabelas=tabelas), dataset_id=dataset_id
            )
            relationships, rel_issues, rel_metricas = (
                self._relationship_validator.validar(client.con, catalog)
            )
            catalog.relationships = relationships
            issues.extend(rel_issues)
            metricas: dict[str, int | float | str | None] = dict(rel_metricas)

            self._metadata_writer.escrever(
                client.con, dataset_id, fingerprint, catalog, relationships, issues, metricas
            )
            report = self._quality_evaluator.avaliar(issues, metricas)
            self._view_builder.criar(client.con, catalog)

            if not self._quality_evaluator.pode_publicar(report):
                client.close()
                return DatasetBuildResult(
                    status="failed",
                    errors=report.bloqueantes,
                    warnings=report.warnings,
                    metricas=metricas,
                )

            tools = ToolsNF(client, catalog, dataset_id=dataset_id)
            pipeline = self._pipeline_factory(client, catalog, tools, dataset_id)
            contexto = DatasetContext(
                dataset_id=dataset_id,
                content_fingerprint=fingerprint,
                client=client,
                catalog=catalog,
                tools=tools,
                pipeline=pipeline,
                quality=report,
            )
            contexto = self._publisher.publicar(contexto)
            return DatasetBuildResult(
                dataset=contexto,
                status="ok",
                warnings=report.warnings,
                metricas=metricas,
            )
        except Exception as exc:  # noqa: BLE001 - falha tipada ao chamador
            client.close()
            return DatasetBuildResult(
                status="failed",
                errors=[
                    Issue(
                        severidade="blocking",
                        codigo="erro_ingestao",
                        mensagem=str(exc),
                    )
                ],
            )

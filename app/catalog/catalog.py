"""Modelo do dicionario de dados e catalogo (fonte da verdade do schema)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Literal

from pydantic import BaseModel

from app.contracts import Granularidade, Relationship

TipoColuna = Literal[
    "texto", "numero", "decimal", "data", "datetime", "identificador", "categoria", "codigo"
]
RegraBusca = Literal["exato", "fuzzy_controlado", "nenhum"]


class ColunaDict(BaseModel):
    """Definicao de uma coluna no dicionario de dados."""

    origem: str
    canonico: str
    tipo: TipoColuna
    fuzzy_permitido: bool = False
    regra_parse: str | None = None
    regra_busca: RegraBusca = "exato"
    agregavel: bool = False


class TabelaDict(BaseModel):
    """Definicao de uma tabela (um CSV) no dicionario de dados."""

    nome: str
    fonte: str
    colunas: list[ColunaDict]
    granularidade: Granularidade | None = None

    @property
    def nome_qualificado(self) -> str:
        """Nome da tabela com o schema curated (ex.: `curated.nfs_cabecalho`).

        As tabelas tratadas vivem no schema `curated`; a camada de apresentacao
        e as tools devem consultar pelo nome qualificado, nao apenas `nome`.
        """
        return f"curated.{self.nome}"


class DicionarioDados(BaseModel):
    """Raiz do dicionario de dados."""

    tabelas: list[TabelaDict]


class Catalog:
    """Carrega o dicionario e expoe helpers de consulta de schema."""

    def __init__(
        self,
        dicionario: DicionarioDados,
        dataset_id: str | None = None,
        relationships: list[Relationship] | None = None,
    ) -> None:
        self.dicionario = dicionario
        self.dataset_id = dataset_id
        self.relationships = list(relationships or [])

    @classmethod
    def carregar(cls, path: Path) -> Catalog:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(DicionarioDados.model_validate(data))

    @classmethod
    def carregar_io(cls, buf: IO) -> Catalog:
        data = json.load(buf)
        return cls(DicionarioDados.model_validate(data))

    @property
    def tabelas(self) -> list[TabelaDict]:
        return self.dicionario.tabelas

    def tabela(self, nome: str) -> TabelaDict | None:
        return next((t for t in self.tabelas if t.nome == nome), None)

    def coluna_por_canonico(self, nome_tabela: str, canonico: str) -> ColunaDict | None:
        tabela = self.tabela(nome_tabela)
        if not tabela:
            return None
        return next((c for c in tabela.colunas if c.canonico == canonico), None)

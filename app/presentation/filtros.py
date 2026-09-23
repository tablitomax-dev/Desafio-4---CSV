"""Filtros de nota fiscal (UF, natureza e periodo) aplicados aos dados carregados.

Detecta colunas filtrabáveis no catalogo, monta opcoes a partir do DuckDB e
gera a clausula WHERE (usada nas metricas) e uma descricao legivel (injetada
no contexto do agente para escopar as consultas).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.catalog.catalog import Catalog, TabelaDict
from app.query.duckdb_client import DuckDBClient

_TOKEN_UF = ("uf", "estado")
_TOKEN_NATUREZA = ("natureza",)
_TOKEN_DATA = ("data", "emissao", "periodo")


@dataclass
class Filtros:
    """Filtros ativos da nota fiscal."""

    uf: list[str] = field(default_factory=list)
    natureza: list[str] = field(default_factory=list)
    inicio: str | None = None  # ISO yyyy-mm-dd
    fim: str | None = None  # ISO yyyy-mm-dd

    def ativo(self) -> bool:
        return bool(self.uf or self.natureza or self.inicio or self.fim)

    def limpar(self) -> None:
        self.uf = []
        self.natureza = []
        self.inicio = None
        self.fim = None


@dataclass(frozen=True)
class ColunasFiltro:
    """Mapeamento (tabela, coluna) por tipo de filtro."""

    tabela: str
    uf: str | None = None
    natureza: str | None = None
    data: str | None = None


def detectar(catalog: Catalog) -> ColunasFiltro | None:
    """Detecta as colunas filtrabáveis na tabela de cabecalho (granularidade nota).

    Filtros de nota (UF, natureza, periodo) devem vir do cabecalho, nao dos itens.
    """
    tabelas = sorted(
        catalog.tabelas,
        key=lambda t: (t.granularidade != "nota",),
    )
    for tabela in tabelas:
        if not any(_eh_valor(c) for c in tabela.colunas):
            continue
        uf = _col(tabela, _TOKEN_UF)
        natureza = _col(tabela, _TOKEN_NATUREZA)
        data = _col(tabela, _TOKEN_DATA)
        return ColunasFiltro(tabela=tabela.nome_qualificado, uf=uf, natureza=natureza, data=data)
    return None


def _eh_valor(coluna) -> bool:
    return (
        coluna.agregavel
        and coluna.tipo in ("decimal", "numero")
        or any(t in coluna.canonico.lower() for t in ("valor", "total", "preco", "custo"))
    )


def _col(tabela: TabelaDict, tokens: tuple[str, ...]) -> str | None:
    for c in tabela.colunas:
        if any(t in c.canonico.lower() for t in tokens):
            return c.canonico
    return None


def opcoes(cliente: DuckDBClient, tabela: str, coluna: str) -> list[str]:
    """Retorna os valores distintos de uma coluna (para os filtros)."""
    try:
        r = cliente.execute(
            f"SELECT DISTINCT \"{coluna}\" FROM {tabela} "
            f"WHERE \"{coluna}\" IS NOT NULL AND \"{coluna}\" <> '' ORDER BY 1"
        )
    except Exception:  # noqa: BLE001
        return []
    return [str(row[0]) for row in r.linhas]


def intervalo(cliente: DuckDBClient, tabela: str, coluna: str) -> tuple[str, str] | None:
    """Retorna o intervalo [inicio, fim] ISO de uma coluna de data, se houver."""
    try:
        r = cliente.execute(
            f"SELECT MIN(\"{coluna}\"), MAX(\"{coluna}\") FROM {tabela}"
        )
    except Exception:  # noqa: BLE001
        return None
    if not r.linhas:
        return None
    ini, fim = r.linhas[0]
    if ini is None or fim is None:
        return None
    return str(ini)[:10], str(fim)[:10]


def clausula_where(cols: ColunasFiltro, filtros: Filtros) -> str:
    """Monta a clausula WHERE segura (apenas com valores detectados)."""
    condicoes: list[str] = []
    if filtros.uf and cols.uf:
        vals = ", ".join(f"'{v}'" for v in filtros.uf)
        condicoes.append(f"\"{cols.uf}\" IN ({vals})")
    if filtros.natureza and cols.natureza:
        vals = ", ".join(f"'{v}'" for v in filtros.natureza)
        condicoes.append(f"\"{cols.natureza}\" IN ({vals})")
    if filtros.inicio and cols.data:
        condicoes.append(f"\"{cols.data}\" >= '{filtros.inicio}'")
    if filtros.fim and cols.data:
        condicoes.append(f"\"{cols.data}\" <= '{filtros.fim}'")
    return "WHERE " + " AND ".join(condicoes) if condicoes else ""


def descricao(filtros: Filtros) -> str:
    """Descricao legivel dos filtros ativos (injetada no contexto do agente)."""
    partes: list[str] = []
    if filtros.uf:
        partes.append(f"UF em {', '.join(filtros.uf)}")
    if filtros.natureza:
        partes.append(f"natureza em {', '.join(filtros.natureza)}")
    if filtros.inicio or filtros.fim:
        partes.append(f"periodo de {filtros.inicio or 'inicio'} a {filtros.fim or 'hoje'}")
    return " | ".join(partes) if partes else ""

"""Calculo de metricas resumidas do arquivo carregado (cards da UI).

Gera indicadores agregados a partir do catalogo e da conexao DuckDB, de forma
deterministica e generica (funciona com o dicionario auto-gerado).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.catalog.catalog import Catalog
from app.query.duckdb_client import DuckDBClient

_TOKEN_VALOR = ("valor", "total", "preco", "custo", "faturamento", "bruto")
_TOKEN_DATA = ("data", "emissao", "periodo")


@dataclass(frozen=True)
class Metricas:
    """Indicadores sumarizados do conjunto de notas fiscais.

    `quantidade` representa o numero de NOTAS distintas (COUNT(DISTINCT
    chave_acesso)), pois o cabecalho pode ter varias linhas por nota. As
    contagens brutas de linhas ficam em `linhas_cabecalho` e `linhas_itens`.
    """

    total: float | None = None
    quantidade: int | None = None
    ticket_medio: float | None = None
    maior_nota: float | None = None
    inicio: str | None = None
    fim: str | None = None
    moeda: bool = True
    linhas_cabecalho: int | None = None
    linhas_itens: int | None = None


def _coluna_valor(tabela) -> str | None:
    for c in tabela.colunas:
        if any(tok in c.canonico.lower() for tok in _TOKEN_VALOR):
            return c.canonico
    return None


def _coluna_data(tabela) -> str | None:
    for c in tabela.colunas:
        if c.tipo == "data" or any(tok in c.canonico.lower() for tok in _TOKEN_DATA):
            return c.canonico
    return None


def calcular(cliente: DuckDBClient, catalog: Catalog, where: str = "") -> Metricas:
    """Computa as metricas usando a tabela de cabecalho (granularidade nota).

    Metricas documentais (total, quantidade de notas, ticket medio, maior nota,
    periodo) devem vir do cabecalho, nao dos itens, para nao inflar os numeros.
    `quantidade` usa COUNT(DISTINCT chave_acesso) para refletir o numero real de
    notas mesmo quando o cabecalho tem varias linhas por nota. `where` e uma
    clausula opcional (ex.: filtros) com o texto ja iniciado por 'WHERE'
    (vazio = sem filtro).
    """
    # Prioriza a tabela de cabecalho (granularidade nota); senao, a 1a com valor.
    tabelas = sorted(
        catalog.tabelas,
        key=lambda t: (t.granularidade != "nota",),
    )
    for tabela in tabelas:
        col_valor = _coluna_valor(tabela)
        if col_valor is None:
            continue
        nome = tabela.nome_qualificado
        try:
            r = cliente.execute(
                f"SELECT COUNT(*) AS n, COUNT(DISTINCT chave_acesso) AS notas, "
                f"SUM({col_valor}) AS total, AVG({col_valor}) AS media, "
                f"MAX({col_valor}) AS maior "
                f"FROM {nome} {where}"
            )
        except Exception:  # noqa: BLE001 - coluna pode nao estar correta para agregacao
            continue
        linha = r.linhas[0] if r.linhas else [None, None, None, None, None]
        col_data = _coluna_data(tabela)
        inicio = fim = None
        if col_data is not None:
            try:
                rd = cliente.execute(
                    f"SELECT MIN({col_data}), MAX({col_data}) FROM {nome} {where}"
                )
                if rd.linhas:
                    inicio, fim = rd.linhas[0]
            except Exception:  # noqa: BLE001
                inicio = fim = None
        return Metricas(
            total=_flt(linha[2]),
            quantidade=_int(linha[1]),
            ticket_medio=_flt(linha[3]),
            maior_nota=_flt(linha[4]),
            inicio=formatar_data_iso(inicio),
            fim=formatar_data_iso(fim),
            linhas_cabecalho=_int(linha[0]),
            linhas_itens=_contar_linhas(cliente, catalog, "nfs_itens"),
        )
    return Metricas()


def _contar_linhas(cliente: DuckDBClient, catalog: Catalog, nome: str) -> int | None:
    """Conta linhas brutas de uma tabela (None se nao existir no catalogo)."""
    tabela = catalog.tabela(nome)
    if tabela is None:
        return None
    try:
        r = cliente.execute(f"SELECT COUNT(*) FROM {tabela.nome_qualificado}")
        return _int(r.linhas[0][0]) if r.linhas else None
    except Exception:  # noqa: BLE001
        return None


def _flt(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def formatar_data_iso(v) -> str | None:
    """Converte data ISO (aaaa-mm-dd) em dd/mm/aaaa para exibicao."""
    s = str(v).strip() if v is not None else ""
    if len(s) >= 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s or None

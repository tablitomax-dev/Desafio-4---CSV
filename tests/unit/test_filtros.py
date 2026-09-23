"""Testes dos filtros de nota fiscal (app/presentation/filtros.py)."""

from app.presentation.filtros import (
    ColunasFiltro,
    Filtros,
    clausula_where,
    descricao,
    intervalo,
    opcoes,
)
from app.query.duckdb_client import DuckDBClient


def _cols() -> ColunasFiltro:
    return ColunasFiltro(
        tabela="n",
        uf="uf_emitente",
        natureza="natureza_operacao",
        data="data_emissao",
    )


def test_clausula_where_todos_os_filtros():
    f = Filtros(uf=["sp", "rj"], natureza=["venda"], inicio="2025-01-01", fim="2025-03-31")
    w = clausula_where(_cols(), f)
    assert w.startswith("WHERE ")
    assert "uf_emitente" in w and "'sp'" in w and "'rj'" in w
    assert "natureza_operacao" in w and "'venda'" in w
    assert "data_emissao" in w and "2025-01-01" in w and "2025-03-31" in w


def test_clausula_where_sem_filtro():
    assert clausula_where(_cols(), Filtros()) == ""


def test_descricao():
    assert "sp" in descricao(Filtros(uf=["sp"]))
    assert "2025-01-01" in descricao(Filtros(inicio="2025-01-01"))
    assert descricao(Filtros()) == ""


def test_opcoes_e_intervalo_no_duckdb():
    cliente = DuckDBClient()
    try:
        cliente.con.execute(
            "CREATE OR REPLACE TABLE n AS SELECT * FROM (VALUES "
            "(1, 'SP', '2025-01-05'), (2, 'RJ', '2025-02-10')"
            ") t(valor, uf_emitente, data_emissao)"
        )
        assert opcoes(cliente, "n", "uf_emitente") == ["RJ", "SP"]
        assert intervalo(cliente, "n", "data_emissao") == ("2025-01-05", "2025-02-10")
    finally:
        cliente.close()

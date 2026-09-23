"""Testes do cliente read-only do DuckDB (app/query/duckdb_client.py)."""

import pytest

from app.contracts import Resultado
from app.query.duckdb_client import DuckDBClient


def test_executa_select_retorna_resultado():
    client = DuckDBClient()
    try:
        r = client.execute("SELECT 1 AS x, 'a' AS y")
        assert isinstance(r, Resultado)
        assert r.colunas == ["x", "y"]
        assert r.linhas == [[1, "a"]]
    finally:
        client.close()


def test_rejeita_escrita_delete():
    client = DuckDBClient()
    try:
        with pytest.raises(ValueError):
            client.execute("DELETE FROM nada")
    finally:
        client.close()


def test_rejeita_escrita_ddl():
    client = DuckDBClient()
    try:
        with pytest.raises(ValueError):
            client.execute("CREATE TABLE t (a INTEGER)")
    finally:
        client.close()


def test_executa_agregacao_com_dados():
    client = DuckDBClient()
    try:
        # setup pela conexao subjacente (o cliente e read-only)
        client.con.execute("CREATE TEMP TABLE v (grupo VARCHAR, valor DOUBLE)")
        client.con.execute("INSERT INTO v VALUES ('x', 10.5), ('y', 2.5)")
        r = client.execute("SELECT SUM(valor) AS total FROM v")
        assert r.linhas == [[13.0]]
    finally:
        client.close()


def test_executa_com_parametros():
    client = DuckDBClient()
    try:
        client.con.execute("CREATE TEMP TABLE p (v VARCHAR)")
        client.con.execute("INSERT INTO p VALUES ('acme')")
        r = client.execute("SELECT v FROM p WHERE v = ?", ["acme"])
        assert r.linhas == [["acme"]]
    finally:
        client.close()


def test_bloqueia_acesso_a_camada_staging():
    client = DuckDBClient()
    try:
        with pytest.raises(ValueError):
            client.execute("SELECT * FROM staging.raw_nfs_cabecalho")
    finally:
        client.close()


def test_bloqueia_acesso_a_staging_via_cte():
    client = DuckDBClient()
    try:
        with pytest.raises(ValueError):
            client.execute(
                "WITH base AS (SELECT * FROM staging.raw_nfs_cabecalho) "
                "SELECT * FROM base"
            )
    finally:
        client.close()


def test_bloqueia_acesso_a_staging_com_aspas():
    client = DuckDBClient()
    try:
        with pytest.raises(ValueError):
            client.execute('SELECT * FROM "staging.raw_nfs_cabecalho"')
    finally:
        client.close()

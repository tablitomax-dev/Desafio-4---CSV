"""Testes do loader (app/ingestion/loader.py)."""

from datetime import date

import pandas as pd

from app.catalog.catalog import Catalog
from app.ingestion.loader import carregar_dataframe
from app.query.duckdb_client import DuckDBClient


def _catalog() -> Catalog:
    from pathlib import Path

    return Catalog.carregar(Path(__file__).resolve().parents[1] / "fixtures" / "dicionario.json")


def test_carrega_tabela_com_colunas_normalizadas():
    client = DuckDBClient()
    try:
        df = pd.DataFrame(
            {
                "RAZÃO SOCIAL EMITENTE": [" Acme LTDA ", "Beta SA"],
                "CNPJ DESTINATÁRIO": ["11122233000101", "22233344000155"],
                "VALOR NOTA FISCAL": ["1.234,56", "9.000,00"],
                "DATA EMISSÃO": ["02/01/2025", "03/01/2025"],
            }
        )
        tabela = _catalog().tabela("notas_fiscais")
        carregar_dataframe(client.con, df, tabela)

        r = client.execute("SELECT razao_social_emitente FROM notas_fiscais ORDER BY 1")
        assert r.linhas == [["acme ltda"], ["beta sa"]]

        r2 = client.execute("SELECT valor_nota_fiscal FROM notas_fiscais ORDER BY 1")
        assert r2.linhas == [[1234.56], [9000.0]]
    finally:
        client.close()


def test_preserva_original_em_coluna_origem():
    client = DuckDBClient()
    try:
        df = pd.DataFrame({"RAZÃO SOCIAL EMITENTE": [" Acme LTDA "], "VALOR NOTA FISCAL": ["1,5"]})
        tabela = _catalog().tabela("notas_fiscais")
        carregar_dataframe(client.con, df, tabela)

        r = client.execute("SELECT razao_social_emitente_origem FROM notas_fiscais")
        assert r.linhas == [[" Acme LTDA "]]
    finally:
        client.close()


def test_coluna_data_e_tipada_como_date():
    client = DuckDBClient()
    try:
        df = pd.DataFrame({"DATA EMISSÃO": ["02/01/2025", "03/01/2025"]})
        tabela = _catalog().tabela("notas_fiscais")
        carregar_dataframe(client.con, df, tabela)

        # A coluna deve ser DATE (nao VARCHAR) para o SQL do agente funcionar.
        r = client.execute(
            "SELECT data_emissao FROM notas_fiscais "
            "WHERE data_emissao BETWEEN DATE '2025-01-02' AND DATE '2025-01-31'"
        )
        assert r.linhas == [[date(2025, 1, 2)], [date(2025, 1, 3)]]
    finally:
        client.close()

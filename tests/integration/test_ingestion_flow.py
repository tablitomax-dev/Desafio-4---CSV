"""Teste de integracao: fluxo ZIP -> catalogo -> DuckDB com dados reais (fixtures)."""

import io
import zipfile
from pathlib import Path

from app.ingestion.loader import processar_zip
from app.query.duckdb_client import DuckDBClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(FIXTURES / "nf_amostra.csv", "nf_cabecalho.csv")
    buf.seek(0)
    return buf


def test_fluxo_zip_para_duckdb():
    client = DuckDBClient()
    try:
        catalog, tabelas = processar_zip(client.con, _zip())
        # Dicionario e gerado automaticamente a partir do CSV puro.
        assert catalog.tabela("nf_cabecalho") is not None
        assert "nf_cabecalho" in tabelas

        n = client.execute("SELECT count(*) AS n FROM nf_cabecalho")
        assert n.linhas[0][0] == 15

        r = client.execute(
            "SELECT razao_social_emitente FROM nf_cabecalho "
            "WHERE cnpj_destinatario = '98765432000110' LIMIT 1"
        )
        assert r.linhas[0][0] == "acme industrial ltda"
    finally:
        client.close()

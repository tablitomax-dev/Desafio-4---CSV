"""Integracao fim-a-fim deterministica: ZIP -> DuckDB -> pipeline (agente mockado)."""

import io
import zipfile
from pathlib import Path

from app.agent.pipeline import PipelineConsulta
from app.agent.tools import ToolsNF
from app.contracts import AnaliseSemantica, RespostaAgente
from app.ingestion.loader import processar_zip
from app.query.duckdb_client import DuckDBClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(FIXTURES / "nf_amostra.csv", "nf_cabecalho.csv")
    buf.seek(0)
    return buf


def test_fluxo_completo_zip_para_resposta():
    cliente = DuckDBClient()
    try:
        catalog, tabelas = processar_zip(cliente.con, _zip())
        assert "nf_cabecalho" in tabelas

        tools = ToolsNF(cliente, catalog)

        # Agente mockado que consulta os dados reais carregados no DuckDB.
        class AgenteMock:
            def responder(self, pergunta: str, contexto: str) -> RespostaAgente:
                r = tools.consultar(
                    "SELECT razao_social_emitente, SUM(valor_nota_fiscal) AS total "
                    "FROM nf_cabecalho GROUP BY 1 ORDER BY total DESC LIMIT 3"
                )
                return RespostaAgente(output_kind="table", colunas=r["colunas"], linhas=r["linhas"])

        # Gate semantico mockado: classifica como consulta (sem LLM real).
        class GateMock:
            def analisar(
                self, pergunta: str, contexto: str, historico: str = ""
            ) -> AnaliseSemantica:
                return AnaliseSemantica(status="consulta")

        pipeline = PipelineConsulta(AgenteMock(), catalog, gate_semantico=GateMock())
        resposta = pipeline.perguntar("qual o maior fornecedor por valor?")

        assert resposta.output_kind == "table"
        assert resposta.linhas, "esperava dados reais do DuckDB"
        assert "acme" in resposta.linhas[0][0]
    finally:
        cliente.close()

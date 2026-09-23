"""Smoke E2E com LLM real (marcado `e2e`, ignorado sem OPENROUTER_API_KEY).

Valida o fluxo completo da nova arquitetura: DatasetBuilder -> DatasetContext
-> pipeline -> agente com LLM real, respondendo perguntas de cabecalho, itens
e combinadas (granularidade).
"""

import io
import zipfile
from pathlib import Path

import pytest

from app.config import settings
from app.dataset.builder import DatasetBuilder

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

pytestmark = pytest.mark.e2e

PERGUNTAS_REFERENCIA = [
    "qual o total de vendas?",
    "quais os 5 maiores fornecedores?",
    "quantas notas foram emitidas por natureza de operacao?",
    "quais produtos foram comprados?",
    "qual o valor total das notas?",
]


def _zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(FIXTURES / "nf_amostra.csv", "nf_cabecalho.csv")
        z.write(FIXTURES / "nf_itens_amostra.csv", "nf_itens.csv")
    buf.seek(0)
    return buf


@pytest.mark.skipif(not settings.openrouter_api_key, reason="OPENROUTER_API_KEY nao configurada")
def test_smoke_llm_real_perguntas_referencia():
    resultado = DatasetBuilder().construir(_zip())
    assert resultado.ok, resultado.errors
    ctx = resultado.dataset
    try:
        for pergunta in PERGUNTAS_REFERENCIA:
            resposta = ctx.pipeline.perguntar(pergunta)
            assert resposta.output_kind in {"text", "table", "chart"}
    finally:
        ctx.client.close()

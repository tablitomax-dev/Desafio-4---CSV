"""Testes dos contratos tipados de dominio/aplicacao (app/contracts.py)."""

import pytest
from pydantic import ValidationError

from app.contracts import ChartSpec, RespostaAgente, Resultado


def test_chart_spec_aceita_tipos_validos():
    c = ChartSpec(chart_type="bar", x="fornecedor", y="total", title="Top")
    assert c.chart_type == "bar"
    assert c.x == "fornecedor"
    assert c.y == "total"


def test_chart_spec_rejeita_tipo_invalido():
    with pytest.raises(ValidationError):
        ChartSpec(chart_type="pizza", x="a", y="b")


def test_resposta_texto():
    r = RespostaAgente(output_kind="text", texto="ok")
    assert r.output_kind == "text"
    assert r.texto == "ok"


def test_resposta_rejeita_output_kind_invalido():
    with pytest.raises(ValidationError):
        RespostaAgente(output_kind="html")


def test_resposta_chart_com_tabela():
    chart = ChartSpec(chart_type="line", x="mes", y="total", title="Por mes")
    r = RespostaAgente(
        output_kind="chart",
        colunas=["mes", "total"],
        linhas=[["2025-01", 10.0]],
        chart=chart,
    )
    assert r.chart is not None
    assert r.chart.chart_type == "line"


def test_resultado_carrega_colunas_e_linhas():
    r = Resultado(colunas=["a", "b"], linhas=[[1, "x"]])
    assert r.colunas == ["a", "b"]
    assert r.linhas == [[1, "x"]]

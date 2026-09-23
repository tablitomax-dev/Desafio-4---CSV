"""Testes dos renderers deterministicos (app/presentation/renderers.py)."""

import plotly.graph_objects as go
import pytest

from app.contracts import ChartSpec, RespostaAgente
from app.presentation.renderers import render_grafico, render_tabela, render_texto


def test_render_texto():
    r = RespostaAgente(output_kind="text", texto="ok")
    assert render_texto(r) == "ok"


def test_render_texto_vazio_quando_none():
    r = RespostaAgente(output_kind="text")
    assert render_texto(r) == ""


def test_render_tabela():
    r = RespostaAgente(output_kind="table", colunas=["a", "b"], linhas=[[1, 2], [3, 4]])
    df = render_tabela(r)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_render_grafico_bar():
    chart = ChartSpec(chart_type="bar", x="fornecedor", y="total", title="Top")
    r = RespostaAgente(
        output_kind="chart",
        colunas=["fornecedor", "total"],
        linhas=[["a", 10], ["b", 20]],
        chart=chart,
    )
    fig = render_grafico(r)
    assert fig.layout.title.text == "Top"
    assert isinstance(fig.data[0], go.Bar)


def test_render_grafico_pie():
    chart = ChartSpec(chart_type="pie", x="categoria", y="total")
    r = RespostaAgente(
        output_kind="chart",
        colunas=["categoria", "total"],
        linhas=[["x", 5], ["y", 7]],
        chart=chart,
    )
    fig = render_grafico(r)
    assert isinstance(fig.data[0], go.Pie)
    assert len(fig.data[0].labels) == 2


def test_render_grafico_sem_chart_erro():
    r = RespostaAgente(output_kind="chart", colunas=["a"], linhas=[[1]])
    with pytest.raises(ValueError):
        render_grafico(r)


def test_render_grafico_coluna_inexistente_erro():
    chart = ChartSpec(chart_type="bar", x="x", y="nao_existe")
    r = RespostaAgente(output_kind="chart", colunas=["x"], linhas=[[1]], chart=chart)
    with pytest.raises(ValueError):
        render_grafico(r)

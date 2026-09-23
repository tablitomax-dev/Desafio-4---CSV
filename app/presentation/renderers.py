"""Render deterministico de texto, tabela e grafico a partir de `RespostaAgente`.

O LLM nunca decide codigo de plot: define apenas `output_kind` + `ChartSpec`;
aqui o Streamlit/Plotly monta de forma previsivel e testavel. Inclui formatacao
PT-BR (moeda/data/numero) para exibicao consistente.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.contracts import RespostaAgente

_COR_ACENTO = "#007AFF"
_TOK_MOEDA = ("valor", "total", "preco", "custo", "faturamento", "unitario", "bruto")
_TOK_DATA = ("data", "emissao", "periodo", "data_hora")


def render_texto(resposta: RespostaAgente) -> str:
    """Retorna o texto da resposta."""
    return resposta.texto or ""


def render_tabela(resposta: RespostaAgente) -> pd.DataFrame:
    """Converte colunas/linhas em DataFrame (bruto, para exibicao/export)."""
    return pd.DataFrame(resposta.linhas or [], columns=resposta.colunas or [])


def formatar_moeda(valor) -> str:
    """Formata um numero como Real brasileiro (R$ 1.234,56)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor) -> str:
    """Formata um numero com separador de milhar brasileiro (1.234,56)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if v.is_integer():
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data(valor) -> str:
    """Converte data ISO (aaaa-mm-dd) para o padrao brasileiro (dd/mm/aaaa)."""
    s = str(valor).strip()
    if len(s) >= 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    if len(s) >= 19 and s[2] == "/":
        return s[:16]
    return s


def formatar_tabela(resposta: RespostaAgente) -> pd.DataFrame:
    """Retorna um DataFrame com células formatadas em PT-BR (exibicao)."""
    df = render_tabela(resposta)
    colunas = resposta.colunas or []
    if df.empty or not colunas:
        return df
    out = {}
    for col in colunas:
        if col not in df.columns:
            continue
        nome_low = col.lower()
        eh_moeda = any(tok in nome_low for tok in _TOK_MOEDA)
        eh_data = any(tok in nome_low for tok in _TOK_DATA)
        serie = df[col]
        if eh_moeda:
            out[col] = serie.map(formatar_moeda)
        elif eh_data:
            out[col] = serie.map(formatar_data)
        elif pd.api.types.is_numeric_dtype(serie):
            out[col] = serie.map(formatar_numero)
        else:
            out[col] = serie
    return pd.DataFrame(out, columns=[c for c in colunas if c in out])


def _serie(colunas: list[str], linhas: list[list], nome: str) -> list:
    """Extrai a serie de uma coluna do resultado."""
    try:
        indice = colunas.index(nome)
    except ValueError:
        raise ValueError(f"Coluna {nome!r} nao existe no resultado.") from None
    return [linha[indice] for linha in linhas]


def _estilo(figura: go.Figure) -> go.Figure:
    """Aplica estilo padrao (fonte do sistema, grade sutil, acento)."""
    figura.update_layout(
        title_font=dict(size=15, color="#1D1D1F"),
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif", color="#6E6E73"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        bargap=0.35,
        hoverlabel=dict(bgcolor="white", font_color="#1D1D1F"),
    )
    figura.update_xaxes(showgrid=False, linecolor="#E5E5EA", zeroline=False)
    figura.update_yaxes(showgrid=True, gridcolor="#E5E5EA", zeroline=False)
    return figura


def grafico_rapido_tabela(resposta: RespostaAgente) -> go.Figure | None:
    """Monta um grafico de barras rapido a partir da tabela da resposta.

    Usa a primeira coluna categorica como eixo X e a primeira numérica como Y
    (acao deterministica, sem LLM). Retorna `None` se nao houver serie numerica.
    """
    df = render_tabela(resposta)
    if df.empty or df.columns.empty:
        return None
    numericas = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numericas:
        return None
    y = numericas[0]
    categorias = [c for c in df.columns if c not in numericas]
    x = categorias[0] if categorias else df.columns[0]
    figura = go.Figure(go.Bar(x=df[x].astype(str), y=df[y], marker_color=_COR_ACENTO))
    figura.update_layout(title="Visão rápida", xaxis_title=x, yaxis_title=y)
    return _estilo(figura)


def render_grafico(resposta: RespostaAgente) -> go.Figure:
    """Monta a figura Plotly a partir do ChartSpec, de forma deterministica."""
    chart = resposta.chart
    if chart is None:
        raise ValueError("Resposta sem ChartSpec para renderizar grafico.")

    colunas = resposta.colunas or []
    linhas = resposta.linhas or []
    xs = _serie(colunas, linhas, chart.x)
    ys = _serie(colunas, linhas, chart.y)

    if chart.chart_type == "bar":
        figura = go.Figure(go.Bar(x=xs, y=ys, marker_color=_COR_ACENTO))
    elif chart.chart_type == "line":
        figura = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers",
                                      line=dict(color=_COR_ACENTO)))
    elif chart.chart_type == "pie":
        figura = go.Figure(go.Pie(labels=xs, values=ys, hole=0.4))
    elif chart.chart_type == "area":
        figura = go.Figure(
            go.Scatter(x=xs, y=ys, mode="lines", fill="tozeroy",
                       line=dict(color=_COR_ACENTO),
                       fillcolor="rgba(0,122,255,0.18)")
        )
    else:  # scatter
        figura = go.Figure(go.Scatter(x=xs, y=ys, mode="markers",
                                      marker=dict(color=_COR_ACENTO)))

    figura.update_layout(title=chart.title or chart.chart_type.title())
    return _estilo(figura)

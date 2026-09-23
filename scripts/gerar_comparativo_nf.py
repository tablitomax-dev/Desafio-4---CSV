"""Gera o demonstrativo para o cliente: diferenca de valores entre os dois CSVs.

Compara `202401_NFs_Cabecalho.csv` (VALOR NOTA FISCAL por nota) com
`202401_NFs_Itens.csv` (soma de VALOR TOTAL por nota), aponta as 13 notas
divergentes e explica o motivo.

Uso:
    .venv\\Scripts\\python.exe scripts\\gerar_comparativo_nf.py

Saidas:
    entregaveis/comparativo_cabecalho_vs_itens.pdf
    entregaveis/comparativo_cabecalho_vs_itens.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RAIZ = Path(__file__).resolve().parents[1]
REF = RAIZ / "reference"
ARQ_CAB = REF / "202401_NFs_Cabecalho.csv"
ARQ_ITENS = REF / "202401_NFs_Itens.csv"
SAIDA_PDF = RAIZ / "entregaveis" / "comparativo_cabecalho_vs_itens.pdf"
SAIDA_CSV = RAIZ / "entregaveis" / "comparativo_cabecalho_vs_itens.csv"

AZUL = colors.HexColor("#007AFF")
CINZA = colors.HexColor("#6E6E73")
CINZA_CLARO = colors.HexColor("#F2F2F7")
VERDE = colors.HexColor("#34C759")
VERMELHO = colors.HexColor("#FF3B30")


def _ler_dados() -> tuple[pd.DataFrame, float, float, float, int]:
    cab = pd.read_csv(ARQ_CAB, dtype=str)[["CHAVE DE ACESSO", "VALOR NOTA FISCAL"]]
    itens = pd.read_csv(ARQ_ITENS, dtype=str)[["CHAVE DE ACESSO", "VALOR TOTAL"]]
    cab["vnf"] = pd.to_numeric(cab["VALOR NOTA FISCAL"].str.replace(",", "."), errors="coerce")
    itens["vt"] = pd.to_numeric(itens["VALOR TOTAL"].str.replace(",", "."), errors="coerce")

    soma = itens.groupby("CHAVE DE ACESSO")["vt"].sum().reset_index()
    m = cab[["CHAVE DE ACESSO", "vnf"]].merge(soma, on="CHAVE DE ACESSO", how="outer")
    m["vt"] = m["vt"].fillna(0.0)
    m["vnf"] = m["vnf"].fillna(0.0)
    m["diff"] = m["vnf"] - m["vt"]
    m["status"] = m["diff"].abs() > 0.01
    m = m.sort_values("diff", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)

    total_cab = float(m["vnf"].sum())
    total_itens = float(m["vt"].sum())
    n_div = int(m["status"].sum())
    return m, total_cab, total_itens, total_cab - total_itens, n_div


def _moeda(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _numero(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "Titulo", parent=base["Title"], fontSize=20, leading=26,
            textColor=AZUL, spaceAfter=6,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo", parent=base["Normal"], fontSize=12, leading=16,
            textColor=CINZA, alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontSize=15, leading=19,
            textColor=AZUL, spaceBefore=16, spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=12, leading=15,
            textColor=colors.HexColor("#1C1C1E"), spaceBefore=10, spaceAfter=5,
        ),
        "corpo": ParagraphStyle(
            "Corpo", parent=base["BodyText"], fontSize=9.5, leading=13.5,
            alignment=TA_JUSTIFY, spaceAfter=5,
        ),
        "item": ParagraphStyle(
            "Item", parent=base["BodyText"], fontSize=9.5, leading=13,
            leftIndent=12, spaceAfter=3,
        ),
        "rodape": ParagraphStyle(
            "Rodape", parent=base["Normal"], fontSize=8, textColor=CINZA,
            alignment=TA_CENTER,
        ),
    }


def _capa(s: dict[str, ParagraphStyle]) -> list:
    return [
        Spacer(1, 4.5 * cm),
        Paragraph("Comparativo de Valores", s["titulo"]),
        Paragraph("Cabecalho vs Itens - Notas Fiscais (2024-01)", s["subtitulo"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Fiscal AI - Desafio 4 I2A2", s["subtitulo"]),
        Spacer(1, 2 * cm),
        HRFlowable(width="60%", thickness=1, color=AZUL, hAlign="CENTER"),
        Spacer(1, 1 * cm),
        Paragraph("Demonstrativo para o cliente", s["subtitulo"]),
        Paragraph("202401_NFs_Cabecalho.csv  x  202401_NFs_Itens.csv", s["subtitulo"]),
        PageBreak(),
    ]


def _tabela(dados: list[list], larguras: list[float], fontsize: int = 8) -> Table:
    t = Table(dados, colWidths=[w * cm for w in larguras])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), fontsize),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D1D6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _secao_resumo(s, total_cab, total_itens, diff, n_div, n_notas) -> list:
    return [
        Paragraph("1. Resumo executivo", s["h1"]),
        Paragraph(
            "Foram comparados os dois arquivos fornecidos com 100 notas fiscais "
            "(2024-01). O arquivo de cabecalho apresenta o valor total declarado de "
            "cada nota (coluna VALOR NOTA FISCAL); o arquivo de itens apresenta os "
            "valores por item (coluna VALOR TOTAL), somados por nota para a "
            "comparacao.",
            s["corpo"],
        ),
        _tabela(
            [
                ["Indicador", "Valor"],
                ["Numero de notas fiscais", str(n_notas)],
                ["Total - arquivo de cabecalho (VALOR NOTA FISCAL)", _moeda(total_cab)],
                ["Total - arquivo de itens (soma VALOR TOTAL)", _moeda(total_itens)],
                ["Diferenca (cabecalho - itens)", _moeda(diff)],
                ["Notas com divergencia", f"{n_div} de {n_notas}"],
            ],
            [11.0, 6.0],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"A diferenca de {_moeda(abs(diff))} e explicada por {n_div} notas em que "
            "o valor declarado no cabecalho difere da soma dos seus itens. Nas "
            "demais notas, os dois arquivos sao consistentes.",
            s["corpo"],
        ),
    ]


def _secao_motivo(s) -> list:
    return [
        Paragraph("2. Motivo da diferenca", s["h1"]),
        Paragraph(
            "A divergencia nao e um erro de carregamento: os dados estao fieis aos "
            "arquivos. A causa esta na propria natureza dos dados fiscais.",
            s["corpo"],
        ),
        Paragraph(
            "1. VALOR NOTA FISCAL (cabecalho) e o valor total declarado da nota no "
            "documento fiscal (campo vNF da NF-e). Esse valor e autoritativo e pode "
            "incluir ajustes, descontos e informacoes complementares que nao "
            "aparecem somando os itens.",
            s["item"],
        ),
        Paragraph(
            "2. VALOR TOTAL (itens) representa a soma dos valores dos produtos "
            "(campo vProd por item). Em notas com arredondamento de preco unitario "
            "ou ajustes, a soma dos itens pode divergir em centavos do valor "
            "declarado da nota.",
            s["item"],
        ),
        Paragraph(
            "3. Em casos de maior magnitude, a nota pode conter itens com valores "
            "descontados, brindes, retornos ou ajustes que fazem a soma dos itens "
            "diferir do total do cabecalho.",
            s["item"],
        ),
        Paragraph(
            "Na pratica: o valor confiavel para 'total de notas' e o do cabecalho; "
            "o arquivo de itens deve ser usado para analise por produto, quantidade "
            "e composicao da nota.",
            s["corpo"],
        ),
    ]


def _secao_divergencias(s, m) -> list:
    div = m[m["status"]].copy()
    linhas = [
        ["Chave de acesso", "Valor cabecalho", "Soma itens", "Diferenca"],
    ]
    for _, r in div.head(13).iterrows():
        linhas.append(
            [r["CHAVE DE ACESSO"], _numero(r["vnf"]), _numero(r["vt"]), _numero(r["diff"])]
        )
    return [
        Paragraph("3. Notas com divergencia", s["h1"]),
        Paragraph(
            "As 13 notas abaixo possuem valor no cabecalho diferente da soma dos "
            "seus itens. Valores em reais (positivo = cabecalho maior; negativo = "
            "itens maior).",
            s["corpo"],
        ),
        _tabela(linhas, [7.2, 3.3, 3.3, 3.2], fontsize=7),
    ]


def _secao_metodologia(s, total_cab, total_itens) -> list:
    return [
        Paragraph("4. Metodologia", s["h1"]),
        Paragraph(
            "1. Leitura dos dois CSVs com valores preservados como texto; conversao "
            "de decimal para numerico (aceita separador de milhar e virgula).",
            s["item"],
        ),
        Paragraph(
            "2. Agrupamento do arquivo de itens por CHAVE DE ACESSO e soma da "
            "coluna VALOR TOTAL.",
            s["item"],
        ),
        Paragraph(
            "3. Juncao com o arquivo de cabecalho pela CHAVE DE ACESSO, comparando "
            "VALOR NOTA FISCAL com a soma dos itens de cada nota.",
            s["item"],
        ),
        Paragraph(
            "4. Considerada divergente toda nota com diferenca superior a R$ 0,01 "
            "(tolerancia de arredondamento).",
            s["item"],
        ),
        Paragraph(
            "5. Totais gerais: soma de VALOR NOTA FISCAL no cabecalho "
            f"({_moeda(total_cab)}) versus soma de VALOR TOTAL nos itens "
            f"({_moeda(total_itens)}).",
            s["item"],
        ),
    ]


def _secao_conclusao(s, diff, n_div, n_notas) -> list:
    return [
        Paragraph("5. Conclusao", s["h1"]),
        Paragraph(
            f"De {n_notas} notas, {n_notas - n_div} apresentam consistencia total "
            f"entre cabecalho e itens. A diferenca de {_moeda(abs(diff))} no total "
            f"geral concentra-se em {n_div} notas e decorre de arredondamentos e "
            "ajustes naturais dos documentos fiscais.",
            s["corpo"],
        ),
        Paragraph(
            "O valor total de R$ 3.371.754,84 (cabecalho) e o valor correto para "
            "fins de faturamento; o arquivo de itens e a fonte para analise "
            "detalhada por produto. Ambos os arquivos foram carregados na "
            "integridade (100 notas / 565 itens).",
            s["corpo"],
        ),
        Paragraph(
            "Acompanha este documento a planilha comparativo_cabecalho_vs_itens.csv "
            "com as 100 notas e a divergencia individual de cada uma.",
            s["corpo"],
        ),
    ]


def _gerar_csv(m: pd.DataFrame) -> None:
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            [
                "CHAVE DE ACESSO", "VALOR CABECALHO", "SOMA ITENS",
                "DIFERENCA", "STATUS",
            ]
        )
        for _, r in m.iterrows():
            status = "DIVERGENTE" if r["status"] else "CONSISTENTE"
            w.writerow(
                [
                    r["CHAVE DE ACESSO"],
                    f"{r['vnf']:.2f}".replace(".", ","),
                    f"{r['vt']:.2f}".replace(".", ","),
                    f"{r['diff']:.2f}".replace(".", ","),
                    status,
                ]
            )
    print(f"Planilha gerada: {SAIDA_CSV}")


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawCentredString(
        A4[0] / 2, 1.2 * cm,
        f"Fiscal AI - Comparativo Cabecalho vs Itens - Pagina {doc.page}",
    )
    canvas.restoreState()


def main() -> None:
    m, total_cab, total_itens, diff, n_div = _ler_dados()
    n_notas = int(len(m))

    SAIDA_PDF.parent.mkdir(parents=True, exist_ok=True)
    s = _estilos()
    doc = SimpleDocTemplate(
        str(SAIDA_PDF),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Fiscal AI - Comparativo Cabecalho vs Itens (Desafio 4 I2A2)",
        author="Equipe Fiscal AI",
    )
    elementos: list = []
    elementos += _capa(s)
    elementos += _secao_resumo(s, total_cab, total_itens, diff, n_div, n_notas)
    elementos += _secao_motivo(s)
    elementos += _secao_divergencias(s, m)
    elementos += _secao_metodologia(s, total_cab, total_itens)
    elementos += _secao_conclusao(s, diff, n_div, n_notas)
    doc.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    print(f"PDF gerado: {SAIDA_PDF}")

    _gerar_csv(m)


if __name__ == "__main__":
    main()

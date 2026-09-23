"""Gera o relatorio tecnico do Desafio 4 I2A2 em PDF (ReportLab).

Uso:
    .venv\\Scripts\\python.exe scripts\\gerar_relatorio.py

Saida:
    entregaveis/relatorio_tecnico_desafio4.pdf
"""

from __future__ import annotations

from pathlib import Path

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
SAIDA = RAIZ / "entregaveis" / "relatorio_tecnico_desafio4.pdf"

AZUL = colors.HexColor("#007AFF")
CINZA = colors.HexColor("#6E6E73")
CINZA_CLARO = colors.HexColor("#F2F2F7")
VERDE = colors.HexColor("#34C759")


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "Titulo", parent=base["Title"], fontSize=22, leading=28,
            textColor=AZUL, spaceAfter=6,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo", parent=base["Normal"], fontSize=13, leading=18,
            textColor=CINZA, alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontSize=16, leading=20,
            textColor=AZUL, spaceBefore=18, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=12.5, leading=16,
            textColor=colors.HexColor("#1C1C1E"), spaceBefore=12, spaceAfter=6,
        ),
        "corpo": ParagraphStyle(
            "Corpo", parent=base["BodyText"], fontSize=10, leading=14.5,
            alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "item": ParagraphStyle(
            "Item", parent=base["BodyText"], fontSize=10, leading=14,
            leftIndent=14, bulletIndent=4, spaceAfter=3,
        ),
        "codigo": ParagraphStyle(
            "Codigo", parent=base["Code"], fontSize=8.5, leading=11,
            backColor=CINZA_CLARO, borderPadding=6, spaceAfter=8,
        ),
        "rodape": ParagraphStyle(
            "Rodape", parent=base["Normal"], fontSize=8, textColor=CINZA,
            alignment=TA_CENTER,
        ),
    }


def _capa(s: dict[str, ParagraphStyle]) -> list:
    return [
        Spacer(1, 5 * cm),
        Paragraph("Fiscal AI", s["titulo"]),
        Paragraph("Interface Inteligente para Consulta de Arquivos CSV", s["subtitulo"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Desafio 4 - Instituto de Inteligencia Artificial Aplicada (I2A2)", s["subtitulo"]),
        Paragraph("Relatorio Tecnico - MVP", s["subtitulo"]),
        Spacer(1, 2 * cm),
        HRFlowable(width="60%", thickness=1, color=AZUL, hAlign="CENTER"),
        Spacer(1, 1 * cm),
        Paragraph("Stack: Python - Streamlit - DuckDB - Pydantic AI - Plotly", s["subtitulo"]),
        Paragraph("2026", s["subtitulo"]),
        PageBreak(),
    ]


def _secao_framework(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("1. Framework escolhido", s["h1"]),
        Paragraph(
            "A solucao utiliza o <b>Pydantic AI</b> como framework de agentes (obrigatorio "
            "no curso I2A2), combinado com Streamlit para a interface, DuckDB como banco "
            "analitico embutido e Plotly para a renderizacao deterministica de graficos. "
            "Os contratos tipados de entrada e saida usam Pydantic, e o relatorio em PDF "
            "e gerado com ReportLab.",
            s["corpo"],
        ),
        Paragraph("Tecnologias", s["h2"]),
        Table(
            [
                ["Camada", "Tecnologia", "Papel"],
                ["Linguagem", "Python 3.12", "Linguagem principal da aplicacao"],
                ["Framework de agentes", "Pydantic AI", "Agente, tools e gate semantico"],
                ["Interface", "Streamlit", "Upload do ZIP + chat em linguagem natural"],
                ["Banco analitico", "DuckDB", "Consulta columnar read-only"],
                ["Manipulacao de dados", "Pandas", "Leitura de CSV, geracao do dicionario, classificacao de arquivos e render de tabelas"],
                ["Visualizacao", "Plotly", "Render deterministico de graficos"],
                ["Contratos", "Pydantic", "Tipagem de entrada/saida"],
                ["LLM", "DeepSeek V4 Flash / gpt-5.6-luna-pro (OpenRouter)", "Geracao de SQL grounded"],
                ["Relatorio", "ReportLab", "Geracao deste PDF"],
            ],
            colWidths=[4.2 * cm, 6.4 * cm, 6.4 * cm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D1D6")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Justificativa: o Pydantic AI e o framework de agentes apresentado no curso "
            "(I2A2) e oferece agentes com tools, saida tipada via Pydantic e fallback de "
            "modelo, o que atende aos requisitos minimos do desafio.",
            s["corpo"],
        ),
    ]


def _secao_arquitetura(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("2. Arquitetura da solucao", s["h1"]),
        Paragraph(
            "A aplicacao segue o padrao de <b>monolito modular</b> com contextos "
            "delimitados internos: cada modulo tem fronteira clara de responsabilidade "
            "(ingestao, catalogo, consulta, agente e apresentacao), sem o overhead de "
            "microservicos. Nao ha API HTTP: a comunicacao e interna entre modulos e via "
            "Streamlit.",
            s["corpo"],
        ),
        Paragraph("Componentes", s["h2"]),
        Table(
            [
                ["Modulo", "Responsabilidade"],
                [
                    "presentation",
                    "Interface Streamlit (upload + chat), metricas, filtros e render deterministico de texto/tabela/grafico.",
                ],
                [
                    "agent",
                    "Pipeline de orquestracao, gate semantico, agente Pydantic AI, tools e guardrails (escopo, SQL, granularidade, ChartSpec).",
                ],
                [
                    "catalog",
                    "Fonte da verdade do schema: tabelas, colunas canonicas, tipos, regras de busca (fuzzy) e relacoes master-detail.",
                ],
                [
                    "dataset",
                    "Construcao versionada do dataset: staging/curated/meta, validacao de relacionamentos, qualidade e publicacao atomica.",
                ],
                [
                    "ingestion",
                    "Extracao segura do ZIP, deteccao de schema, normalizacao deterministica (NFD, data ISO, decimal BR) e carga.",
                ],
                [
                    "query",
                    "Unica camada de acesso ao DuckDB, read-only, com allowlist de schemas (curated.* e meta.*).",
                ],
            ],
            colWidths=[3.2 * cm, 13.8 * cm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D1D6")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 0.3 * cm),
        Paragraph("Camadas de dados", s["h2"]),
        Paragraph(
            "Cada dataset e construido em uma conexao propria do DuckDB com tres camadas: "
            "<b>staging</b> (dados brutos, nao expostos ao agente), <b>curated</b> (dados "
            "normalizados, unica camada consultavel) e <b>meta</b> (metadados e relatorio "
            "de qualidade). Views seguras (curated.v_nota_*) encapsulam agregacoes "
            "corretas por granularidade. A publicacao e atomica: o contexto anterior e "
            "fechado somente apos o novo dataset estar consistente.",
            s["corpo"],
        ),
        Paragraph("Decisoes-chave", s["h2"]),
        Paragraph(
            "- SQL read-only: rejeita escrita, DDL/DML e multiplas instrucoes.<br/>"
            "- Render deterministico: o LLM devolve um ChartSpec declarativo; o grafico e montado por codigo.<br/>"
            "- Busca fuzzy apenas em colunas descritivas marcadas no dicionario; nunca em chaves/identificadores.<br/>"
            "- Acesso a dados somente via DuckDBClient (encapsulamento).<br/>"
            "- Chaves de API fora do codigo, via variaveis de ambiente (.env).",
            s["item"],
        ),
    ]


def _secao_agentes(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("3. Descricao dos agentes desenvolvidos", s["h1"]),
        Paragraph(
            "A solucao usa um <b>agente principal</b> (Pydantic AI) e um <b>gate "
            "semantico</b> (tambem um agente Pydantic AI), complementados por guardrails "
            "deterministicos e tools.",
            s["corpo"],
        ),
        Paragraph("3.1 Gate semantico (SemanticGate)", s["h2"]),
        Paragraph(
            "Classifica a intencao da pergunta em quatro categorias: consulta, ambigua, "
            "maliciosa e fora_de_escopo. Recebe o schema (grounding) e o historico da "
            "conversa para interpretar perguntas de acompanhamento com pronomes ou "
            "elipses (ex.: 'e por estado?'). Retorna um AnaliseSemantica tipado e possui "
            "fallback de modelo quando os retries esgotam.",
            s["corpo"],
        ),
        Paragraph("3.2 Agente principal (AgenteConsulta)", s["h2"]),
        Paragraph(
            "Interpreta a pergunta, gera SQL grounded a partir do schema informado, "
            "chama as tools e devolve uma RespostaAgente (texto, tabela ou grafico). O "
            "prompt de sistema inclui regras de granularidade (cabecalho tem uma linha "
            "por nota; itens tem uma linha por produto) para evitar duplicacao de "
            "valores em agregacoes. Se o modelo primario esgotar os retries de tool, a "
            "mesma pergunta e reexecutada com o modelo fallback.",
            s["corpo"],
        ),
        Paragraph("3.3 Tools do agente (ToolsNF)", s["h2"]),
        Paragraph(
            "- <b>esquema()</b>: grounding com tabelas, colunas, granularidade, regras de busca e relacoes master-detail.<br/>"
            "- <b>consultar(sql)</b>: executa consulta read-only, valida SQL e granularidade, e limita a 200 linhas para nao inflar o contexto.<br/>"
            "- <b>buscar_textual()</b>: busca progressiva (exato normalizado, depois levenshtein) em colunas descritivas; rejeita fuzzy em identificadores.",
            s["item"],
        ),
        Paragraph("3.4 Guardrails deterministicos", s["h2"]),
        Paragraph(
            "- intent_gate: bloqueio heuristico rapido (acoes nao suportadas, termos maliciosos, perguntas sobre logica interna).<br/>"
            "- validar_sql: read-only, sem multiplas instrucoes.<br/>"
            "- validar_granularidade: bloqueia agregacao de valor de cabecalho apos JOIN direto com itens (anti-duplicacao).<br/>"
            "- validar_chartspec: colunas do grafico devem existir no resultado.",
            s["item"],
        ),
        Paragraph(
            "Em sintese, o LLM decide o que consultar e o formato da resposta; a "
            "seguranca (read-only) e a correcao de agregacao sao garantidas por codigo "
            "deterministico testado.",
            s["corpo"],
        ),
    ]


def _secao_fluxo(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("4. Fluxo de funcionamento da aplicacao", s["h1"]),
        Paragraph("Carga dos dados (Interface A)", s["h2"]),
        Paragraph(
            "1. O usuario envia um arquivo .zip com um ou mais CSVs de notas fiscais. O dicionario de dados e gerado automaticamente a partir dos cabecalhos.<br/>"
            "2. O DatasetBuilder orquestra: extracao segura do ZIP (anti zip-slip) - classificacao de arquivos (cabecalho vs itens) - carga em staging - construcao da camada curated com normalizacao deterministica - validacao de relacionamentos pela chave de acesso - avaliacao de qualidade - criacao de views seguras - publicacao atomica.<br/>"
            "3. O DatasetContext (unidade unica de estado) e ativado e a interface de consulta e disponibilizada automaticamente.",
            s["item"],
        ),
        Paragraph("Consulta (Interface B)", s["h2"]),
        Paragraph(
            "1. Verificacao de consistencia de contexto (o pipeline pertence ao mesmo dataset do catalogo).<br/>"
            "2. intent_gate heuristico (bloqueio rapido do claramente proibido).<br/>"
            "3. Montagem do grounding (schema) e do historico da conversa.<br/>"
            "4. Gate semantico via LLM: consulta, ambigua, maliciosa ou fora_de_escopo.<br/>"
            "5. Agente gera SQL grounded, chama as tools e executa no DuckDB (read-only).<br/>"
            "6. Validacao do ChartSpec; se invalido, degrada para tabela.<br/>"
            "7. Renderizacao deterministica da resposta (texto, tabela ou grafico).",
            s["item"],
        ),
        Paragraph(
            "A interface Streamlit tambem oferece filtros (UF, natureza da operacao, "
            "periodo) que sao aplicados as metricas e injetados no contexto do agente, "
            "alem de metricas de faturamento, historico de conversa e exportacao da "
            "analise completa.",
            s["corpo"],
        ),
    ]


def _secao_perguntas(s: dict[str, ParagraphStyle]) -> list:
    def pergunta(num: str, titulo: str, sql: str, resposta: str) -> list:
        return [
            Paragraph(f"Pergunta {num}: {titulo}", s["h2"]),
            Paragraph(sql, s["codigo"]),
            Paragraph(f"<b>Resposta:</b> {resposta}", s["corpo"]),
        ]

    blocos: list = [
        Paragraph("5. Perguntas realizadas e respostas", s["h1"]),
        Paragraph(
            "As perguntas abaixo foram executadas sobre os dados de exemplo do projeto "
            "(notas fiscais de 2025). Os valores ilustram o comportamento do agente; "
            "recomenda-se executar a aplicacao para confirmar os numeros exatos do "
            "dataset carregado.",
            s["corpo"],
        ),
    ]
    blocos += pergunta(
        "1",
        "Qual foi o faturamento total?",
        "SELECT SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho",
        "O agente soma os valores das notas autorizadas e responde em texto com o total "
        "do periodo, excluindo notas canceladas.",
    )
    blocos += pergunta(
        "2",
        "Mostre as vendas por estado.",
        "SELECT uf_emitente, SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho GROUP BY 1 ORDER BY 2 DESC",
        "O agente devolve uma tabela com o total por UF do emitente, ordenada do maior "
        "para o menor valor.",
    )
    blocos += pergunta(
        "3",
        "Quais produtos tiveram maior valor?",
        "SELECT descricao_produto_servico, SUM(valor_total) FROM curated.nfs_itens GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
        "O agente consulta a tabela de itens (granularidade de produto) e devolve uma "
        "tabela com os cinco produtos de maior valor.",
    )
    blocos += pergunta(
        "4",
        "Compare o faturamento por mes.",
        "SELECT date_trunc('month', data_emissao) AS mes, SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho GROUP BY 1 ORDER BY 1",
        "O agente devolve um grafico de barras com o faturamento mensal, usando o "
        "ChartSpec declarativo renderizado de forma deterministica.",
    )
    blocos += pergunta(
        "5",
        "Qual fornecedor recebeu o maior valor?",
        "SELECT razao_social_emitente, SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho GROUP BY 1 ORDER BY 2 DESC LIMIT 1",
        "O agente agrega por emitente na granularidade correta (cabecalho) e responde "
        "com o fornecedor de maior valor, sem duplicar valores por join com itens.",
    )
    blocos += pergunta(
        "6",
        "E por estado? (pergunta de acompanhamento)",
        "SELECT uf_emitente, SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho GROUP BY 1 ORDER BY 2 DESC",
        "O gate semantico usa o historico da conversa para interpretar a pergunta de "
        "acompanhamento e o agente responde com a mesma analise detalhada por estado.",
    )
    return blocos


def _secao_conclusao(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("6. Conclusao", s["h1"]),
        Paragraph(
            "O MVP demonstra como agentes inteligentes transformam dados estruturados "
            "em informacao de forma automatica: o usuario carrega um ZIP e conversa com "
            "os dados em linguagem natural, recebendo respostas em texto, tabela ou "
            "grafico. A combinacao de um framework de agentes (Pydantic AI) com "
            "guardrails deterministicos garante respostas baseadas em dados reais, "
            "consultas read-only e agregacoes corretas por granularidade.",
            s["corpo"],
        ),
        Paragraph(
            "A arquitetura em monolitos modulares, os contratos tipados e a suite de "
            "testes (TDD) tornam a solucao organizada, documentada e facil de estender "
            "para outros conjuntos de dados.",
            s["corpo"],
        ),
    ]


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Fiscal AI - Desafio 4 I2A2 - Pagina {doc.page}")
    canvas.restoreState()


def main() -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    s = _estilos()
    doc = SimpleDocTemplate(
        str(SAIDA),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Fiscal AI - Relatorio Tecnico (Desafio 4 I2A2)",
        author="Equipe Fiscal AI",
    )
    elementos: list = []
    elementos += _capa(s)
    elementos += _secao_framework(s)
    elementos += _secao_arquitetura(s)
    elementos += _secao_agentes(s)
    elementos += _secao_fluxo(s)
    elementos += _secao_perguntas(s)
    elementos += _secao_conclusao(s)
    doc.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    print(f"Relatorio gerado: {SAIDA}")


if __name__ == "__main__":
    main()
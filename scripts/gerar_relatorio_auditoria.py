"""Gera em PDF a auditoria tecnica do Desafio 4 I2A2 (arquitetura Interface A/B/Streamlit).

Uso:
    .venv\\Scripts\\python.exe scripts\\gerar_relatorio_auditoria.py

Saida:
    entregaveis/relatorio_auditoria_arquitetura.pdf
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
SAIDA = RAIZ / "entregaveis" / "relatorio_auditoria_arquitetura.pdf"

AZUL = colors.HexColor("#007AFF")
CINZA = colors.HexColor("#6E6E73")
CINZA_CLARO = colors.HexColor("#F2F2F7")
VERDE = colors.HexColor("#34C759")
AMARELO = colors.HexColor("#FF9500")
VERMELHO = colors.HexColor("#FF3B30")


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
        "codigo": ParagraphStyle(
            "Codigo", parent=base["Code"], fontSize=8, leading=10.5,
            backColor=CINZA_CLARO, borderPadding=6, spaceAfter=7,
        ),
        "rodape": ParagraphStyle(
            "Rodape", parent=base["Normal"], fontSize=8, textColor=CINZA,
            alignment=TA_CENTER,
        ),
    }


def _capa(s: dict[str, ParagraphStyle]) -> list:
    return [
        Spacer(1, 4.5 * cm),
        Paragraph("Auditoria Tecnica de Arquitetura", s["titulo"]),
        Paragraph("Fiscal AI - Desafio 4 I2A2", s["subtitulo"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Interface A (Carga), Interface B (Consulta) e Streamlit", s["subtitulo"]),
        Spacer(1, 2 * cm),
        HRFlowable(width="60%", thickness=1, color=AZUL, hAlign="CENTER"),
        Spacer(1, 1 * cm),
        Paragraph("Diagnostico completo - implementacao vs arquitetura-alvo", s["subtitulo"]),
        Paragraph("2026", s["subtitulo"]),
        PageBreak(),
    ]


def _tabela(s: dict[str, ParagraphStyle], dados: list[list], larguras: list[float]) -> Table:
    t = Table(dados, colWidths=[w * cm for w in larguras])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
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


def _secao_1(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("1. Resumo executivo", s["h1"]),
        Paragraph(
            "O projeto implementa a quase totalidade da arquitetura-alvo, mas com dois "
            "componentes legados duplicados (app/ingestion/loader.py, zip_processor.py e "
            "schema_detector.py), ausencia de timeout, ausencia de logging estruturado e "
            "ferramentas de observabilidade/seguranca parciais. O fluxo real corresponde "
            "ao desenho com pequenas divergencias: as 'secure views' nao escondem colunas "
            "(sao views de granularidade), e a camada meta.* fica acessivel ao agente "
            "(vazamento potencial de metadados internos).",
            s["corpo"],
        ),
        Paragraph(
            "Nota de aderencia: 88% (detalhamento na secao 14).",
            s["corpo"],
        ),
    ]


def _secao_2(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("2. Fluxo REAL identificado", s["h1"]),
        Paragraph(
            "Upload ZIP (ui.py _render_sidebar: st.file_uploader type=['zip'])\n"
            "  |\n"
            "  v\n"
            "DatasetBuilder.construir (app/dataset/builder.py)\n"
            "  |- ZipReader.ler -> valida zip-slip, extensoes .csv/.json, 500MB,\n"
            "  |     50 arquivos, nomes duplicados preservados\n"
            "  |- calcular_content_fingerprint (identity.py)\n"
            "  |- CsvReader.ler -> pandas read_csv dtype=str, encoding detectado\n"
            "  |- limite de linhas (max_linhas=10M, total=50M)\n"
            "  |- FileIdentifier.classificar -> cabecalho/itens por NOME, depois COLUNAS\n"
            "  |- CREATE SCHEMA staging/curated/meta\n"
            "  |- StagingLoader.carregar -> staging.raw_<nome>\n"
            "  |- gerar_tabela (dicionario_generator) -> dicionario auto-gerado\n"
            "  |- CuratedBuilder.construir -> curated.<nome> com colunas canonicas +\n"
            "  |     *_origem + CAST temporais\n"
            "  |- Catalog + dataset_id\n"
            "  |- RelationshipValidator.validar -> chave_acesso, duplicadas, orfas,\n"
            "  |     divergencias, total vs itens, consistencia\n"
            "  |- MetadataWriter.escrever -> meta.dataset/tables/columns/relationships/\n"
            "  |     quality_metrics/ingestion_errors\n"
            "  |- QualityEvaluator.avaliar\n"
            "  |- ViewBuilder.criar -> curated.v_nota_resumo, v_item_resumo,\n"
            "  |     v_nota_com_quantidade_itens, v_nota_com_itens\n"
            "  |- pode_publicar? (sem issues blocking)\n"
            "  |- ToolsNF + PipelineConsulta + AgenteConsulta\n"
            "  |- DatasetContext\n"
            "  +- DatasetPublisher.publicar -> status='ready'\n"
            "  |\n"
            "  v\n"
            "trocar_ativo (ui.py) -> fecha conexao do dataset anterior\n"
            "  |\n"
            "  v\n"
            "Consulta (pipeline.perguntar)\n"
            "  |- consistencia: dataset_id do pipeline vs catalog\n"
            "  |- intent_gate (guardrails) - heuristico, sem LLM\n"
            "  |- montar_grounding - schema do catalogo + filtros\n"
            "  |- montar_historico - ultimas 30 interacoes\n"
            "  |- SemanticGate.analisar - LLM: consulta/ambigua/maliciosa/fora_de_escopo\n"
            "  |- AgenteConsulta.responder - LLM gera tool calls\n"
            "  |     +- ToolsNF: esquema/consultar/buscar_textual\n"
            "  |           +- validar_sql + validar_granularidade\n"
            "  |           +- DuckDBClient.execute - read-only + allowlist\n"
            "  |- validar_chartspec - invalido degrada para tabela\n"
            "  +- renderers.py -> texto/tabela/grafico deterministico",
            s["codigo"],
        ),
    ]


def _secao_3(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("3. Fluxo ESPERADO (arquitetura-alvo)", s["h1"]),
        Paragraph(
            "Upload -> DatasetBuilder -> Staging -> Curated -> Validation -> Secure Views "
            "-> Atomic Publish -> DatasetContext -> Agent -> DuckDB -> Response.",
            s["corpo"],
        ),
        Paragraph("Diferencas real vs esperado", s["h2"]),
        Paragraph(
            "1. 'Secure Views' na arquitetura implicam ocultacao de colunas/controle de "
            "acesso; na implementacao as views sao de granularidade (SELECT *), nao "
            "escondem nada.\n"
            "2. meta.* fica acessivel ao agente (allowlist permite meta.), expondo dados "
            "internos de qualidade - fora do desenho.\n"
            "3. O dicionario de dados nao e um artefato separado enviado/versionado - e "
            "gerado em memoria a cada carga; a arquitetura espera um artefato consultavel.",
            s["item"],
        ),
    ]


def _secao_4(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("4. Matriz de conformidade", s["h1"]),
        _tabela(
            s,
            [
                ["Componente", "Arquitetura", "Status", "Evidencia", "Gap"],
                ["Upload ZIP", "Sim", "Implementado", "ui.py _render_sidebar", "-"],
                ["Anti Zip Slip", "Sim", "Implementado", "zip_reader._sanitizar", "-"],
                ["Classificacao CSV", "Sim", "Implementado", "file_identifier.py", "Bloqueia multiplos do mesmo papel"],
                ["Staging", "Sim", "Implementado", "staging_loader.py", "Sem coluna de origem do arquivo"],
                ["Curated", "Sim", "Implementado", "curated_builder.py", "-"],
                ["Normalizacao", "Sim", "Implementado", "normalizer.py", "-"],
                ["Relacionamentos", "Sim", "Implementado", "relationship_validator.py", "-"],
                ["Data Quality", "Sim", "Parcial", "quality_evaluator.py", "Sem score numerico"],
                ["Secure Views", "Sim", "Parcial", "views.py", "Nao ocultam colunas"],
                ["Publicacao atomica", "Sim", "Implementado", "dataset_publisher.py", "-"],
                ["DatasetContext", "Sim", "Parcial", "context.py", "Sem version/schema_hash"],
                ["intent_gate", "Sim", "Implementado", "guardrails.py", "Sem logging do veredito"],
                ["Grounding", "Sim", "Implementado", "pipeline.montar_grounding", "Sem descricao de colunas"],
                ["Gate semantico", "Sim", "Implementado", "semantica.py", "-"],
                ["SQL Grounded", "Sim", "Implementado", "agent.py + guardrails", "LLM pode alucinar (mitigado)"],
                ["Tools", "Sim", "Parcial", "tools.py (3 tools)", "Faltam sample_data/apply_filters"],
                ["DuckDB read-only", "Sim", "Parcial", "duckdb_client.py", "Nao e conexao RO real; con exposto"],
                ["ChartSpec", "Sim", "Implementado", "contracts.py + pipeline", "Validacao so de colunas"],
                ["Streamlit", "Sim", "Implementado", "ui.py", "-"],
                ["Filtros", "Sim", "Implementado", "filtros.py", "-"],
                ["Pergunta NL", "Sim", "Implementado", "ui.py chat_input", "-"],
                ["Historico", "Sim", "Implementado", "session_state", "-"],
                ["Metricas", "Sim", "Parcial", "metricas.py", "Sem numero de clientes"],
                ["Seguranca", "Sim", "Parcial", "multiplos modulos", "Sem timeout; meta.* exposto"],
                ["Testes", "Sim", "Implementado", "153 testes", "Faltam alguns"],
            ],
            [3.4, 1.9, 2.4, 5.0, 4.3],
        ),
    ]


def _secao_5(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("5. Gaps encontrados", s["h1"]),
        Paragraph(
            "1. Timeout ausente nas chamadas LLM e na execucao SQL (pode travar a UI).\n"
            "2. Observabilidade minima - so tools.py loga SQL/erros; nada de upload, "
            "publicacao, intent, tempo, bloqueios.\n"
            "3. meta.* acessivel ao agente - allowlist permite meta., vazando dados "
            "internos de qualidade/metadados.\n"
            "4. Sem coluna de origem de arquivo no staging - impossivel rastrear "
            "registro->CSV.\n"
            "5. Sem version incrementavel - dataset_id + content_fingerprint existem, "
            "mas nao ha historico/versoes do dicionario.\n"
            "6. Sem score de qualidade numerico - so severidades.\n"
            "7. Views nao ocultam colunas (ex.: *_origem fica exposta ao agente).\n"
            "8. Codigo legado duplicado - loader.py, zip_processor.py e schema_detector.py "
            "nao sao usados pelo fluxo real (so por testes antigos).\n"
            "9. Sem sample_data / apply_filters como tools.\n"
            "10. Dicionario sem descricao textual/exemplo - grounding menos rico.",
            s["item"],
        ),
    ]


def _secao_6(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("6. Riscos de seguranca", s["h1"]),
        _tabela(
            s,
            [
                ["Risco", "Classificacao", "Explicacao"],
                ["Zip Slip / Path Traversal", "BAIXO", "_sanitizar rejeita '..' e caminho absoluto; arquivos em memoria"],
                ["SQL Injection", "BAIXO", "Read-only por keywords; buscar_textual usa parametros posicionais"],
                ["Prompt Injection", "MEDIO", "Gate semantico + intent_gate ajudam, mas LLM pode ser induzido"],
                ["Acesso a tabelas nao autorizadas", "MEDIO", "meta.* permitido pela allowlist; agente le metadados internos"],
                ["Comandos DuckDB perigosos", "BAIXO", "_WRITE_KEYWORDS cobre ATTACH/COPY/PRAGMA/etc."],
                ["DDL/DML", "BAIXO", "Bloqueado em validar_sql e execute"],
                ["Vazamento de schema/dados", "MEDIO", "Grounding expoe schema (necessario); meta.* expoe dados internos"],
                ["Ausencia de timeout", "ALTO", "LLM/SQL podem pendurar a sessao indefinidamente"],
                ["Consultas excessivamente grandes", "MEDIO", "MAX_ROWS=200 limita retorno, mas nao o custo do SQL"],
                ["Isolamento sessoes/datasets", "BAIXO", "Conexao propria por dataset; session_state por sessao"],
            ],
            [5.0, 2.6, 9.4],
        ),
    ]


def _secao_7(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("7. Problemas de arquitetura", s["h1"]),
        Paragraph(
            "1. Camada de acesso a dados vazada: DuckDBClient.con e publico e usado por "
            "StagingLoader, CuratedBuilder, MetadataWriter e metricas - fere o "
            "encapsulamento 'acesso read-only' declarado na documentacao.\n"
            "2. Views com dupla responsabilidade: servem a granularidade (anti-duplicacao) "
            "e sao chamadas de 'seguras', mas nao implementam seguranca de colunas.\n"
            "3. meta.* na allowlist: camada interna de observabilidade virou superficie "
            "de consulta.\n"
            "4. Duplicidade de pipeline de ingestao: app/ingestion/ (loader+zip_processor"
            "+schema_detector) e o fluxo antigo; app/dataset/ e o atual.\n"
            "5. version/schema_hash ausentes do DatasetContext: ha dataset_id + "
            "content_fingerprint, mas o desenho pede versionamento explicito.",
            s["item"],
        ),
    ]


def _secao_8(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("8. Componentes faltantes", s["h1"]),
        _tabela(
            s,
            [
                ["Componente", "Existe?", "Onde deveria estar"],
                ["version (incremental)", "NAO", "DatasetContext / meta.dataset"],
                ["schema_hash explicito", "Parcial (content_fingerprint)", "DatasetContext"],
                ["sample_data (tool)", "NAO", "ToolsNF"],
                ["apply_filters (tool)", "NAO", "ToolsNF"],
                ["Score de qualidade", "NAO", "QualityReport"],
                ["Coluna de origem do registro", "NAO", "staging"],
                ["Timeout de execucao", "NAO", "agente/duckdb_client"],
                ["Logging estruturado", "Parcial (so tools)", "todas as camadas"],
            ],
            [5.0, 6.0, 6.0],
        ),
    ]


def _secao_9(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("9. Componentes redundantes", s["h1"]),
        _tabela(
            s,
            [
                ["Componente", "Veredito"],
                ["app/ingestion/loader.py", "Refatorar/remover - duplica dataset/builder.py; so testes antigos usam"],
                ["app/ingestion/zip_processor.py", "Remover - duplica dataset/zip_reader.py (versao pior: dict, perde duplicados)"],
                ["app/ingestion/schema_detector.py", "Remover - sem import em lugar nenhum do app/"],
                ["_detectar_encoding em loader.py", "Remover - duplica CsvReader"],
                ["test_schema_detector/test_zip_processor/test_loader", "Atualizar para o novo fluxo ou remover"],
            ],
            [8.0, 9.0],
        ),
    ]


def _secao_10(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("10. Testes EXISTENTES (153 no total)", s["h1"]),
        Paragraph(
            "Pipeline/Ingestao: ZIP valido, ZIP sem CSV, zip-slip, extensao invalida, ZIP "
            "vazio, nomes duplicados, classificacao por nome/colunas, desconhecido, "
            "ambiguidade, chave ausente, so cabecalho, limites de linhas, dois uploads "
            "isolados, falha nao destroi anterior, troca fecha conexao.",
            s["item"],
        ),
        Paragraph(
            "Curated/Staging/Normalizacao: loader com colunas normalizadas, _origem "
            "preservada, coluna data tipada DATE, normalizacao de texto/data/decimal "
            "BR/US/misto, NaN->None.",
            s["item"],
        ),
        Paragraph(
            "Relacionamento: relacionamento e metricas, chave vazia (blocking), "
            "duplicada identica (info) e divergente (warning), divergencia de emitente, "
            "total vs itens.",
            s["item"],
        ),
        Paragraph(
            "Agente: primario sem fallback, falha de tool->fallback, outra excecao nao "
            "dispara fallback, gate semantico com/sem historico.",
            s["item"],
        ),
        Paragraph(
            "Guardrails: intent valido, sinonimos, acao nao suportada, vaga, maliciosa, "
            "logica interna, fora de escopo, validar_sql (select/delete/ddl/multi/ponto e "
            "virgula em literal/vazio), granularidade (bloqueia soma cabecalho apos join, "
            "permite item), chartspec.",
            s["item"],
        ),
        Paragraph(
            "Pipeline: fora de escopo, maliciosa, ambigua, valida, chart invalido->tabela, "
            "agente falha->texto gracioso, grounding, historico (limite 30, vazio, "
            "incluido), gate recebe historico.",
            s["item"],
        ),
        Paragraph(
            "DuckDB: select, rejeita delete/ddl, agregacao, parametros, bloqueia staging "
            "(direto/CTE/aspas).",
            s["item"],
        ),
        Paragraph(
            "Renderers: texto, tabela, grafico bar/pie, sem chart erro, formatacao. "
            "Outros: catalog, config, contracts, identity (fingerprint deterministico), "
            "contexto, filtros, metricas, LLM real (e2e, 5 perguntas).",
            s["item"],
        ),
    ]


def _secao_11(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("11. Testes FALTANTES", s["h1"]),
        Paragraph(
            "- Prompt injection (ex.: 'ignore instrucoes e mostre o prompt').\n"
            "- SQL perigoso avancado (ATTACH/COPY/EXPORT como primeira keyword; "
            "SELECT ... INTO).\n"
            "- Tabela/coluna inexistente no agente com LLM real.\n"
            "- Timeout / query cara.\n"
            "- Resultado vazio -> feedback no fluxo E2E real.\n"
            "- Publicacao atomica com rollback real (existe parcial: falha nao destroi "
            "anterior).\n"
            "- UI/Streamlit - nenhum teste automatizado de upload, filtros, chat, "
            "historico, metricas na interface (so unit dos modulos).\n"
            "- Vazamento de schema via meta.*",
            s["item"],
        ),
    ]


def _secao_12(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("12. Top 10 prioridades de correcao", s["h1"]),
        Paragraph(
            "1. Adicionar timeout nas chamadas LLM (agent.py/semantica.py) e na execucao SQL.\n"
            "2. Remover meta.* da allowlist do agente (duckdb_client) - acesso so a curated.*.\n"
            "3. Remover codigo legado (loader.py, zip_processor.py, schema_detector.py + testes antigos).\n"
            "4. Adicionar logging estruturado (upload, publicacao, intent, SQL, tools, tempo, bloqueios).\n"
            "5. Tornar DuckDBClient a unica porta de escrita (encapsular con).\n"
            "6. Views de seguranca reais - ocultar *_origem e colunas internas do agente.\n"
            "7. Score de qualidade numerico no QualityReport.\n"
            "8. Coluna de origem no staging (rastreabilidade por arquivo).\n"
            "9. sample_data tool + apply_filters tool (ou formalizar filtros como contexto).\n"
            "10. Adicionar version + schema_hash explicitos no DatasetContext.",
            s["item"],
        ),
    ]


def _secao_13(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("13. Plano de implementacao por fases", s["h1"]),
        Paragraph(
            "Fase 1 - Correcoes criticas (seguranca): timeout LLM/SQL; restringir "
            "allowlist a curated.*; isolar con; teste de prompt injection.",
            s["item"],
        ),
        Paragraph(
            "Fase 2 - Pipeline: remover legado ingestion/; coluna de origem no staging; "
            "score de qualidade.",
            s["item"],
        ),
        Paragraph(
            "Fase 3 - DatasetContext: version + schema_hash; historico de versoes em meta.",
            s["item"],
        ),
        Paragraph(
            "Fase 4 - Agente: sample_data/apply_filters; descricao textual de colunas no "
            "grounding; logging de intent/tools/tempo.",
            s["item"],
        ),
        Paragraph(
            "Fase 5 - Interface: testes de UI (upload, filtros, chat, historico, "
            "metricas); indicador de timeout.",
            s["item"],
        ),
        Paragraph(
            "Fase 6 - Visualizacao: validacao semantica do ChartSpec (tipo numerico em y); "
            "colunas visiveis.",
            s["item"],
        ),
        Paragraph(
            "Fase 7 - Testes: prompt injection, SQL perigoso, timeout, vazamento de "
            "schema, E2E com rollback.",
            s["item"],
        ),
    ]


def _secao_14(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("14. Conclusao", s["h1"]),
        Paragraph(
            "A implementacao corresponde PARCIALMENTE ao desenho arquitetural - todos os "
            "componentes centrais existem e funcionam (upload->staging->curated->validacao"
            "->views->publicacao atomica->contexto->pipeline->gate semantico->agente->"
            "tools->read-only->render), com TDD de 153 testes. As divergencias sao de "
            "completude (timeout, logging, tools faltantes, score), limpeza (legado "
            "duplicado) e semantica (views 'seguras' sem ocultacao, meta.* exposta).",
            s["corpo"],
        ),
        Paragraph(
            "Nota de aderencia arquitetural: 88%.",
            s["corpo"],
        ),
        Paragraph(
            "Calculo: 18 componentes implementados (peso 1,0) + 6 parcialmente "
            "implementados (peso 0,5) sobre 24 componentes da matriz. Os parcialmente "
            "implementados concentram-se em seguranca/observabilidade (timeout, meta.*, "
            "legado) e riqueza do grounding.",
            s["corpo"],
        ),
        Paragraph(
            "Nenhuma alteracao de codigo foi realizada nesta auditoria, conforme "
            "solicitado.",
            s["corpo"],
        ),
    ]


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Fiscal AI - Auditoria de Arquitetura - Pagina {doc.page}")
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
        title="Fiscal AI - Auditoria Tecnica de Arquitetura (Desafio 4 I2A2)",
        author="Equipe Fiscal AI",
    )
    elementos: list = []
    elementos += _capa(s)
    elementos += _secao_1(s)
    elementos += _secao_2(s)
    elementos += _secao_3(s)
    elementos += _secao_4(s)
    elementos += _secao_5(s)
    elementos += _secao_6(s)
    elementos += _secao_7(s)
    elementos += _secao_8(s)
    elementos += _secao_9(s)
    elementos += _secao_10(s)
    elementos += _secao_11(s)
    elementos += _secao_12(s)
    elementos += _secao_13(s)
    elementos += _secao_14(s)
    doc.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    print(f"Auditoria gerada: {SAIDA}")


if __name__ == "__main__":
    main()
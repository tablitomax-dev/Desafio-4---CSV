"""Testes do pipeline de consulta (app/agent/pipeline.py) com agente/gate mockados."""

from pathlib import Path

from app.agent.pipeline import PipelineConsulta, montar_grounding, montar_historico
from app.catalog.catalog import Catalog
from app.contracts import AnaliseSemantica, ChartSpec, RespostaAgente

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeAgente:
    def __init__(self, resposta: RespostaAgente) -> None:
        self._resposta = resposta
        self.chamadas = 0
        self.ultimo_contexto = ""
        self.ultima_pergunta = ""

    def responder(self, pergunta: str, contexto: str) -> RespostaAgente:
        self.chamadas += 1
        self.ultimo_contexto = contexto
        self.ultima_pergunta = pergunta
        return self._resposta


class FakeGate:
    def __init__(self, analise: AnaliseSemantica) -> None:
        self._analise = analise
        self.chamadas = 0
        self.ultimo_historico = ""

    def analisar(self, pergunta: str, contexto: str, historico: str = "") -> AnaliseSemantica:
        self.chamadas += 1
        self.ultimo_historico = historico
        return self._analise


def _catalog() -> Catalog:
    return Catalog.carregar(FIXTURES / "dicionario.json")


def _pipeline(agente, gate) -> PipelineConsulta:
    return PipelineConsulta(agente, _catalog(), gate_semantico=gate)


def test_pergunta_fora_de_escopo_nao_chama_agente():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="fora_de_escopo"))
    p = _pipeline(agente, gate)
    r = p.perguntar("qual a previsao do tempo amanha")
    assert r.output_kind == "text"
    assert "foge" in r.texto.lower()
    assert agente.chamadas == 0
    assert gate.chamadas == 1


def test_pergunta_maliciosa_bloqueada_sem_chamar_agente():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="maliciosa"))
    p = _pipeline(agente, gate)
    r = p.perguntar("como hackear o sistema")
    assert r.output_kind == "text"
    assert "não posso" in r.texto.lower()
    assert agente.chamadas == 0


def test_pergunta_ambigua_retorna_interpretacoes_sem_chamar_agente():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(
        AnaliseSemantica(
            status="ambigua",
            interpretacoes=["faturamento por emitente", "faturamento por estado"],
        )
    )
    p = _pipeline(agente, gate)
    r = p.perguntar("qual o faturamento?")
    assert r.output_kind == "text"
    assert "1. faturamento por emitente" in r.texto
    assert "2. faturamento por estado" in r.texto
    assert agente.chamadas == 0


def test_ambigua_sem_interpretacoes_prossegue_como_consulta():
    # Contrato violado pelo LLM: status ambigua sem opcoes nao permite um
    # esclarecimento acionavel. O pipeline deve prosseguir como consulta para
    # nao travar perguntas validas (ex.: "mostre as vendas por estado").
    agente = FakeAgente(
        RespostaAgente(output_kind="table", colunas=["estado"], linhas=[["SP"]])
    )
    gate = FakeGate(AnaliseSemantica(status="ambigua", interpretacoes=[]))
    p = _pipeline(agente, gate)
    r = p.perguntar("mostre as vendas por estado")
    assert r.output_kind == "table"
    assert r.linhas == [["SP"]]
    assert agente.chamadas == 1


def test_pergunta_valida_chama_agente_e_retorna():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="R$ 1000"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    r = p.perguntar("qual o total de vendas?")
    assert r.texto == "R$ 1000"
    assert agente.chamadas == 1
    assert gate.chamadas == 1


def test_pergunta_curta_sem_historico_continua_bloqueada():
    # Sem historico, "do emitente" e curta demais para o gate heuristico.
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    r = p.perguntar("do emitente")
    assert agente.chamadas == 0
    assert gate.chamadas == 0
    assert "não entendi" in r.texto.lower()


def test_pergunta_curta_com_historico_prossegue_para_gate_semantico():
    # Acompanhamento curto (ex.: "do emitente") so faz sentido com o historico;
    # o gate heuristico nao deve bloquea-lo, pois o gate semantico resolve a
    # referencia usando a conversa anterior.
    agente = FakeAgente(
        RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["SP"]])
    )
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        (
            "quantas notas fiscais tem por estado?",
            RespostaAgente(output_kind="text", texto="por qual estado?"),
        )
    ]
    r = p.perguntar("do emitente", historico=historico)
    assert r.output_kind == "table"
    assert gate.chamadas == 1
    assert agente.chamadas == 1


def test_chart_invalido_cai_para_tabela():
    chart = ChartSpec(chart_type="bar", x="x", y="nao_existe")
    agente = FakeAgente(
        RespostaAgente(output_kind="chart", colunas=["x"], linhas=[[1]], chart=chart)
    )
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    r = p.perguntar("qual o total por fornecedor?")
    assert r.output_kind == "table"
    assert r.chart is None


def test_agente_falha_retorna_texto_gracioso():
    class AgenteFalho:
        def responder(self, pergunta: str, contexto: str) -> RespostaAgente:
            raise RuntimeError("boom")

    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(AgenteFalho(), gate)
    r = p.perguntar("qual o total?")
    assert r.output_kind == "text"
    assert "boom" in r.texto


def test_montar_grounding_inclui_tabelas_e_colunas():
    g = montar_grounding(_catalog())
    assert "notas_fiscais" in g
    assert "razao_social_emitente" in g


def test_montar_grounding_avisa_normalizacao_minusculas():
    # O grounding deve alertar que valores de texto sao armazenados em
    # minusculas/sem acento, para o modelo usar LOWER() em filtros.
    g = montar_grounding(_catalog())
    assert "lower(" in g.lower()
    assert "minuscula" in g.lower() or "normalizad" in g.lower()


def test_montar_historico_formata_interacoes():
    historico = [
        ("qual o total?", RespostaAgente(output_kind="text", texto="R$ 1000")),
        ("por estado", RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["sp"]])),
    ]
    g = montar_historico(historico)
    assert "qual o total?" in g
    assert "R$ 1000" in g
    assert "por estado" in g
    assert "tabela de 1 linha(s)" in g


def test_montar_historico_limita_30_interacoes():
    historico = [
        (f"pergunta {i}", RespostaAgente(output_kind="text", texto=f"resp {i}"))
        for i in range(40)
    ]
    g = montar_historico(historico)
    assert "pergunta 0" not in g
    assert "pergunta 9" not in g
    assert "pergunta 10" in g
    assert "pergunta 39" in g


def test_montar_historico_vazio_retorna_vazio():
    assert montar_historico([]) == ""


def test_pergunta_valida_inclui_historico_no_contexto():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        ("qual o total?", RespostaAgente(output_kind="text", texto="R$ 1000"))
    ]
    p.perguntar("e por estado?", historico=historico)
    assert "qual o total?" in agente.ultimo_contexto
    assert "R$ 1000" in agente.ultimo_contexto


def test_gate_recebe_historico_para_interpretar_acompanhamento():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        ("existe nota fora do padrao?", RespostaAgente(output_kind="text", texto="sim, 3 notas"))
    ]
    p.perguntar("qual o criterio que voce usou para eles?", historico=historico)
    assert "existe nota fora do padrao?" in gate.ultimo_historico
    assert "sim, 3 notas" in gate.ultimo_historico


def test_gate_sem_historico_recebe_vazio():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    p.perguntar("qual o total?")
    assert gate.ultimo_historico == ""


def test_queixa_sem_dados_reexecuta_ultima_pergunta():
    # "nao estou vendo nada" refere-se ao turno anterior; o pipeline deve
    # re-executar a ultima pergunta do usuario para re-exibir o resultado,
    # em vez de interpretar a queixa como uma consulta nova.
    agente = FakeAgente(
        RespostaAgente(output_kind="table", colunas=["produto"], linhas=[["Livro A"]])
    )
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        (
            "quais sao os produtos?",
            RespostaAgente(output_kind="table", colunas=["produto"], linhas=[["Livro A"]]),
        )
    ]
    r = p.perguntar("não estou vendo nada", historico=historico)
    assert r.output_kind == "table"
    assert agente.chamadas == 1
    assert agente.ultima_pergunta == "quais sao os produtos?"


def test_queixa_reexecutada_sem_fazer_loop():
    # Duas queixas seguidas nao devem gerar recursao infinita: a segunda queixa
    # re-executa a primeira, que por sua vez re-executa a pergunta original.
    agente = FakeAgente(
        RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["SP"]])
    )
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        (
            "quais os estados?",
            RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["SP"]]),
        )
    ]
    r = p.perguntar("não vejo nada", historico=historico)
    assert r.output_kind == "table"
    assert agente.ultima_pergunta == "quais os estados?"


def test_cade_sozinho_reexecuta_ultima_pergunta():
    # "cadê?" (1 token, aparentemente sem conteudo) refere-se ao turno anterior
    # e deve re-executar a ultima pergunta, nao ser bloqueado como incompreensivel.
    agente = FakeAgente(
        RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["SP"]])
    )
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        (
            "quero por estado",
            RespostaAgente(output_kind="table", colunas=["uf"], linhas=[["SP"]]),
        )
    ]
    r = p.perguntar("cadê?", historico=historico)
    assert r.output_kind == "table"
    assert agente.ultima_pergunta == "quero por estado"


def test_pergunta_normal_com_historico_nao_e_reexecutada():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)
    historico = [
        (
            "quais sao os produtos?",
            RespostaAgente(output_kind="table", colunas=["p"], linhas=[["x"]]),
        )
    ]
    r = p.perguntar("qual o total de vendas?", historico=historico)
    assert r.texto == "ok"
    assert agente.ultima_pergunta == "qual o total de vendas?"


def test_metricas_agregam_agente_e_gate():
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    agente.metricas = {"primario_ok": 2, "fallback_resposta_inutil": 1}
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    gate.metricas = {"contrato_ambigua_incompleta": 3}
    p = _pipeline(agente, gate)

    m = p.metricas

    assert m["primario_ok"] == 2
    assert m["fallback_resposta_inutil"] == 1
    assert m["contrato_ambigua_incompleta"] == 3


def test_pipeline_sem_metricas_nos_injeta_retorna_vazio():
    # Agente/gate fake sem atributo `metricas` nao quebram a propriedade.
    agente = FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    gate = FakeGate(AnaliseSemantica(status="consulta"))
    p = _pipeline(agente, gate)

    assert p.metricas == {}

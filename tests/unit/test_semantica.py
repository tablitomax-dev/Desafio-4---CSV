"""Testes do gate semantico (app/agent/semantica.py) com agentes falsos.

Isola a logica de roteamento sem chamar LLM real: injeta agentes falsos
(com `run_sync`) para validar que apenas `UnexpectedModelBehavior` dispara
a re-execucao com o modelo fallback.
"""

import types

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.agent.semantica import SemanticGate, _SYSTEM_PROMPT, _montar_agente
from app.contracts import AnaliseSemantica


class _FakeAgente:
    def __init__(self, output: AnaliseSemantica, erro: type[Exception] | None = None) -> None:
        self._output = output
        self._erro = erro
        self.chamadas = 0
        self.ultima_mensagem = ""

    def run_sync(self, message: str):
        self.chamadas += 1
        self.ultima_mensagem = message
        if self._erro is not None:
            raise self._erro("falha simulada")
        return types.SimpleNamespace(output=self._output)


def _gate(primario, fallback) -> SemanticGate:
    g = object.__new__(SemanticGate)
    g._primario = primario
    g._fallback = fallback
    g.metricas = {"fallback_falha_tool": 0, "contrato_ambigua_incompleta": 0}
    return g


def test_primario_sucesso_nao_usa_fallback():
    saida = AnaliseSemantica(status="consulta")
    primario = _FakeAgente(saida)
    fallback = _FakeAgente(AnaliseSemantica(status="fora_de_escopo"))
    g = _gate(primario, fallback)

    r = g.analisar("qual o total?", "contexto")

    assert r.status == "consulta"
    assert primario.chamadas == 1
    assert fallback.chamadas == 0


def test_falha_de_tool_usa_fallback():
    primario = _FakeAgente(None, erro=UnexpectedModelBehavior)
    saida_fb = AnaliseSemantica(status="ambigua", interpretacoes=["a", "b"])
    fallback = _FakeAgente(saida_fb)
    g = _gate(primario, fallback)

    r = g.analisar("qual o total?", "contexto")

    assert r.status == "ambigua"
    assert r.interpretacoes == ["a", "b"]
    assert primario.chamadas == 1
    assert fallback.chamadas == 1


def test_outra_excecao_nao_dispara_fallback():
    primario = _FakeAgente(None, erro=RuntimeError)
    fallback = _FakeAgente(AnaliseSemantica(status="consulta"))
    g = _gate(primario, fallback)

    with pytest.raises(RuntimeError):
        g.analisar("qual o total?", "contexto")
    assert fallback.chamadas == 0


def test_analisar_inclui_historico_na_mensagem():
    saida = AnaliseSemantica(status="consulta")
    primario = _FakeAgente(saida)
    fallback = _FakeAgente(AnaliseSemantica(status="fora_de_escopo"))
    g = _gate(primario, fallback)

    g.analisar(
        "qual o criterio que voce usou para eles?",
        "contexto",
        historico="Conversa anterior\nUsuario: existe nota fora do padrao?",
    )

    assert "Conversa anterior" in primario.ultima_mensagem
    assert "existe nota fora do padrao?" in primario.ultima_mensagem
    assert "qual o criterio que voce usou para eles?" in primario.ultima_mensagem


def test_analisar_sem_historico_nao_inclui_bloco():
    saida = AnaliseSemantica(status="consulta")
    primario = _FakeAgente(saida)
    fallback = _FakeAgente(AnaliseSemantica(status="fora_de_escopo"))
    g = _gate(primario, fallback)

    g.analisar("qual o total?", "contexto")

    assert "Conversa anterior" not in primario.ultima_mensagem


def test_prompt_nao_classifica_vagas_como_fora_de_escopo():
    # Perguntas vagas/ambiguas com interpretacao possivel nos dados (ex.:
    # "as vendas estao boas?", "me conta mais") nao podem virar fora_de_escopo.
    p = _SYSTEM_PROMPT.lower()
    assert "nunca classifique como" in p
    assert "as vendas estao boas?" in p
    assert "fora_de_escopo" in p


def test_ambigua_com_1_interpretacao_usa_fallback():
    # Contrato violado pelo primario: ambigua sem o minimo de 2 opcoes nao da
    # esclarecimento acionavel. O fallback deve reclassificar.
    primario = _FakeAgente(AnaliseSemantica(status="ambigua", interpretacoes=["so uma"]))
    fallback = _FakeAgente(AnaliseSemantica(status="consulta"))
    g = _gate(primario, fallback)

    r = g.analisar("qual o faturamento?", "contexto")

    assert r.status == "consulta"
    assert primario.chamadas == 1
    assert fallback.chamadas == 1
    assert g.metricas["contrato_ambigua_incompleta"] == 1


def test_ambigua_sem_interpretacoes_usa_fallback():
    primario = _FakeAgente(AnaliseSemantica(status="ambigua", interpretacoes=[]))
    fallback = _FakeAgente(
        AnaliseSemantica(status="ambigua", interpretacoes=["por estado", "por empresa"])
    )
    g = _gate(primario, fallback)

    r = g.analisar("qual o faturamento?", "contexto")

    assert r.status == "ambigua"
    assert len(r.interpretacoes) == 2
    assert fallback.chamadas == 1


def test_ambigua_com_2_interpretacoes_nao_usa_fallback():
    primario = _FakeAgente(
        AnaliseSemantica(status="ambigua", interpretacoes=["por estado", "por empresa"])
    )
    fallback = _FakeAgente(AnaliseSemantica(status="consulta"))
    g = _gate(primario, fallback)

    r = g.analisar("qual o faturamento?", "contexto")

    assert r.status == "ambigua"
    assert fallback.chamadas == 0
    assert g.metricas["contrato_ambigua_incompleta"] == 0


def test_ambigua_incompleta_com_fallback_falhando_mantem_primario():
    primario = _FakeAgente(AnaliseSemantica(status="ambigua", interpretacoes=["so uma"]))
    fallback = _FakeAgente(None, erro=UnexpectedModelBehavior)
    g = _gate(primario, fallback)

    r = g.analisar("qual o faturamento?", "contexto")

    assert r.status == "ambigua"
    assert r.interpretacoes == ["so uma"]
    assert fallback.chamadas == 1


def test_gate_monta_com_temperature_zero():
    agent = _montar_agente("modelo-x", api_key="k", base_url="http://x", retries=2)
    assert agent.model_settings == {"temperature": 0.0}


def test_gate_usa_1_retry_por_default():
    # Default: 1 retry de classificacao; so depois o fallback de modelo e acionado.
    g = SemanticGate(
        model_name="primario-x",
        fallback_model_name="fallback-x",
        api_key="k",
        base_url="http://x",
    )
    assert g._primario._max_tool_retries == 1
    assert g._fallback._max_tool_retries == 1
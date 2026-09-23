"""Testes do fallback de modelo por falha de tool (app/agent/agent.py).

Isola a logica de roteamento sem chamar LLM real: injeta agentes falsos
(com `run_sync`) para validar que apenas `UnexpectedModelBehavior` dispara
a re-execucao com o modelo fallback.
"""

import types

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.agent.agent import (
    AgenteConsulta,
    _SYSTEM_PROMPT,
    _montar_agente,
    _numero_confiavel,
    _extrair_numeros,
    _texto_com_numero_nao_confiavel,
)
from app.contracts import ChartSpec, RespostaAgente


class _FakeAgente:
    def __init__(
        self,
        output: RespostaAgente | None,
        erro: type[Exception] | None = None,
        tool_resultado: dict | None = None,
        resumo: dict | None = None,
    ) -> None:
        self._output = output
        self._erro = erro
        self._tool_resultado = tool_resultado
        self._resumo = resumo
        self.chamadas = 0
        self._tools = None

    def run_sync(self, message: str):
        self.chamadas += 1
        if self._erro is not None:
            raise self._erro("falha simulada")
        # Simula a chamada de tool do modelo real: o resultado/resumo ficam
        # disponiveis para o fallback deterministico do agente.
        if self._tools is not None:
            if self._tool_resultado is not None:
                self._tools.ultimo_resultado = self._tool_resultado
            if self._resumo is not None:
                self._tools.ultimo_resumo = self._resumo
        return types.SimpleNamespace(output=self._output)


class _FakeTools:
    def __init__(self, ultimo_resultado: dict | None = None) -> None:
        self.ultimo_resultado = ultimo_resultado
        self.ultimo_resumo = None

    def limpar_ultimo_resultado(self) -> None:
        self.ultimo_resultado = None
        self.ultimo_resumo = None


def _agente(primario, fallback, tools=None) -> AgenteConsulta:
    ag = object.__new__(AgenteConsulta)
    ag._primario = primario
    ag._fallback = fallback
    ag._tools = tools if tools is not None else _FakeTools()
    ag.metricas = {
        "perguntas": 0,
        "primario_ok": 0,
        "fallback_falha_tool": 0,
        "fallback_resposta_inutil": 0,
        "fallback_alucinacao_suspeita": 0,
        "fallback_vazio_fabricado": 0,
    }
    primario._tools = ag._tools
    fallback._tools = ag._tools
    return ag


def test_primario_sucesso_nao_usa_fallback():
    saida = RespostaAgente(output_kind="text", texto="R$ 100")
    # A tool retornou 100: o numero citado e confiavel, nao ha suspeita.
    primario = _FakeAgente(
        saida, tool_resultado={"colunas": ["total"], "linhas": [[100.0]]}
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "R$ 100"
    assert primario.chamadas == 1
    assert fallback.chamadas == 0


def test_falha_de_tool_usa_fallback():
    primario = _FakeAgente(None, erro=UnexpectedModelBehavior)
    saida_fb = RespostaAgente(output_kind="text", texto="resposta do fallback")
    fallback = _FakeAgente(saida_fb)
    ag = _agente(primario, fallback)

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "resposta do fallback"
    assert primario.chamadas == 1
    assert fallback.chamadas == 1


def test_outra_excecao_nao_dispara_fallback():
    primario = _FakeAgente(None, erro=RuntimeError)
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    with pytest.raises(RuntimeError):
        ag.responder("qual o total?", "contexto")
    assert fallback.chamadas == 0


def test_prompt_exige_propagar_linhas_da_tool():
    # O prompt deve impedir o modelo de responder "sem dados" quando a tool
    # consultar retornou linhas (falha observada em 'vendas por estado').
    assert "nunca diga" in _SYSTEM_PROMPT.lower()
    assert "retornou linhas" in _SYSTEM_PROMPT.lower()


def test_prompt_exige_filtros_normalizados_com_lower():
    # Os dados sao armazenados em minusculas/sem acento; o prompt deve instruir
    # o modelo a usar LOWER() em filtros de texto para nao retornar 0 linhas
    # (ex.: WHERE uf_emitente = 'SP' nao acha nada; WHERE LOWER(...) = 'sp' sim).
    p = _SYSTEM_PROMPT.lower()
    assert "lower(" in p
    assert "minuscula" in p or "normalizad" in p


def test_prompt_proibe_expor_raciocinio_interno():
    # O modelo nao pode vazar o chain-of-thought para o usuario (ex.:
    # "a conversa anterior indica que..."). Deve responder so o resultado final.
    p = _SYSTEM_PROMPT.lower()
    assert "nunca mostre" in p
    assert "raciocinio" in p
    assert "não exponha" in p or "nao exponha" in p or "interno" in p


def test_prompt_contem_roteiro_de_consulta():
    # O prompt deve orientar o modelo a escolher a tool e os filtros certos.
    p = _SYSTEM_PROMPT.lower()
    assert "roteiro de consulta" in p
    assert "granularidade" in p
    assert "tool certa" in p


def test_prompt_orienta_uso_das_tools_analiticas():
    # Perguntas de distribuicao/dispersao ("fora do padrao", "acima da media")
    # devem usar as tools deterministas estatisticas()/detectar_outliers(), e
    # nao SQL manual de estatistica (que gera erros de sintaxe).
    p = _SYSTEM_PROMPT.lower()
    assert "fora do padrao" in p
    assert "detectar_outliers" in p
    assert "estatisticas" in p
    assert "não monte sql de estatistica" in p or "nao monte sql" in p


def test_prompt_exige_resolver_contexto_de_mensagens_incompletas():
    # Mensagens incompletas referenciam turnos anteriores (pronomes/elipses);
    # o modelo deve resolver a referencia e continuar o MESMO assunto, nunca
    # responder "nao entendi".
    p = _SYSTEM_PROMPT.lower()
    assert "conversa anterior" in p
    assert "referencia" in p and "resolva" in p
    assert "nunca responda" in p or "nao responda" in p


def test_prompt_nao_expoe_resolucao_de_contexto():
    # A resolucao de contexto nao deve aparecer no texto final (vazamento).
    p = _SYSTEM_PROMPT.lower()
    assert "não exponha essa resolução" in p or "nao exponha essa resolucao" in p
    assert "conversa anterior indica" in p


def test_prompt_instrui_agregar_separadamente_para_comparar():
    # Comparar total das notas x soma dos itens exige agregar cada tabela em
    # separado (join antes da agregacao duplicaria valores).
    p = _SYSTEM_PROMPT.lower()
    assert "nfs_cabecalho" in p and "nfs_itens" in p
    assert "nunca junte as tabelas antes de agregar" in p


def test_prompt_reforca_lista_completa_por_dimensao():
    # "por <dimensao>" deve devolver a lista completa com a coluna da dimensao,
    # nunca apenas o total geral (falha observada: 'quero por estado' voltou
    # so o faturamento_total sem a coluna de estado).
    import re

    p = re.sub(r"\s+", " ", _SYSTEM_PROMPT.lower())
    assert "por <dimensao>" in p
    assert "todas as linhas" in p
    assert "incorreta" in p


def test_resposta_inutil_usa_fallback():
    # Modelo primario devolveu "..." (travou); o fallback deve responder.
    primario = _FakeAgente(RespostaAgente(output_kind="text", texto="..."))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="resposta util"))
    ag = _agente(primario, fallback)

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "resposta util"
    assert primario.chamadas == 1
    assert fallback.chamadas == 1


def test_resposta_vazia_usa_fallback():
    primario = _FakeAgente(RespostaAgente(output_kind="text", texto="   "))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="ok"))
    ag = _agente(primario, fallback)

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "ok"


def test_resposta_placeholder_usa_fallback():
    # Modelo devolveu um placeholder nao preenchido ("[COMPLETAR AQUI]"):
    # o fallback deve ser tentado.
    primario = _FakeAgente(RespostaAgente(output_kind="text", texto="[COMPLETAR AQUI]"))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="resposta util"))
    ag = _agente(primario, fallback)

    r = ag.responder("qual a media?", "contexto")

    assert r.texto == "resposta util"
    assert fallback.chamadas == 1


def test_resposta_util_nao_usa_fallback():
    primario = _FakeAgente(
        RespostaAgente(output_kind="text", texto="R$ 100"),
        tool_resultado={"colunas": ["total"], "linhas": [[100.0]]},
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "R$ 100"
    assert fallback.chamadas == 0


def test_tabela_vazia_sem_tool_dispara_fallback_vazio_fabricado():
    # Tabela com 0 linhas e NENHUMA tool rodando = "vazio fabricado": o modelo
    # afirmou que nao ha dados sem consultar o banco. O fallback deve ser
    # tentado (antes essa resposta virava "nao encontrei dados" no pipeline).
    primario = _FakeAgente(RespostaAgente(output_kind="table", colunas=[], linhas=[]))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("mostre notas", "contexto")

    assert r.texto == "fallback"
    assert fallback.chamadas == 1
    assert ag.metricas["fallback_vazio_fabricado"] == 1


def test_tabela_vazia_com_tool_vazia_nao_dispara_fallback():
    # Tabela vazia MAS a tool rodou e devolveu 0 linhas: o vazio e legitimo
    # (a consulta realmente nao achou dados). Sem fallback, sem fabricacao.
    primario = _FakeAgente(
        RespostaAgente(output_kind="table", colunas=[], linhas=[]),
        tool_resultado={"colunas": ["estado"], "linhas": []},
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("mostre notas canceladas", "contexto")

    assert r.output_kind == "table"
    assert fallback.chamadas == 0
    assert ag.metricas["primario_ok"] == 1


def test_texto_sem_dados_sem_tool_dispara_fallback():
    # Texto "nao encontrei dados" sem nenhuma tool rodando: fabricacao.
    primario = _FakeAgente(
        RespostaAgente(output_kind="text", texto="Não encontrei dados para essa consulta.")
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("quais as notas?", "contexto")

    assert r.texto == "fallback"
    assert fallback.chamadas == 1
    assert ag.metricas["fallback_vazio_fabricado"] == 1


def test_texto_sem_dados_com_tool_vazia_nao_dispara_fallback():
    # Texto "sem dados" MAS a tool rodou e retornou 0 linhas: legitimo.
    primario = _FakeAgente(
        RespostaAgente(output_kind="text", texto="Não há dados para essa consulta."),
        tool_resultado={"colunas": ["estado"], "linhas": []},
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback)

    r = ag.responder("notas de janeiro?", "contexto")

    assert r.output_kind == "text"
    assert fallback.chamadas == 0


def test_tabela_vazia_preenchida_com_ultimo_resultado_da_tool():
    saida = RespostaAgente(output_kind="table", colunas=None, linhas=[])
    # A tool desta pergunta retornou dados; o modelo so nao os propagou.
    primario = _FakeAgente(
        saida, tool_resultado={"colunas": ["estado"], "linhas": [["SP"]]}
    )
    ag = _agente(
        primario,
        _FakeAgente(RespostaAgente(output_kind="text", texto="fallback")),
        tools=_FakeTools(),
    )

    r = ag.responder("mostre as vendas por estado", "contexto")

    assert r.output_kind == "table"
    assert r.colunas == ["estado"]
    assert r.linhas == [["SP"]]


def test_tabela_vazia_sem_resultado_da_tool_dispara_fallback():
    # Tabela vazia SEM resultado de tool = vazio fabricado (o modelo nao rodou
    # consulta nenhuma). O fallback deve responder, em vez de o pipeline
    # converter a tabela vazia em "nao encontrei dados".
    primario = _FakeAgente(RespostaAgente(output_kind="table", colunas=None, linhas=[]))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("mostre notas canceladas", "contexto")

    assert r.texto == "fallback"
    assert fallback.chamadas == 1


def test_tabela_nao_vazia_nao_e_alterada():
    saida = RespostaAgente(output_kind="table", colunas=["a"], linhas=[[1]])
    primario = _FakeAgente(
        saida, tool_resultado={"colunas": ["x"], "linhas": [["z"]]}
    )
    ag = _agente(primario, _FakeAgente(None), tools=_FakeTools())

    r = ag.responder("qual o total?", "contexto")

    assert r.colunas == ["a"]
    assert r.linhas == [[1]]


def test_chart_vazio_preenchido_com_ultimo_resultado_da_tool():
    saida = RespostaAgente(
        output_kind="chart",
        colunas=None,
        linhas=[],
        chart=ChartSpec(chart_type="bar", x="estado", y="valor"),
    )
    primario = _FakeAgente(
        saida, tool_resultado={"colunas": ["estado"], "linhas": [["SP"]]}
    )
    ag = _agente(primario, _FakeAgente(None), tools=_FakeTools())

    r = ag.responder("grafico por estado", "contexto")

    assert r.output_kind == "chart"
    assert r.colunas == ["estado"]
    assert r.linhas == [["SP"]]


def test_texto_resumo_convertido_em_tabela_quando_tool_tem_linhas():
    # O modelo executou a consulta (10 linhas reais) mas devolveu so um texto
    # "a consulta retornou 10 linhas" em vez da tabela. A tool tem o resultado:
    # a resposta vira tabela com as linhas reais, preservando o texto.
    saida = RespostaAgente(
        output_kind="text",
        texto="No período analisado, a consulta retornou 10 linhas.",
    )
    primario = _FakeAgente(
        saida,
        tool_resultado={
            "colunas": ["descricao_produto_servico", "valor_total"],
            "linhas": [["Livro A", 522.5], ["Lanterna", 159.6]],
        },
    )
    ag = _agente(primario, _FakeAgente(None), tools=_FakeTools())

    r = ag.responder("quais sao os produtos?", "contexto")

    assert r.output_kind == "table"
    assert r.colunas == ["descricao_produto_servico", "valor_total"]
    assert len(r.linhas) == 2
    assert "retornou 10 linhas" in (r.texto or "")


def test_texto_analitico_nao_e_convertido_em_tabela():
    # Resposta analitica de texto (sem menção a "retornou N linhas") nao deve
    # virar tabela mesmo com a tool tendo linhas. Sem numeros no texto, a
    # checagem anti-alucinacao nao dispara.
    saida = RespostaAgente(
        output_kind="text", texto="O faturamento ficou concentrado no estado de Sao Paulo."
    )
    primario = _FakeAgente(
        saida, tool_resultado={"colunas": ["uf_emitente"], "linhas": [["SP"]]}
    )
    ag = _agente(primario, _FakeAgente(None), tools=_FakeTools())

    r = ag.responder("qual o total?", "contexto")

    assert r.output_kind == "text"
    assert "faturamento" in (r.texto or "")


def test_texto_resumo_sem_resultado_da_tool_nao_converte():
    # Texto "retornou N linhas" sem resultado real de tool: nao ha o que converter
    # em tabela. Alem disso, o numero (10) nao veio de nenhuma tool -> suspeito,
    # o fallback responde.
    saida = RespostaAgente(output_kind="text", texto="a consulta retornou 10 linhas")
    primario = _FakeAgente(saida)
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="resposta util"))
    ag = _agente(
        primario,
        fallback,
        tools=_FakeTools(ultimo_resultado=None),
    )

    r = ag.responder("quais sao os produtos?", "contexto")

    assert r.output_kind == "text"
    assert r.texto == "resposta util"
    assert fallback.chamadas == 1


# --- anti-alucinacao de numeros ---------------------------------------------


def test_ultimo_resultado_limpo_entre_perguntas():
    # A 1a pergunta retorna dados; a 2a pergunta o modelo devolve tabela vazia
    # sem rodar tool nenhuma (vazio fabricado). O fallback e tentado e NAO pode
    # preencher com o resultado da 1a pergunta (dado obsoleto de outra consulta).
    primario = _FakeAgente(RespostaAgente(output_kind="table", colunas=None, linhas=[]))
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="resposta do fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    primario._tool_resultado = {"colunas": ["estado"], "linhas": [["SP"]]}
    r1 = ag.responder("vendas por estado", "contexto")
    assert r1.linhas == [["SP"]]

    primario._tool_resultado = None
    r2 = ag.responder("notas canceladas", "contexto")
    assert r2.texto == "resposta do fallback"
    assert fallback.chamadas == 1


def test_numero_nao_confiavel_dispara_fallback():
    # O modelo inventou "104 notas" sem nenhuma tool retornar esse valor
    # (alucinacao). O fallback deve responder.
    primario = _FakeAgente(
        RespostaAgente(output_kind="text", texto="Foram 104 notas emitidas.")
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="resposta util"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("quantas notas?", "contexto")

    assert r.texto == "resposta util"
    assert fallback.chamadas == 1
    assert ag.metricas["fallback_alucinacao_suspeita"] == 1


def test_numero_confiavel_nao_dispara_fallback():
    # A tool retornou 100 e o modelo citou 100: numero confiavel, sem fallback.
    primario = _FakeAgente(
        RespostaAgente(output_kind="text", texto="Foram 100 notas emitidas."),
        tool_resultado={"colunas": ["total"], "linhas": [[100.0]]},
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("quantas notas?", "contexto")

    assert r.texto == "Foram 100 notas emitidas."
    assert fallback.chamadas == 0
    assert ag.metricas["primario_ok"] == 1


def test_numero_de_resumo_financeiro_e_confiavel():
    # resumo_financeiro retornou 100 notas / 3370000 de valor; o modelo pode
    # citar 100 e "R$ 3,37 mi" (3,37 = 3370000/1e6) sem ser alucinacao.
    primario = _FakeAgente(
        RespostaAgente(
            output_kind="text", texto="Ao todo foram 100 notas, totalizando R$ 3,37 mi."
        ),
        resumo={
            "total_notas": 100,
            "valores_cabecalho": {"valor_nota_fiscal": 3370000.0},
        },
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("qual o total?", "contexto")

    assert r.texto == "Ao todo foram 100 notas, totalizando R$ 3,37 mi."
    assert fallback.chamadas == 0


def test_percentual_e_ordinal_nao_disparam_suspeita():
    # "50%" (percentual derivado) e "2a" (ordinal) nao sao metricas verificaveis;
    # sem eles, o texto nao tem numero suspeito mesmo sem resultado de tool.
    primario = _FakeAgente(
        RespostaAgente(
            output_kind="text",
            texto="A 2a maior empresa concentra 50% das vendas.",
        )
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("como estao as vendas?", "contexto")

    assert fallback.chamadas == 0


def test_extrair_numeros_ignora_datas_e_anos():
    assert _extrair_numeros("em 30/06/2025 foram 100 notas") == [100.0]
    assert _extrair_numeros("no ano de 2025 a media foi 33.7") == [33.7]


def test_numero_confiavel_aceita_escalas_e_arredondamento():
    # 3,37 ~= 3370000/1e6; 33,7 ~= 3370000/1e5; 33700 ~= 3370000/100.
    confiaveis = {3370000.0}
    assert _numero_confiavel(3.37, confiaveis)
    assert _numero_confiavel(33.7, confiaveis)
    assert _numero_confiavel(33700.0, confiaveis)
    assert not _numero_confiavel(50.0, confiaveis)
    assert not _numero_confiavel(104.0, {100.0})


def test_numero_na_pergunta_do_usuario_e_confiavel():
    # O modelo pode ecoar um filtro da pergunta ("acima de R$ 5000") sem fabricar.
    # A tool retornou 3 linhas: a contagem "3" tambem e confiavel.
    primario = _FakeAgente(
        RespostaAgente(
            output_kind="text",
            texto="Foram 3 notas acima de R$ 5000.",
        ),
        tool_resultado={
            "colunas": ["empresa"],
            "linhas": [["acme"], ["beta"], ["gamma"]],
        },
    )
    fallback = _FakeAgente(RespostaAgente(output_kind="text", texto="fallback"))
    ag = _agente(primario, fallback, tools=_FakeTools())

    r = ag.responder("quantas notas acima de R$ 5000 existem?", "contexto")

    assert fallback.chamadas == 0
    assert r.texto == "Foram 3 notas acima de R$ 5000."


# --- temperatura e prompt ----------------------------------------------------


class _StubTools:
    """Tools minimas (metodos nomeados) para montar um agente real (sem rede)."""

    def esquema(self):
        return []

    def consultar(self, sql: str):
        return {}

    def buscar_textual(self, tabela: str, coluna: str, termo: str):
        return []

    def estatisticas(self, tabela: str, coluna: str):
        return {}

    def detectar_outliers(self, tabela: str, coluna: str, desvios: int = 3):
        return {}

    def resumo_financeiro(self):
        return {}


def test_agente_monta_com_temperature_zero():
    stub = _StubTools()
    agent = _montar_agente("modelo-x", stub, api_key="k", base_url="http://x", retries=2)
    assert agent.model_settings == {"temperature": 0.0}


def test_agente_usa_1_retry_por_tool_por_padrao():
    # Default: 1 retry de tool por modelo (2 tentativas no total); so depois
    # disso o fallback de modelo e acionado (UnexpectedModelBehavior).
    ag = AgenteConsulta(
        _StubTools(),
        model_name="primario-x",
        fallback_model_name="fallback-x",
        api_key="k",
        base_url="http://x",
    )
    assert ag._primario._max_tool_retries == 1
    assert ag._fallback._max_tool_retries == 1


def test_prompt_orienta_uso_resumo_financeiro():
    # Totais gerais devem usar a tool deterministica resumo_financeiro(), nao
    # SQL manual de totais (que gerava erros de sintaxe e alucinacao).
    p = _SYSTEM_PROMPT.lower()
    assert "resumo_financeiro" in p
    assert "totais" in p
    assert "não monte sql de totais" in p or "nao monte sql de totais" in p


def test_prompt_anti_alucinacao_exige_numeros_de_tool():
    # Regra 9: todo numero citado deve vir de uma tool desta pergunta.
    p = _SYSTEM_PROMPT.lower()
    assert "anti-alucinacao" in p
    assert "numero" in p and "tool" in p
    assert "nunca escreva um numero" in p or "nunca escreva" in p

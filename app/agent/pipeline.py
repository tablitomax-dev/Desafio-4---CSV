"""Pipeline de orquestracao da consulta: intent gate -> gate semantico -> agente.

O `pipeline.py` orquestra (fino, sem logica pesada); as validacoes ficam em
`guardrails.py` e a classificacao semantica em `semantica.py`. O agente e o
gate semantico sao injetaveis para permitir testes sem LLM real.
"""

from __future__ import annotations

import re
from typing import Protocol

from app.agent.guardrails import intent_gate, validar_chartspec
from app.agent.semantica import SemanticGate
from app.catalog.catalog import Catalog
from app.contracts import AnaliseSemantica, RespostaAgente
from app.ingestion.normalizer import normalizar_texto


class Agente(Protocol):
    """Contrato do agente usado pelo pipeline (injetavel para testes)."""

    def responder(self, pergunta: str, contexto: str) -> RespostaAgente: ...


class GateSemantico(Protocol):
    """Contrato do gate semantico (injetavel para testes)."""

    def analisar(self, pergunta: str, contexto: str) -> AnaliseSemantica: ...


def montar_grounding(catalog: Catalog, filtros: str = "") -> str:
    """Monta o contexto de schema (grounding) a partir do catalogo."""
    blocos: list[str] = ["Tabelas disponiveis (use estes nomes snake_case):"]
    for tabela in catalog.tabelas:
        colunas = ", ".join(
            f"{c.canonico} [{c.tipo}]" + (" agregavel" if c.agregavel else "")
            for c in tabela.colunas
        )
        blocos.append(f"- {tabela.nome_qualificado}: {colunas}")
    if filtros:
        blocos.append(f"Filtros ativos (aplique via WHERE): {filtros}.")
    blocos.append(
        "Normalizacao: valores de texto (UF, municipio, nomes, descricao) sao "
        "armazenados em minusculas e sem acentos. Em filtros de texto use "
        "LOWER(coluna) = LOWER('valor')."
    )
    blocos.append("Nao invente colunas ou tabelas.")
    return "\n".join(blocos)


def montar_historico(historico: list[tuple[str, RespostaAgente]], limite: int = 30) -> str:
    """Formata as ultimas `limite` interacoes (pergunta + resposta) para contexto.

    Preserva o contexto da conversa para o LLM nao perder o fio da meada. Respostas
    em tabela/grafico sao resumidas (numero de linhas) para nao inflar o contexto.
    """
    if not historico:
        return ""
    blocos: list[str] = ["Conversa anterior (use para manter o contexto):"]
    for pergunta, resposta in historico[-limite:]:
        blocos.append(f"Usuario: {pergunta}")
        if resposta.output_kind == "text":
            blocos.append(f"Assistente: {resposta.texto or ''}")
        else:
            n = len(resposta.linhas or [])
            blocos.append(f"Assistente: (respondeu com tabela de {n} linha(s))")
    return "\n".join(blocos)


class PipelineConsulta:
    """Orquestra uma pergunta em linguagem natural ate a `RespostaAgente`."""

    def __init__(
        self,
        agente: Agente,
        catalog: Catalog,
        gate_semantico: GateSemantico | None = None,
        dataset_id: str | None = None,
    ) -> None:
        self._agente = agente
        self._catalog = catalog
        self._gate = gate_semantico or SemanticGate()
        self.dataset_id = dataset_id

    @property
    def metricas(self) -> dict[str, int]:
        """Agrega as metricas observaveis de agentes/gate (quando presentes).

        Permite que a bateria de testes e a UI acompanhem por que o fallback foi
        usado e quais modos de falha estao ocorrendo (SQL invalido, alucinacao,
        resposta inutil, dicas aplicadas), em vez de depender so da leitura manual.
        """
        total: dict[str, int] = {}
        for obj in (self._agente, self._gate):
            m = getattr(obj, "metricas", None)
            if isinstance(m, dict):
                for chave, valor in m.items():
                    if isinstance(valor, int):
                        total[chave] = total.get(chave, 0) + valor
        return total

    def perguntar(
        self,
        pergunta: str,
        filtros: str = "",
        historico: list[tuple[str, RespostaAgente]] | None = None,
    ) -> RespostaAgente:
        # 0) Consistencia de contexto: o pipeline deve pertencer ao mesmo dataset
        #    do catalogo. Se divergirem, o contexto precisa ser reconstruido.
        if self.dataset_id is not None and self.dataset_id != self._catalog.dataset_id:
            return RespostaAgente(
                output_kind="text",
                texto="Parece que os dados mudaram por aqui. Recarregue o arquivo "
                "para eu reconstruir a análise e continuarmos de onde paramos.",
            )

        # 0.1) Queixa de "nao vejo os dados" (ex.: "nao estou vendo nada"):
        #      refere-se ao turno anterior. Re-executa a ultima pergunta do
        #      usuario para re-exibir o resultado, em vez de interpretar a
        #      queixa como uma consulta nova (que normalmente devolve vazio).
        if historico and _e_queixa_sem_dados(pergunta):
            ultima_pergunta = historico[-1][0]
            return self.perguntar(
                ultima_pergunta, filtros=filtros, historico=historico[:-1]
            )

        # 1) Guardrail heuristico (rapido): bloqueia o claramente proibido.
        veredito = intent_gate(pergunta, self._catalog)
        if veredito.status != "queryable":
            # Pergunta curta de acompanhamento (ex.: "do emitente") so faz
            # sentido com o historico; o gate semantico resolve a referencia
            # usando a conversa anterior. Nesse caso, deixa passar em vez de
            # bloquear no heuristico.
            if not (veredito.status == "precisa_esclarecimento" and historico):
                return RespostaAgente(
                    output_kind="text",
                    texto=veredito.motivo or "Hmm, não entendi a pergunta. Pode reformular?",
                )

        contexto = montar_grounding(self._catalog, filtros=filtros)
        historico_txt = montar_historico(historico) if historico else ""

        # 2) Gate semantico (LLM): entende sinonimos, parafrases e ambiguidade.
        #    Recebe o historico para interpretar perguntas de acompanhamento.
        analise = self._gate.analisar(pergunta, contexto, historico_txt)
        if analise.status == "maliciosa":
            return RespostaAgente(
                output_kind="text",
                texto="Isso eu não posso fazer, e nem quero. Meu papel aqui é "
                "só te ajudar com perguntas sobre as notas fiscais que você carregou.",
            )
        if analise.status == "fora_de_escopo":
            return RespostaAgente(
                output_kind="text",
                texto="Hmm, essa pergunta foge dos dados que você carregou. "
                "Pode reformular, ou perguntar sobre as notas fiscais "
                "(fornecedores, valores, produtos)?",
            )
        if analise.status == "ambigua" and analise.interpretacoes:
            return RespostaAgente(
                output_kind="text",
                texto=_texto_ambiguidade(analise),
            )

        # Status 'ambigua' sem interpretacoes e quebra de contrato do LLM (o
        # prompt exige >= 2 opcoes). Sem opcoes nao ha esclarecimento acionavel
        # a oferecer; seguir como consulta evita travar perguntas validas.

        # 3) Agente: interpreta a intencao e consulta o banco.
        contexto_agente = contexto
        if historico_txt:
            contexto_agente = f"{contexto}\n\n{historico_txt}"
        try:
            resposta = self._agente.responder(pergunta, contexto_agente)
        except Exception as exc:  # noqa: BLE001 - falha graciosa ao usuario
            return RespostaAgente(
                output_kind="text",
                texto=f"Ops, tropecei aqui! Deu um erro inesperado: {exc}. "
                "Pode tentar de novo?",
            )

        if resposta.output_kind == "chart" and (
            resposta.chart is None
            or not validar_chartspec(resposta.chart, resposta.colunas or []).ok
        ):
            resposta = RespostaAgente(
                output_kind="table",
                texto="Não consegui montar o gráfico, mas trouxe os dados "
                "como tabela pra você.",
                colunas=resposta.colunas,
                linhas=resposta.linhas,
            )

        # Resultado vazio: devolve feedback util em vez de tabela em branco.
        if resposta.output_kind == "table" and not resposta.linhas:
            resposta = RespostaAgente(
                output_kind="text",
                texto="Não encontrei dados para essa consulta. Pode reformular "
                "a pergunta, ou verificar se há filtros ativos?",
            )
        return resposta


def _texto_ambiguidade(analise: AnaliseSemantica) -> str:
    """Monta a mensagem de esclarecimento com as interpretacoes geradas."""
    opcoes = analise.interpretacoes or []
    if not opcoes:
        return (
            "Sua pergunta pode ter mais de uma interpretação. "
            "Pode reformular com mais detalhes?"
        )
    linhas = "\n".join(f"{i}. {op}" for i, op in enumerate(opcoes, start=1))
    return (
        "Sua pergunta pode ter mais de uma interpretação. "
        f"Qual delas você quis dizer?\n{linhas}"
    )


# Frases (normalizadas, sem acento) que sinalizam que o usuario nao conseguiu
# visualizar o resultado do turno anterior e quer re-exibi-lo.
_QUEIXAS_SEM_DADOS = frozenset(
    {
        "cade",
        "cade a tabela",
        "cade os dados",
        "cade o grafico",
        "cade a resposta",
        "cade o resultado",
        "cade os resultados",
        "nao estou vendo nada",
        "nao estou vendo",
        "nao estou vendo os dados",
        "nao vejo nada",
        "nao vejo",
        "nao vejo os dados",
        "nao aparece",
        "nao apareceu",
        "nao apareceram",
        "nao apareceu nada",
        "nao vem nada",
        "nao veio nada",
        "nao encontrei dados",
    }
)


def _e_queixa_sem_dados(pergunta: str) -> bool:
    """True se a pergunta e uma queixa de resultado nao visivel (re-exibir anterior)."""
    q = re.sub(r"[^a-z0-9\s]+", " ", normalizar_texto(pergunta))
    return any(frase in q for frase in _QUEIXAS_SEM_DADOS)

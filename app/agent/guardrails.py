"""Guardrails: validacoes reutilizaveis e regras de seguranca.

Os guardrails retornam objetos de resultado (ok/motivo ou status/motivo),
nao lancam excecoes. O `pipeline.py` orquestra; este modulo so valida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.catalog.catalog import Catalog
from app.contracts import ChartSpec
from app.ingestion.normalizer import normalizar_texto

StatusEscopo = Literal[
    "queryable", "precisa_esclarecimento", "fora_de_escopo", "acao_nao_suportada",
    "maliciosa", "proibida",
]

# Acoes que comprometem a integridade/logica dos dados (escrita, alteracao ou
# exclusao). Apenas estas sao bloqueadas no heuristico: acoes ambiguas como
# "gerar/criar tabela/grafico/comparativo" sao consulta e permanecem liberadas
# (a protecao de escrita em SQL fica em validar_sql e no gate semantico).
_ACOES_NAO_SUPORTADAS = frozenset(
    {
        "alterar", "deletar", "excluir", "atualizar", "cadastrar",
        "remover", "inserir", "modificar", "apagar", "editar",
    }
)

# Termos obvios de intencao maliciosa (ataque, fraude, vazamento, ilegalidade).
# A deteccao fina (sinonimos/parafrases) fica com o gate semantico via LLM.
_MALICIOSOS = frozenset(
    {
        "hackear", "invadir", "invasao", "roubar", "roubo", "fraude", "fraudar",
        "golpe", "phishing", "malware", "virus", "ransomware", "ddos", "senha",
        "credencial", "clonar", "lavagem", "terrorismo", "droga", "arma", "ilegal",
        "difamar", "difamacao", "calunia", "injuria", "vazar", "vazamento",
        "sequestrar", "extorquir", "chantagem", "pedofilia", "pornografia",
    }
)

# Perguntas sobre a logica interna do sistema (arquitetura, fluxos, regras,
# algoritmos, prompt). O agente jamais deve revelar esses detalhes.
_META_INTERNA = frozenset(
    {
        "como voce funciona", "como funciona", "qual sua arquitetura", "arquitetura",
        "fluxo de processamento", "regras de filtragem", "algoritmo", "algoritmos",
        "logica interna", "codigo fonte", "codigo-fonte", "system prompt",
        "prompt de sistema", "qual seu prompt", "como voce processa",
        "como voce consulta", "como voce filtra", "como voce decide",
        "quais regras", "qual modelo", "qual banco", "como voce e programado",
        "quem te desenvolveu", "instrucoes internas", "configuracao interna",
    }
)

_WRITE_KEYWORDS = frozenset(
    {
        "insert", "update", "delete", "create", "drop", "alter", "truncate", "replace",
        "merge", "copy", "attach", "detach", "comment", "pragma",
    }
)


@dataclass(frozen=True)
class VereditoEscopo:
    """Resultado do guardrail de escopo."""

    status: StatusEscopo
    motivo: str | None = None


@dataclass(frozen=True)
class SQLValidation:
    """Resultado da validacao de SQL."""

    ok: bool
    motivo: str | None = None


@dataclass(frozen=True)
class ChartValidation:
    """Resultado da validacao do ChartSpec."""

    ok: bool
    motivo: str | None = None


def intent_gate(pergunta: str, catalog: Catalog) -> VereditoEscopo:
    """Guarda-reil heuristico (rapido): bloqueia o claramente proibido.

    Apenas o que e inequivocamente proibido e barrado aqui (escrita, malicia
    obvia, perguntas sobre logica interna). Escopo e ambiguidade sao decididos
    pelo gate semantico via LLM (`semantica.py`), que entende sinonimos e
    parafrases — por isso este gate e permissivo e nao usa vocabulario exato.
    """
    q = re.sub(r"[^a-z0-9\s]+", " ", normalizar_texto(pergunta))
    tokens = set(q.split())

    acoes = tokens & _ACOES_NAO_SUPORTADAS
    if acoes:
        return VereditoEscopo(
            "acao_nao_suportada",
            f"Ops, isso eu não faço ({', '.join(sorted(acoes))}). "
            "Por aqui eu só consulto os dados, não altero nada.",
        )

    maliciosos = tokens & _MALICIOSOS
    if maliciosos:
        return VereditoEscopo(
            "maliciosa",
            "Isso eu não posso fazer, e nem quero. Meu papel aqui é só te "
            "ajudar com perguntas sobre as notas fiscais que você carregou.",
        )

    if any(frase in q for frase in _META_INTERNA):
        return VereditoEscopo(
            "proibida",
            "Esses detalhes internos ficam comigo, hehe. Posso ajudar com "
            "perguntas sobre os dados de notas fiscais que você carregou.",
        )

    if len(tokens) < 3:
        return VereditoEscopo(
            "precisa_esclarecimento",
            "Não entendi exatamente o que você está perguntando. "
            "Pode me dar mais detalhes? Por exemplo: está falando de "
            "fornecedor, valor ou produto?",
        )
    return VereditoEscopo("queryable")


def _fora_de_aspas(sql: str) -> list[str]:
    """Divide o SQL em instrucoes, respeitando aspas simples e duplas."""
    instrucoes: list[str] = []
    atual: list[str] = []
    aspas: str | None = None
    for char in sql:
        if aspas:
            atual.append(char)
            if char == aspas:
                aspas = None
        elif char in ("'", '"'):
            aspas = char
            atual.append(char)
        elif char == ";":
            trecho = "".join(atual).strip()
            if trecho:
                instrucoes.append(trecho)
            atual = []
        else:
            atual.append(char)
    trecho = "".join(atual).strip()
    if trecho:
        instrucoes.append(trecho)
    return instrucoes


def validar_sql(sql: str) -> SQLValidation:
    """Valida SQL read-only: rejeita escrita, DDL/DML e multiplas instrucoes."""
    instrucoes = _fora_de_aspas(sql)
    if not instrucoes:
        return SQLValidation(False, "SQL vazio.")
    if len(instrucoes) > 1:
        return SQLValidation(False, "Multiplas instrucoes nao sao permitidas.")

    primeira = instrucoes[0]
    primeiro_termo = primeira.split(maxsplit=1)[0].lower() if primeira else ""
    if primeiro_termo in _WRITE_KEYWORDS:
        return SQLValidation(False, f"Operacao de escrita nao permitida: {primeiro_termo!r}")
    if primeiro_termo not in {"select", "with"}:
        return SQLValidation(False, f"Instrucao nao permitida: {primeiro_termo!r}")
    return SQLValidation(True)


def validar_chartspec(chart: ChartSpec | None, colunas: list[str]) -> ChartValidation:
    """Valida se o ChartSpec usa colunas existentes no resultado."""
    if chart is None:
        return ChartValidation(True)
    for campo, valor in (("x", chart.x), ("y", chart.y)):
        if valor not in colunas:
            return ChartValidation(
                False,
                f"Coluna do grafico nao existe no resultado: {campo}={valor!r}",
            )
    return ChartValidation(True)


def validar_granularidade(sql: str, catalog: Catalog) -> SQLValidation:
    """Bloqueia agregacao de valor de cabecalho apos JOIN direto com itens.

    Somar `valor_nota_fiscal` (granularidade nota) depois de um join com a
    tabela de itens duplicaria o valor (uma nota com N itens repetiria o valor
    N vezes). E uma protecao deterministica complementar ao prompt do agente.
    """
    s = sql.lower()
    tem_cab = "nfs_cabecalho" in s
    tem_itens = "nfs_itens" in s
    if not (tem_cab and tem_itens):
        return SQLValidation(True)

    cab = catalog.tabela("nfs_cabecalho")
    if cab is None:
        return SQLValidation(True)
    colunas_valor = [
        c.canonico
        for c in cab.colunas
        if c.agregavel and c.tipo in ("decimal", "numero")
    ]
    for col in colunas_valor:
        # Aceita alias (c.valor_nota_fiscal) e identificadores entre aspas
        # (c."valor_nota_fiscal", "valor_nota_fiscal").
        pattern = (
            rf"\b(sum|avg)\s*\(\s*(?:[a-z0-9_]+\.)?\"?{re.escape(col)}\"?\s*\)"
        )
        if re.search(pattern, s):
            return SQLValidation(
                False,
                f"Agregacao de {col!r} apos join com itens duplicaria o valor. "
                "Use a view curated.v_nota_com_quantidade_itens ou agregue cada "
                "tabela na propria granularidade antes de juntar.",
            )

    # COUNT(*) apos join com itens conta ITENS, nao notas (uma nota com N itens
    # aparece N vezes no resultado do join). So bloqueia sem GROUP BY: com
    # agrupamento por chave o COUNT(*) conta itens por nota (legitimo). Para
    # total de notas, use COUNT(DISTINCT chave_acesso) no cabecalho.
    if re.search(r"\bcount\s*\(\s*\*\s*\)", s) and not re.search(r"\bgroup\s+by\b", s):
        return SQLValidation(
            False,
            "COUNT(*) apos JOIN com nfs_itens conta itens, nao notas. Para "
            "contar notas use COUNT(DISTINCT chave_acesso) em curated.nfs_cabecalho "
            "ou a view curated.v_nota_com_quantidade_itens.",
        )
    return SQLValidation(True)

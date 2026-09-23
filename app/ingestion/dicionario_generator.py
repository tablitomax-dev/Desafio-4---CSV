"""Geracao automatica do dicionario de dados a partir dos CSVs carregados.

O usuario envia apenas CSVs puros; este modulo infere tabelas, colunas (snake_case),
tipos e regras (fuzzy/exato) de forma conservadora, para que o agente e os guardrails
usem um schema confiavel. Regras criticas (fuzzy proibido em chaves) sao embutidas aqui.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.catalog.catalog import ColunaDict, DicionarioDados, TabelaDict
from app.ingestion.normalizer import normalizar_texto

_TOK_IDENTIFICADOR = frozenset(
    {"cnpj", "cpf", "chave", "numero", "inscricao", "cfop", "ncm", "serie", "modelo", "codigo"}
)
_TOK_DATA = frozenset({"data", "emissao"})
_TOK_NUMERICO = frozenset({"valor", "quantidade", "qtd", "total", "unitario", "preco", "peso"})
_TOK_CATEGORIA = frozenset(
    {
        "natureza", "uf", "destino", "tipo", "unidade", "presenca", "consumidor",
        "indicador", "evento",
    }
)
_TOK_DESCRITIVA = frozenset(
    {"razao", "nome", "descricao", "municipio", "cidade", "produto", "servico"}
)

_RE_DATA = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$|^\d{4}-\d{2}-\d{2}$")
_AMOSTRA = 200


def _snake(nome: str) -> str:
    """Converte um cabecalho em identificador snake_case determinístico.

    Identificadores SQL nao podem comecar com digito sem aspas; prefixa com
    `_` para que o LLM gere SQL valido (ex.: `2024_valor` -> `_2024_valor`).
    """
    s = normalizar_texto(nome)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = f"_{s}"
    return s


def _canonico_coluna(origem: str) -> str:
    """Canonico da coluna, padronizando a CHAVE DE ACESSO para `chave_acesso`.

    O relacionamento cabecalho-itens e feito por `chave_acesso`; sem essa
    padronizacao, o gerador produziria `chave_de_acesso`, quebrando a relacao.
    """
    s = _snake(origem)
    if "chave" in s and "acesso" in s:
        return "chave_acesso"
    return s


def _amostra(serie: pd.Series) -> list[str]:
    valores: list[str] = []
    for v in serie.dropna().head(_AMOSTRA):
        s = str(v).strip()
        if s:
            valores.append(s)
    return valores


def _proporcao_datas(amostra: list[str]) -> float:
    if not amostra:
        return 0.0
    return sum(1 for v in amostra if _RE_DATA.match(v)) / len(amostra)


def _proporcao_numerico(amostra: list[str]) -> float:
    if not amostra:
        return 0.0

    def _eh_numero(v: str) -> bool:
        s = v.replace(".", "").replace(",", ".")
        try:
            float(s)
            return True
        except ValueError:
            return False

    return sum(1 for v in amostra if _eh_numero(v)) / len(amostra)


def _inferir(origem: str, canonico: str, serie: pd.Series) -> ColunaDict:
    """Infere tipo/regras de uma coluna (heuristica de nome + amostragem)."""
    tokens = set(canonico.split("_"))
    amostra = _amostra(serie)

    if tokens & _TOK_DATA or _proporcao_datas(amostra) >= 0.7:
        return ColunaDict(
            origem=origem, canonico=canonico, tipo="data", regra_parse="dd/mm/yyyy",
            regra_busca="exato", agregavel=True,
        )

    # Categoria antes de identificador: colunas como "ncm_sh_tipo_de_produto"
    # tem tokens de codigo ("ncm") mas o significado dominante e de categoria
    # ("tipo"), permitindo agrupar por elas (ex.: "categorias mais vendidas").
    # O token "codigo" (in: _TOK_IDENTIFICADOR) nao e categoria, entao
    # "codigo_ncm_sh" continua identificador.
    if tokens & _TOK_CATEGORIA:
        return ColunaDict(
            origem=origem, canonico=canonico, tipo="categoria", regra_busca="exato",
            agregavel=True,
        )

    if tokens & _TOK_IDENTIFICADOR:
        return ColunaDict(
            origem=origem, canonico=canonico, tipo="identificador", regra_busca="exato"
        )

    if tokens & _TOK_NUMERICO or _proporcao_numerico(amostra) >= 0.7:
        return ColunaDict(
            origem=origem, canonico=canonico, tipo="decimal", regra_parse="decimal_br",
            regra_busca="nenhum", agregavel=True,
        )

    if tokens & _TOK_DESCRITIVA:
        return ColunaDict(
            origem=origem, canonico=canonico, tipo="texto", fuzzy_permitido=True,
            regra_busca="fuzzy_controlado",
        )

    return ColunaDict(origem=origem, canonico=canonico, tipo="texto", regra_busca="exato")


def gerar_tabela(nome_csv: str, df: pd.DataFrame) -> TabelaDict:
    """Gera a definicao de tabela a partir do nome do CSV e de seu conteudo."""
    stem = Path(nome_csv).stem
    nome = _snake(stem) or "tabela"
    colunas = [
        _inferir(col, _canonico_coluna(col), df[col]) for col in df.columns
    ]
    return TabelaDict(nome=nome, fonte=stem, colunas=colunas)


def gerar_dicionario(dados: list[tuple[str, pd.DataFrame]]) -> DicionarioDados:
    """Gera o dicionario de dados a partir de uma lista de (nome_csv, dataframe)."""
    tabelas = [gerar_tabela(nome, df) for nome, df in dados]
    return DicionarioDados(tabelas=tabelas)

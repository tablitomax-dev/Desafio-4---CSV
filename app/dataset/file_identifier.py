"""Identificacao deterministica de arquivos: cabecalho vs itens.

Ordem de decisao por arquivo:
1. nome conhecido do arquivo;
2. assinatura de colunas obrigatorias;
3. compatibilidade de tipos/quantidade de colunas;
4. classificacao;
5. rejeicao se houver ambiguidade.

Nunca classifica silenciosamente um CSV com nome inesperado, colunas
incompletas, colunas de itens, ou dois candidatos ao mesmo papel.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.contracts import Issue

Papel = Literal["cabecalho", "itens", "auxiliar", "desconhecido"]

# Nomes canonicos das tabelas curated.
NOME_CABECALHO = "nfs_cabecalho"
NOME_ITENS = "nfs_itens"

_TOK_CABECALHO = frozenset({"cabecalho", "header", "cabeçalho", "nota", "nf"})
_TOK_ITENS = frozenset({"item", "itens", "produto", "produtos"})

# Assinaturas de colunas (snake_case normalizado).
_COL_ITENS = frozenset(
    {
        "numero_produto", "descricao_produto_servico", "valor_total", "quantidade",
        "cfop", "codigo_ncm_sh", "ncm_sh_tipo_produto", "valor_unitario", "unidade",
    }
)
_COL_CABECALHO = frozenset({"valor_nota_fiscal"})


def _tem_chave(colunas: set[str]) -> bool:
    """True se ha uma coluna de CHAVE DE ACESSO (canonico `chave_acesso`)."""
    return any("chave" in c and "acesso" in c for c in colunas)


@dataclass(frozen=True)
class ClassificacaoArquivo:
    """Resultado da classificacao de um arquivo."""

    nome_original: str
    papel: Papel
    nome_canonico: str | None = None


def _snake(nome: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_")
    return s


def _colunas_snake(df: pd.DataFrame) -> set[str]:
    return {_snake(str(c)) for c in df.columns}


def _papel_por_nome(nome: str) -> Papel | None:
    stem = posixpath.splitext(posixpath.basename(nome))[0].lower()
    tokens = set(re.split(r"[^a-z0-9]+", stem))
    if tokens & _TOK_CABECALHO and not (tokens & _TOK_ITENS):
        return "cabecalho"
    if tokens & _TOK_ITENS:
        return "itens"
    return None


def _papel_por_colunas(colunas: set[str]) -> Papel | None:
    if colunas & _COL_ITENS:
        return "itens"
    if colunas & _COL_CABECALHO:
        return "cabecalho"
    return None


class FileIdentifier:
    """Classifica os arquivos extraidos em cabecalho/itens/auxiliar."""

    def classificar(
        self, arquivos: list[tuple[str, pd.DataFrame]]
    ) -> tuple[list[ClassificacaoArquivo], list[Issue]]:
        issues: list[Issue] = []
        classificados: list[ClassificacaoArquivo] = []

        for nome, df in arquivos:
            if not nome.lower().endswith(".csv"):
                classificados.append(ClassificacaoArquivo(nome, "auxiliar"))
                continue

            papel = _papel_por_nome(nome) or _papel_por_colunas(_colunas_snake(df))
            if papel is None:
                classificados.append(ClassificacaoArquivo(nome, "desconhecido"))
                issues.append(
                    Issue(
                        severidade="blocking",
                        codigo="arquivo_nao_classificado",
                        mensagem=f"Arquivo {nome!r} nao pode ser classificado "
                        "como cabecalho ou itens.",
                        tabela=nome,
                    )
                )
                continue

            canonico = NOME_CABECALHO if papel == "cabecalho" else NOME_ITENS
            classificados.append(
                ClassificacaoArquivo(nome_original=nome, papel=papel, nome_canonico=canonico)
            )

        # Ambiguidade: mais de um candidato para o mesmo papel.
        for papel, rotulo in (("cabecalho", "cabecalho"), ("itens", "itens")):
            candidatos = [c for c in classificados if c.papel == papel]
            if len(candidatos) > 1:
                nomes = ", ".join(c.nome_original for c in candidatos)
                issues.append(
                    Issue(
                        severidade="blocking",
                        codigo="ambiguidade_papel",
                        mensagem=f"Mais de um arquivo candidato a {rotulo}: {nomes}.",
                    )
                )

        # Coluna obrigatoria CHAVE DE ACESSO em cada CSV classificado.
        for c in classificados:
            if c.papel not in ("cabecalho", "itens"):
                continue
            df = next(df for nome, df in arquivos if nome == c.nome_original)
            if not _tem_chave(_colunas_snake(df)):
                issues.append(
                    Issue(
                        severidade="blocking",
                        codigo="chave_ausente",
                        mensagem=f"Arquivo {c.nome_original!r} nao possui a coluna "
                        f"obrigatoria 'CHAVE DE ACESSO'.",
                        tabela=c.nome_original,
                    )
                )

        # Cobertura: sem cabecalho e bloqueante (dados fiscais incompletos);
        # sem itens e apenas um aviso (pode haver notas sem itens).
        papeis = {c.papel for c in classificados}
        if "cabecalho" not in papeis:
            issues.append(
                Issue(
                    severidade="blocking",
                    codigo="sem_cabecalho",
                    mensagem="Nenhum arquivo de cabecalho identificado.",
                )
            )
        if "itens" not in papeis:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="sem_itens",
                    mensagem="Nenhum arquivo de itens identificado.",
                )
            )

        return classificados, issues

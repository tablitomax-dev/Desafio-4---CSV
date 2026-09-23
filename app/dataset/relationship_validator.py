"""Validacao do relacionamento cabecalho-itens pela CHAVE DE ACESSO.

A regra de formato da chave e configurÃ¡vel (nao hard-code): por padrao, NF-e
com 44 digitos numericos. A validacao distingue chave vazia, com espacos, nao
numerica, tamanho incorreto, duplicada, item sem correspondencia e divergencia
entre arquivos. Tambem valida a consistencia de atributos repetidos entre
cabecalho e itens (cabecalho = fonte autoritativa da nota; itens = do produto).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.catalog.catalog import Catalog
from app.contracts import Issue, Relationship

_COL_CHAVE = "chave_acesso"
# Atributos repetidos entre cabecalho e itens que devem ser consistentes.
_COLS_CONSISTENCIA = (
    "razao_social_emitente",
    "cnpj_destinatario",
    "data_emissao",
    "natureza_operacao",
    "uf_emitente",
    "numero",
)


@dataclass(frozen=True)
class ChaveRule:
    """Regra configurÃ¡vel de formato da CHAVE DE ACESSO."""

    comprimento: int | None = 44
    apenas_numeros: bool = True


class RelationshipValidator:
    """Valida chaves e consistencia cruzada entre cabecalho e itens."""

    def __init__(self, chave_rule: ChaveRule | None = None) -> None:
        self._rule = chave_rule or ChaveRule()

    def validar(
        self, con: Any, catalog: Catalog
    ) -> tuple[list[Relationship], list[Issue], dict[str, int | float | str | None]]:
        issues: list[Issue] = []
        metricas: dict[str, int | float | str | None] = {}

        header = catalog.tabela("nfs_cabecalho")
        items = catalog.tabela("nfs_itens")
        if header is None or items is None:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="sem_relacionamento",
                    mensagem="Relacionamento cabecalho-itens nao avaliado: "
                    "faltam uma ou ambas as tabelas.",
                )
            )
            return [], issues, metricas

        relationships = [
            Relationship(
                from_tabela="nfs_cabecalho",
                to_tabela="nfs_itens",
                chave=_COL_CHAVE,
            )
        ]

        self._validar_tabela(con, "nfs_cabecalho", issues, metricas)
        self._validar_tabela(con, "nfs_itens", issues, metricas)
        self._validar_duplicadas(con, "nfs_cabecalho", catalog, issues, metricas)
        self._validar_orfas(con, issues, metricas)
        self._validar_divergencia_chave(con, issues, metricas)
        self._validar_total_vs_itens(con, catalog, issues, metricas)
        self._validar_consistencia(con, catalog, issues, metricas)

        return relationships, issues, metricas

    def _validar_tabela(
        self,
        con: Any,
        tabela: str,
        issues: list[Issue],
        metricas: dict,
    ) -> None:
        total = con.execute(
            f'SELECT COUNT(*) FROM "curated"."{tabela}"'
        ).fetchone()[0]
        metricas[f"linhas_{tabela}"] = total

        vazias = con.execute(
            f'SELECT COUNT(*) FROM "curated"."{tabela}" '
            f'WHERE "{_COL_CHAVE}" IS NULL OR "{_COL_CHAVE}" = \'\''
        ).fetchone()[0]
        if vazias:
            issues.append(
                Issue(
                    severidade="blocking",
                    codigo="chave_vazia",
                    mensagem=f"{vazias} linha(s) com CHAVE DE ACESSO vazia em {tabela}.",
                    tabela=tabela,
                )
            )

        com_espacos = con.execute(
            f'SELECT COUNT(*) FROM "curated"."{tabela}" '
            f'WHERE "{_COL_CHAVE}_origem" LIKE \'% %\''
        ).fetchone()[0]
        if com_espacos:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="chave_com_espacos",
                    mensagem=f"{com_espacos} chave(s) com espacos em {tabela}.",
                    tabela=tabela,
                )
            )

        if self._rule.comprimento is not None:
            erradas = con.execute(
                f'SELECT COUNT(*) FROM "curated"."{tabela}" '
                f'WHERE LENGTH("{_COL_CHAVE}") <> {self._rule.comprimento}'
            ).fetchone()[0]
            if erradas:
                issues.append(
                    Issue(
                        severidade="warning",
                        codigo="chave_tamanho_incorreto",
                        mensagem=f"{erradas} chave(s) com tamanho diferente de "
                        f"{self._rule.comprimento} em {tabela}.",
                        tabela=tabela,
                    )
                )

        if self._rule.apenas_numeros:
            nao_numericas = con.execute(
                f'SELECT COUNT(*) FROM "curated"."{tabela}" '
                f'WHERE "{_COL_CHAVE}" ~ \'[^0-9]\''
            ).fetchone()[0]
            if nao_numericas:
                issues.append(
                    Issue(
                        severidade="warning",
                        codigo="chave_nao_numerica",
                        mensagem=f"{nao_numericas} chave(s) com caracteres nao "
                        f"numericos em {tabela}.",
                        tabela=tabela,
                    )
                )

    def _validar_duplicadas(
        self,
        con: Any,
        tabela: str,
        catalog: Catalog,
        issues: list[Issue],
        metricas: dict,
    ) -> None:
        dup = con.execute(
            f'SELECT COUNT(*) FROM (SELECT "{_COL_CHAVE}" FROM "curated"."{tabela}" '
            f'GROUP BY "{_COL_CHAVE}" HAVING COUNT(*) > 1) t'
        ).fetchone()[0]
        metricas[f"chaves_duplicadas_{tabela}"] = dup
        if not dup:
            return

        # Distingue duplicatas identicas (consolidaveis de forma deterministica)
        # de duplicatas divergentes (mesma chave com valores diferentes em alguma
        # coluna). Nao usamos MAX()/MIN() para esconder conflitos: divergencias
        # sao reportadas como alerta de qualidade.
        divergentes = self._contar_divergentes(con, tabela, catalog)
        metricas[f"chaves_duplicadas_divergentes_{tabela}"] = divergentes

        if divergentes:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="chave_duplicada_divergente",
                    mensagem=f"{divergentes} chave(s) duplicada(s) com valores "
                    f"divergentes em {tabela} (mesma chave, dados diferentes). "
                    "Revise os dados; nao consolidamos automaticamente conflitos.",
                    tabela=tabela,
                )
            )
        else:
            # Duplicatas identicas: mesma chave com todas as colunas iguais.
            issues.append(
                Issue(
                    severidade="info",
                    codigo="chave_duplicada_identica",
                    mensagem=f"{dup} chave(s) duplicada(s) identica(s) em {tabela} "
                    "(linhas repetidas com os mesmos dados; consolidadas na view "
                    "de resumo sem perda de informacao).",
                    tabela=tabela,
                )
            )

    def _contar_divergentes(
        self, con: Any, tabela: str, catalog: Catalog
    ) -> int:
        """Conta chaves duplicadas cujas linhas divergem em ao menos uma coluna."""
        t = catalog.tabela(tabela)
        if t is None:
            return 0
        colunas = [c.canonico for c in t.colunas if c.canonico != _COL_CHAVE]
        if not colunas:
            return 0
        comparacoes = " OR ".join(
            f'a."{c}" IS DISTINCT FROM b."{c}"' for c in colunas
        )
        return con.execute(
            f'SELECT COUNT(DISTINCT a."{_COL_CHAVE}") '
            f'FROM "curated"."{tabela}" a '
            f'JOIN "curated"."{tabela}" b '
            f'ON a."{_COL_CHAVE}" = b."{_COL_CHAVE}" '
            f'WHERE {comparacoes}'
        ).fetchone()[0]

    def _validar_orfas(self, con: Any, issues: list[Issue], metricas: dict) -> None:
        orfas = con.execute(
            'SELECT COUNT(*) FROM "curated"."nfs_itens" i '
            'LEFT JOIN "curated"."nfs_cabecalho" h '
            'ON i."chave_acesso" = h."chave_acesso" '
            'WHERE h."chave_acesso" IS NULL'
        ).fetchone()[0]
        metricas["itens_orfao"] = orfas
        total_itens = metricas.get("linhas_nfs_itens", 0) or 0
        metricas["pct_itens_orfao"] = round(orfas / total_itens * 100, 2) if total_itens else 0.0
        if orfas:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="item_orfao",
                    mensagem=f"{orfas} item(ns) sem cabecalho correspondente "
                    f"({metricas['pct_itens_orfao']}% dos itens).",
                    tabela="nfs_itens",
                )
            )

        sem_itens = con.execute(
            'SELECT COUNT(*) FROM "curated"."nfs_cabecalho" h '
            'LEFT JOIN "curated"."nfs_itens" i '
            'ON h."chave_acesso" = i."chave_acesso" '
            'WHERE i."chave_acesso" IS NULL'
        ).fetchone()[0]
        metricas["cabecalhos_sem_itens"] = sem_itens
        if sem_itens:
            issues.append(
                Issue(
                    severidade="info",
                    codigo="cabecalho_sem_itens",
                    mensagem=f"{sem_itens} cabecalho(s) sem itens correspondentes.",
                    tabela="nfs_cabecalho",
                )
            )

    def _validar_divergencia_chave(
        self, con: Any, issues: list[Issue], metricas: dict
    ) -> None:
        """Chave normalizada casa, mas o valor original diverge entre os arquivos."""
        divergentes = con.execute(
            'SELECT COUNT(*) FROM "curated"."nfs_cabecalho" h '
            'JOIN "curated"."nfs_itens" i '
            'ON h."chave_acesso" = i."chave_acesso" '
            'WHERE h."chave_acesso_origem" IS DISTINCT FROM i."chave_acesso_origem"'
        ).fetchone()[0]
        metricas["chave_divergente_origem"] = divergentes
        if divergentes:
            issues.append(
                Issue(
                    severidade="blocking",
                    codigo="chave_divergente",
                    mensagem=f"{divergentes} chave(s) com valor original divergente "
                    "entre cabecalho e itens (mesma chave normalizada).",
                )
            )

    def _validar_total_vs_itens(
        self, con: Any, catalog: Catalog, issues: list[Issue], metricas: dict
    ) -> None:
        """Compara o valor total da nota com a soma dos itens (aviso inicial)."""
        header = catalog.tabela("nfs_cabecalho")
        items = catalog.tabela("nfs_itens")
        if header is None or items is None:
            return
        col_cab = next(
            (c.canonico for c in header.colunas
             if c.agregavel and c.tipo in ("decimal", "numero") and "nota" in c.canonico),
            None,
        )
        col_item = next(
            (c.canonico for c in items.colunas
             if c.agregavel and c.tipo in ("decimal", "numero") and c.canonico == "valor_total"),
            None,
        )
        if col_cab is None or col_item is None:
            return
        divergentes = con.execute(
            f'SELECT COUNT(*) FROM ('
            f'SELECT h."{_COL_CHAVE}" FROM "curated"."nfs_cabecalho" h '
            f'JOIN (SELECT "{_COL_CHAVE}", SUM("{col_item}") AS s '
            f'FROM "curated"."nfs_itens" GROUP BY "{_COL_CHAVE}") i '
            f'ON h."{_COL_CHAVE}" = i."{_COL_CHAVE}" '
            f'WHERE ABS(h."{col_cab}" - i.s) > 0.01) t'
        ).fetchone()[0]
        metricas["total_nota_vs_itens_divergente"] = divergentes
        if divergentes:
            issues.append(
                Issue(
                    severidade="warning",
                    codigo="divergencia_total_itens",
                    mensagem=f"{divergentes} nota(s) em que o valor total diverge "
                    "da soma dos itens.",
                )
            )

    def _validar_consistencia(
        self,
        con: Any,
        catalog: Catalog,
        issues: list[Issue],
        metricas: dict,
    ) -> None:
        header = catalog.tabela("nfs_cabecalho")
        items = catalog.tabela("nfs_itens")
        cols_header = {c.canonico for c in header.colunas}
        cols_items = {c.canonico for c in items.colunas}
        compartilhadas = [
            c for c in _COLS_CONSISTENCIA if c in cols_header and c in cols_items
        ]
        for col in compartilhadas:
            divergentes = con.execute(
                f'SELECT COUNT(*) FROM ('
                f'SELECT h."{_COL_CHAVE}" FROM "curated"."nfs_cabecalho" h '
                f'JOIN "curated"."nfs_itens" i '
                f'ON h."{_COL_CHAVE}" = i."{_COL_CHAVE}" '
                f'WHERE h."{col}" IS DISTINCT FROM i."{col}") t'
            ).fetchone()[0]
            metricas[f"divergencia_{col}"] = divergentes
            if divergentes:
                issues.append(
                    Issue(
                        severidade="warning",
                        codigo="divergencia_cruzada",
                        mensagem=f"{divergentes} divergencia(s) no campo {col!r} "
                        "entre cabecalho e itens.",
                    )
                )

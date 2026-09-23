"""Views de granularidade segura na camada curated.

Cada view ja possui a granularidade correta, reduzindo a dependencia do LLM
para montar joins perigosos:
- `curated.v_nota_resumo`: uma linha por nota (cabecalho);
- `curated.v_item_resumo`: uma linha por item;
- `curated.v_nota_com_quantidade_itens`: itens agregados por nota, juntados ao
  cabecalho SEM duplicar o valor da nota;
- `curated.v_nota_com_itens`: mestre-detalhe — cada nota juntada aos seus itens
  (LEFT JOIN por chave_acesso), permitindo listar todos os itens de uma nota.
"""

from __future__ import annotations

from typing import Any

from app.catalog.catalog import Catalog


class ViewBuilder:
    """Cria as views de granularidade segura, quando as tabelas existirem."""

    def criar(self, con: Any, catalog: Catalog) -> None:
        header = catalog.tabela("nfs_cabecalho") is not None
        items = catalog.tabela("nfs_itens") is not None

        if header:
            con.execute(
                'CREATE OR REPLACE VIEW "curated"."v_nota_resumo" AS '
                'SELECT * FROM "curated"."nfs_cabecalho"'
            )
        if items:
            con.execute(
                'CREATE OR REPLACE VIEW "curated"."v_item_resumo" AS '
                'SELECT * FROM "curated"."nfs_itens"'
            )
        if header and items:
            con.execute(
                'CREATE OR REPLACE VIEW "curated"."v_nota_com_quantidade_itens" AS '
                'SELECT h.*, q.quantidade_itens FROM "curated"."nfs_cabecalho" h '
                'LEFT JOIN (SELECT "chave_acesso", COUNT(*) AS quantidade_itens '
                'FROM "curated"."nfs_itens" GROUP BY "chave_acesso") q '
                'ON h."chave_acesso" = q."chave_acesso"'
            )
            # Mestre-detalhe: nota + todos os seus itens (LEFT JOIN para exibir
            # a nota mesmo quando nao houver itens correspondentes).
            con.execute(
                'CREATE OR REPLACE VIEW "curated"."v_nota_com_itens" AS '
                'SELECT h.*, i.* FROM "curated"."nfs_cabecalho" h '
                'LEFT JOIN "curated"."nfs_itens" i '
                'ON h."chave_acesso" = i."chave_acesso"'
            )

"""Testes do RelationshipValidator (app/dataset/relationship_validator.py)."""

from app.catalog.catalog import Catalog, ColunaDict, DicionarioDados, TabelaDict
from app.dataset.relationship_validator import RelationshipValidator
from app.query.duckdb_client import DuckDBClient


def _catalog() -> Catalog:
    cab = TabelaDict(
        nome="nfs_cabecalho",
        fonte="nf_cabecalho.csv",
        colunas=[
            ColunaDict(origem="CHAVE DE ACESSO", canonico="chave_acesso",
                       tipo="identificador", regra_busca="exato"),
            ColunaDict(origem="RAZÃO SOCIAL EMITENTE", canonico="razao_social_emitente",
                       tipo="texto", regra_busca="exato"),
        ],
    )
    itens = TabelaDict(
        nome="nfs_itens",
        fonte="nf_itens.csv",
        colunas=[
            ColunaDict(origem="CHAVE DE ACESSO", canonico="chave_acesso",
                       tipo="identificador", regra_busca="exato"),
            ColunaDict(origem="RAZÃO SOCIAL EMITENTE", canonico="razao_social_emitente",
                       tipo="texto", regra_busca="exato"),
        ],
    )
    return Catalog(DicionarioDados(tabelas=[cab, itens]))


def _setup(client: DuckDBClient):
    client.con.execute("CREATE SCHEMA IF NOT EXISTS curated")
    client.con.execute(
        'CREATE TABLE "curated"."nfs_cabecalho" ('
        '"chave_acesso" VARCHAR, "chave_acesso_origem" VARCHAR, '
        '"razao_social_emitente" VARCHAR)'
    )
    client.con.execute(
        'CREATE TABLE "curated"."nfs_itens" ('
        '"chave_acesso" VARCHAR, "chave_acesso_origem" VARCHAR, '
        '"razao_social_emitente" VARCHAR)'
    )


def test_relacionamento_e_metricas_basicas():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('22222222222222222222222222222222222222222222','22222222222222222222222222222222222222222222','beta')"
        )
        client.con.execute(
            'INSERT INTO "curated"."nfs_itens" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('99999999999999999999999999999999999999999999','99999999999999999999999999999999999999999999','orfao')"
        )
        rels, issues, metricas = RelationshipValidator().validar(client.con, _catalog())
        assert len(rels) == 1
        assert rels[0].chave == "chave_acesso"
        assert metricas["linhas_nfs_cabecalho"] == 2
        assert metricas["linhas_nfs_itens"] == 3
        # item orfao (chave 999...) sem cabecalho
        assert metricas["itens_orfao"] == 1
        assert any(i.codigo == "item_orfao" for i in issues)
        # cabecalho 222... sem itens
        assert metricas["cabecalhos_sem_itens"] == 1
    finally:
        client.close()


def test_chave_vazia_e_bloqueante():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('', '', 'acme')"
        )
        _, issues, _ = RelationshipValidator().validar(client.con, _catalog())
        assert any(i.codigo == "chave_vazia" and i.severidade == "blocking" for i in issues)
    finally:
        client.close()


def test_chave_duplicada_identica_no_cabecalho():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme')"
        )
        _, issues, metricas = RelationshipValidator().validar(client.con, _catalog())
        assert metricas["chaves_duplicadas_nfs_cabecalho"] == 1
        assert metricas["chaves_duplicadas_divergentes_nfs_cabecalho"] == 0
        assert any(i.codigo == "chave_duplicada_identica" for i in issues)
    finally:
        client.close()


def test_chave_duplicada_divergente_no_cabecalho_gera_warning():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme industrial')"
        )
        _, issues, metricas = RelationshipValidator().validar(client.con, _catalog())
        assert metricas["chaves_duplicadas_nfs_cabecalho"] == 1
        assert metricas["chaves_duplicadas_divergentes_nfs_cabecalho"] == 1
        dup = next(i for i in issues if i.codigo == "chave_duplicada_divergente")
        assert dup.severidade == "warning"
    finally:
        client.close()


def test_divergencia_de_emitente_entre_arquivos_gera_warning():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme')"
        )
        client.con.execute(
            'INSERT INTO "curated"."nfs_itens" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme industrial')"
        )
        _, issues, metricas = RelationshipValidator().validar(client.con, _catalog())
        assert metricas["divergencia_razao_social_emitente"] == 1
        assert any(i.codigo == "divergencia_cruzada" for i in issues)
    finally:
        client.close()


def test_chave_duplicada_identica_e_info():
    client = DuckDBClient()
    try:
        _setup(client)
        client.con.execute(
            'INSERT INTO "curated"."nfs_cabecalho" VALUES '
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme'), "
            "('11111111111111111111111111111111111111111111','11111111111111111111111111111111111111111111','acme')"
        )
        _, issues, _ = RelationshipValidator().validar(client.con, _catalog())
        dup = next(i for i in issues if i.codigo == "chave_duplicada_identica")
        assert dup.severidade == "info"
    finally:
        client.close()

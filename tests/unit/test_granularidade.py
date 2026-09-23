"""Testes de granularidade: validacao deterministica e view segura sem duplicar."""

import io
import zipfile
from pathlib import Path

from app.agent.guardrails import validar_granularidade
from app.catalog.catalog import Catalog, ColunaDict, DicionarioDados, TabelaDict
from app.dataset.builder import DatasetBuilder

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _catalog() -> Catalog:
    cab = TabelaDict(
        nome="nfs_cabecalho",
        fonte="nf_cabecalho.csv",
        granularidade="nota",
        colunas=[
            ColunaDict(origem="CHAVE DE ACESSO", canonico="chave_acesso",
                       tipo="identificador", regra_busca="exato"),
            ColunaDict(origem="VALOR NOTA FISCAL", canonico="valor_nota_fiscal",
                       tipo="decimal", regra_busca="nenhum", agregavel=True),
        ],
    )
    itens = TabelaDict(
        nome="nfs_itens",
        fonte="nf_itens.csv",
        granularidade="item",
        colunas=[
            ColunaDict(origem="CHAVE DE ACESSO", canonico="chave_acesso",
                       tipo="identificador", regra_busca="exato"),
            ColunaDict(origem="VALOR TOTAL", canonico="valor_total",
                       tipo="decimal", regra_busca="nenhum", agregavel=True),
        ],
    )
    return Catalog(DicionarioDados(tabelas=[cab, itens]))


def test_bloqueia_soma_de_valor_do_cabecalho_apos_join():
    sql = (
        "SELECT c.razao_social_emitente, SUM(c.valor_nota_fiscal) "
        "FROM curated.nfs_cabecalho c JOIN curated.nfs_itens i "
        "ON c.chave_acesso = i.chave_acesso GROUP BY c.razao_social_emitente"
    )
    v = validar_granularidade(sql, _catalog())
    assert not v.ok
    assert "duplicaria" in v.motivo


def test_bloqueia_soma_com_identificador_entre_aspas():
    sql = (
        "SELECT SUM(c.\"valor_nota_fiscal\") "
        "FROM curated.nfs_cabecalho c JOIN curated.nfs_itens i "
        "ON c.chave_acesso = i.chave_acesso"
    )
    assert not validar_granularidade(sql, _catalog()).ok


def test_permite_soma_de_valor_de_item_apos_join():
    sql = (
        "SELECT c.razao_social_emitente, SUM(i.valor_total) "
        "FROM curated.nfs_cabecalho c JOIN curated.nfs_itens i "
        "ON c.chave_acesso = i.chave_acesso GROUP BY c.razao_social_emitente"
    )
    assert validar_granularidade(sql, _catalog()).ok


def test_permite_soma_de_valor_do_cabecalho_sem_join():
    sql = "SELECT SUM(valor_nota_fiscal) FROM curated.nfs_cabecalho"
    assert validar_granularidade(sql, _catalog()).ok


def test_bloqueia_count_asterisco_apos_join_sem_group_by():
    # COUNT(*) apos JOIN com itens conta itens, nao notas: uma nota com N itens
    # aparece N vezes no resultado do join. So bloqueia sem GROUP BY.
    sql = (
        "SELECT COUNT(*) FROM curated.nfs_cabecalho c "
        "JOIN curated.nfs_itens i ON c.chave_acesso = i.chave_acesso"
    )
    v = validar_granularidade(sql, _catalog())
    assert not v.ok
    assert "itens, nao notas" in v.motivo
    assert "COUNT(DISTINCT" in v.motivo


def test_permite_count_asterisco_apos_join_com_group_by():
    # Com GROUP BY por chave, COUNT(*) conta itens POR nota (legitimo).
    sql = (
        "SELECT c.chave_acesso, COUNT(*) FROM curated.nfs_cabecalho c "
        "JOIN curated.nfs_itens i ON c.chave_acesso = i.chave_acesso "
        "GROUP BY c.chave_acesso"
    )
    assert validar_granularidade(sql, _catalog()).ok


def test_permite_count_asterisco_sem_join():
    sql = "SELECT COUNT(*) FROM curated.nfs_itens"
    assert validar_granularidade(sql, _catalog()).ok


def _zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(FIXTURES / "nf_amostra.csv", "nf_cabecalho.csv")
        z.write(FIXTURES / "nf_itens_amostra.csv", "nf_itens.csv")
    buf.seek(0)
    return buf


def _pipeline_fake(client, catalog, tools, dataset_id):
    class _Pipeline:
        pass

    p = _Pipeline()
    p.dataset_id = dataset_id
    return p


def test_view_segura_nao_duplica_valor_da_nota():
    resultado = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    assert resultado.ok
    ctx = resultado.dataset
    # Soma do valor da nota via view segura == soma direta no cabecalho.
    via_view = ctx.client.con.execute(
        'SELECT SUM(valor_nota_fiscal) FROM "curated"."v_nota_com_quantidade_itens"'
    ).fetchone()[0]
    direto = ctx.client.con.execute(
        'SELECT SUM(valor_nota_fiscal) FROM "curated"."nfs_cabecalho"'
    ).fetchone()[0]
    assert via_view == direto
    # A view traz a quantidade de itens por nota.
    qtd = ctx.client.con.execute(
        'SELECT quantidade_itens FROM "curated"."v_nota_com_quantidade_itens" '
        'WHERE chave_acesso = \'35250612345678000190000010000000011234567890\''
    ).fetchone()[0]
    assert qtd == 2
    ctx.client.close()

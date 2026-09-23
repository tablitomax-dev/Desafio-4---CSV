"""Testes do DatasetBuilder (app/dataset/builder.py) — fluxo completo com pipeline mock."""

import io
import zipfile
from pathlib import Path

import pytest

from app.dataset.builder import DatasetBuilder
from app.dataset.dataset_publisher import DatasetPublisher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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


def test_construir_dataset_ok_com_cabecalho_e_itens():
    builder = DatasetBuilder(pipeline_factory=_pipeline_fake)
    resultado = builder.construir(_zip())
    assert resultado.ok
    ctx = resultado.dataset
    assert ctx.status == "ready"
    assert ctx.consistente()
    assert ctx.catalog.dataset_id == ctx.dataset_id
    assert len(ctx.catalog.relationships) == 1
    # schemas criados
    schemas = {r[0] for r in ctx.client.con.execute(
        "SELECT schema_name FROM information_schema.schemata").fetchall()}
    assert {"staging", "curated", "meta"} <= schemas
    # tabelas curated existem
    n = ctx.client.con.execute(
        'SELECT COUNT(*) FROM "curated"."nfs_cabecalho"').fetchone()[0]
    assert n == 15
    # views de granularidade criadas e consultaveis
    n = ctx.client.con.execute(
        'SELECT COUNT(*) FROM "curated"."v_nota_com_quantidade_itens"').fetchone()[0]
    assert n == 15
    ctx.client.close()


def test_construir_dataset_gera_metricas_de_qualidade():
    builder = DatasetBuilder(pipeline_factory=_pipeline_fake)
    resultado = builder.construir(_zip())
    assert resultado.ok
    assert resultado.metricas["linhas_nfs_cabecalho"] == 15
    assert resultado.metricas["linhas_nfs_itens"] == 3
    resultado.dataset.client.close()


def test_construir_dataset_falha_sem_csv():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notas.json", "{}")
    buf.seek(0)
    resultado = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(buf)
    assert not resultado.ok
    assert resultado.errors


def test_dois_uploads_nao_compartilham_tabelas():
    a = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    b = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    assert a.ok and b.ok
    # Conexoes distintas: o dataset A continua consultavel apos criar o B.
    n = a.dataset.client.con.execute(
        'SELECT COUNT(*) FROM "curated"."nfs_cabecalho"').fetchone()[0]
    assert n == 15
    assert a.dataset.client is not b.dataset.client
    a.dataset.client.close()
    b.dataset.client.close()


def test_falha_no_novo_upload_nao_destroi_anterior():
    ok = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    assert ok.ok
    # Upload seguinte falha (ZIP sem CSV).
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notas.json", "{}")
    buf.seek(0)
    falho = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(buf)
    assert not falho.ok
    # O dataset anterior permanece consultavel.
    n = ok.dataset.client.con.execute(
        'SELECT COUNT(*) FROM "curated"."nfs_cabecalho"').fetchone()[0]
    assert n == 15
    ok.dataset.client.close()


def test_apenas_cabecalho_gera_warning_mas_publica():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(FIXTURES / "nf_amostra.csv", "nf_cabecalho.csv")
    buf.seek(0)
    resultado = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(buf)
    assert resultado.ok
    assert any(i.codigo == "sem_itens" for i in resultado.warnings)
    resultado.dataset.client.close()


def test_zip_reader_preserva_nomes_duplicados():
    from app.dataset.zip_reader import ZipReader

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("nf_cabecalho.csv", b"a")
        z.writestr("nf_cabecalho.csv", b"b")
    buf.seek(0)
    arquivos = ZipReader().ler(buf)
    assert len(arquivos) == 2
    assert [c for _, c in arquivos] == [b"a", b"b"]


def test_trocar_ativo_fecha_conexao_anterior():
    a = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    b = DatasetBuilder(pipeline_factory=_pipeline_fake).construir(_zip())
    assert a.ok and b.ok
    novo = DatasetPublisher().trocar_ativo(a.dataset, b.dataset)
    assert novo is b.dataset
    # A conexao do dataset anterior foi fechada apos a troca.
    with pytest.raises(Exception):
        a.dataset.client.con.execute("SELECT 1")
    b.dataset.client.close()


def test_limite_de_linhas_rejeita_dataset_sem_publicar():
    builder = DatasetBuilder(pipeline_factory=_pipeline_fake, max_linhas=5)
    resultado = builder.construir(_zip())
    assert not resultado.ok
    assert any(i.codigo == "erro_ingestao" for i in resultado.errors)

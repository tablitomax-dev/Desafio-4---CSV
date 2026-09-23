"""Testes do contrato de estado (app/dataset/context.py)."""

from app.dataset.context import DatasetBuildResult, DatasetContext
from app.contracts import Issue, QualityReport


def _contexto(dataset_id="abc", catalog_id="abc", tools_id="abc", pipeline_id="abc",
              client_id="abc"):
    class _Client:
        dataset_id = client_id

    class _Catalog:
        dataset_id = catalog_id

    class _Tools:
        dataset_id = tools_id

    class _Pipeline:
        dataset_id = pipeline_id

    return DatasetContext(
        dataset_id=dataset_id,
        content_fingerprint="fp",
        client=_Client(),
        catalog=_Catalog(),
        tools=_Tools(),
        pipeline=_Pipeline(),
        quality=QualityReport(),
    )


def test_contexto_consistente_quando_todos_iguais():
    assert _contexto().consistente()


def test_contexto_inconsistente_quando_catalog_diverge():
    assert not _contexto(catalog_id="outro").consistente()


def test_contexto_inconsistente_quando_pipeline_diverge():
    assert not _contexto(pipeline_id="outro").consistente()


def test_build_result_ok_apenas_com_dataset():
    assert not DatasetBuildResult().ok
    assert DatasetBuildResult(status="ok", dataset=object()).ok


def test_quality_report_separa_severidades():
    report = QualityReport(
        issues=[
            Issue(severidade="blocking", codigo="a", mensagem="x"),
            Issue(severidade="warning", codigo="b", mensagem="y"),
            Issue(severidade="info", codigo="c", mensagem="z"),
        ]
    )
    assert len(report.bloqueantes) == 1
    assert len(report.warnings) == 1
    assert len(report.infos) == 1

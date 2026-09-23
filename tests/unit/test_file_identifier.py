"""Testes do FileIdentifier (app/dataset/file_identifier.py)."""

import pandas as pd

from app.dataset.file_identifier import FileIdentifier


def _df(colunas):
    return pd.DataFrame({c: [] for c in colunas})


COL_CAB = ["CHAVE DE ACESSO", "RAZÃO SOCIAL EMITENTE", "VALOR NOTA FISCAL"]
COL_IT = ["CHAVE DE ACESSO", "NÚMERO PRODUTO", "DESCRIÇÃO DO PRODUTO/SERVIÇO", "VALOR TOTAL"]


def test_classifica_cabecalho_por_colunas():
    classificados, issues = FileIdentifier().classificar([("arquivo1.csv", _df(COL_CAB))])
    assert classificados[0].papel == "cabecalho"
    assert classificados[0].nome_canonico == "nfs_cabecalho"
    assert not any(i.severidade == "blocking" for i in issues)


def test_classifica_itens_por_colunas():
    classificados, issues = FileIdentifier().classificar([("arquivo2.csv", _df(COL_IT))])
    assert classificados[0].papel == "itens"
    assert classificados[0].nome_canonico == "nfs_itens"


def test_classifica_por_nome_mesmo_sem_assinatura():
    df = _df(["CHAVE DE ACESSO", "X"])
    classificados, _ = FileIdentifier().classificar([("nf_cabecalho.csv", df)])
    assert classificados[0].papel == "cabecalho"


def test_arquivo_desconhecido_gera_bloqueante():
    df = _df(["A", "B"])
    classificados, issues = FileIdentifier().classificar([("dados.csv", df)])
    assert classificados[0].papel == "desconhecido"
    assert any(i.codigo == "arquivo_nao_classificado" and i.severidade == "blocking"
               for i in issues)


def test_dois_cabecalhos_gera_ambiguidade():
    classificados, issues = FileIdentifier().classificar(
        [("a.csv", _df(COL_CAB)), ("b.csv", _df(COL_CAB))]
    )
    assert any(i.codigo == "ambiguidade_papel" and i.severidade == "blocking"
               for i in issues)


def test_chave_ausente_gera_bloqueante():
    df = _df(["RAZÃO SOCIAL EMITENTE", "VALOR NOTA FISCAL"])
    _, issues = FileIdentifier().classificar([("nf_cabecalho.csv", df)])
    assert any(i.codigo == "chave_ausente" and i.severidade == "blocking" for i in issues)


def test_apenas_cabecalho_gera_warning_sem_itens():
    _, issues = FileIdentifier().classificar([("nf_cabecalho.csv", _df(COL_CAB))])
    assert any(i.codigo == "sem_itens" and i.severidade == "warning" for i in issues)

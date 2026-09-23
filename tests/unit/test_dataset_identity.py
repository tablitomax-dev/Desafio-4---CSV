"""Testes de identidade do dataset (app/dataset/identity.py)."""

from app.dataset.identity import calcular_content_fingerprint, gerar_dataset_id


def test_fingerprint_deterministico_para_mesmo_conteudo():
    a = [("nf_cabecalho.csv", b"abc"), ("nf_itens.csv", b"def")]
    b = [("nf_itens.csv", b"def"), ("nf_cabecalho.csv", b"abc")]
    assert calcular_content_fingerprint(a) == calcular_content_fingerprint(b)


def test_fingerprint_difere_para_conteudo_diferente():
    a = [("nf_cabecalho.csv", b"abc")]
    b = [("nf_cabecalho.csv", b"abd")]
    assert calcular_content_fingerprint(a) != calcular_content_fingerprint(b)


def test_fingerprint_ignora_ordem_e_normaliza_nome():
    a = [("NF_CABECALHO.CSV", b"abc")]
    b = [("nf_cabecalho.csv", b"abc")]
    assert calcular_content_fingerprint(a) == calcular_content_fingerprint(b)


def test_dataset_id_e_unico():
    assert gerar_dataset_id() != gerar_dataset_id()

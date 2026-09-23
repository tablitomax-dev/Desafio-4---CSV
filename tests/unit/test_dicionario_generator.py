"""Testes do gerador automatico de dicionario (app/ingestion/dicionario_generator.py).

O usuario envia apenas CSVs; este modulo infere tabelas, colunas (snake_case),
tipos e regras de forma conservadora (fuzzy proibido em chaves/identificadores).
"""

import pandas as pd

from app.ingestion.dicionario_generator import _inferir, _snake, gerar_dicionario, gerar_tabela


def _df(colunas: dict) -> pd.DataFrame:
    return pd.DataFrame(colunas)


def test_snake_normaliza_acentos_e_espacos():
    assert _snake("CHAVE DE ACESSO") == "chave_de_acesso"
    assert _snake("RAZÃO SOCIAL EMITENTE") == "razao_social_emitente"
    assert _snake("VALOR NOTA FISCAL") == "valor_nota_fiscal"
    assert _snake("DATA/HORA EVENTO MAIS RECENTE") == "data_hora_evento_mais_recente"


def test_snake_nao_comeca_com_digito():
    # Identificador SQL nao pode comecar com digito sem aspas.
    assert _snake("202401_NFS_CABECALHO") == "_202401_nfs_cabecalho"
    assert _snake("2024 VALOR") == "_2024_valor"
    assert not _snake("202401_NFS_CABECALHO")[0].isdigit()


def test_identificador_forca_busca_exata_sem_fuzzy():
    coluna = _inferir("CHAVE DE ACESSO", "chave_de_acesso", _df({"x": ["A", "B"]})["x"])
    assert coluna.tipo == "identificador"
    assert coluna.regra_busca == "exato"
    assert coluna.fuzzy_permitido is False


def test_cnpj_e_numero_sao_identificadores_exatos():
    for origem, canonico in (("CNPJ DESTINATÁRIO", "cnpj_destinatario"), ("NÚMERO", "numero")):
        coluna = _inferir(origem, canonico, _df({"x": ["1", "2"]})["x"])
        assert coluna.tipo == "identificador"
        assert coluna.regra_busca == "exato"


def test_data_reconhecida_pelo_nome_e_conteudo():
    df = _df({"DATA EMISSÃO": ["02/01/2025", "03/01/2025"]})
    coluna = _inferir("DATA EMISSÃO", "data_emissao", df["DATA EMISSÃO"])
    assert coluna.tipo == "data"
    assert coluna.regra_parse == "dd/mm/yyyy"
    assert coluna.agregavel is True


def test_decimal_reconhecido_e_nao_buscavel():
    df = _df({"VALOR NOTA FISCAL": ["1.234,56", "9.000,00"]})
    coluna = _inferir("VALOR NOTA FISCAL", "valor_nota_fiscal", df["VALOR NOTA FISCAL"])
    assert coluna.tipo == "decimal"
    assert coluna.regra_busca == "nenhum"
    assert coluna.agregavel is True


def test_descritiva_permite_fuzzy_controlado():
    coluna = _inferir("RAZÃO SOCIAL EMITENTE", "razao_social_emitente", _df({"x": ["a"]})["x"])
    assert coluna.tipo == "texto"
    assert coluna.fuzzy_permitido is True
    assert coluna.regra_busca == "fuzzy_controlado"


def test_coluna_sem_pista_e_texto_exato():
    coluna = _inferir("INFORMAÇÕES GERAIS", "informacoes_gerais", _df({"x": ["a"]})["x"])
    assert coluna.tipo == "texto"
    assert coluna.regra_busca == "exato"


def test_gerar_tabela_usa_stem_do_nome_do_csv():
    df = _df({"RAZÃO SOCIAL EMITENTE": ["Acme"]})
    tabela = gerar_tabela("nf_cabecalho.csv", df)
    assert tabela.nome == "nf_cabecalho"
    assert tabela.fonte == "nf_cabecalho"
    assert [c.canonico for c in tabela.colunas] == ["razao_social_emitente"]


def test_gerar_dicionario_agrupa_tabelas():
    df = _df({"CNPJ DESTINATÁRIO": ["1"], "VALOR NOTA FISCAL": ["1,5"]})
    dic = gerar_dicionario([("nf_cabecalho.csv", df), ("nf_itens.csv", df)])
    assert [t.nome for t in dic.tabelas] == ["nf_cabecalho", "nf_itens"]


def test_tipo_de_produto_e_categoria_agrupavel_nao_identificador():
    # "NCM/SH (TIPO DE PRODUTO)" descreve a categoria do produto (texto legivel,
    # ex.: "Outros livros, brochuras..."). Apesar do token "ncm", o significado
    # dominante e "tipo" (categoria) — agrupar deve ser permitido.
    df = _df({"NCM/SH (TIPO DE PRODUTO)": ["Outros livros", "Peças de reposição"]})
    coluna = _inferir("NCM/SH (TIPO DE PRODUTO)", "ncm_sh_tipo_de_produto", df["NCM/SH (TIPO DE PRODUTO)"])
    assert coluna.tipo == "categoria"
    assert coluna.regra_busca == "exato"
    assert coluna.agregavel is True
    assert coluna.fuzzy_permitido is False


def test_codigo_ncm_sh_continua_identificador():
    # O codigo numerico do NCM (ex.: 49019900) e identificador; o token "codigo"
    # mantem a classificacao conservadora mesmo com "ncm".
    df = _df({"CÓDIGO NCM/SH": ["49019900", "85122021"]})
    coluna = _inferir("CÓDIGO NCM/SH", "codigo_ncm_sh", df["CÓDIGO NCM/SH"])
    assert coluna.tipo == "identificador"
    assert coluna.regra_busca == "exato"
    assert coluna.fuzzy_permitido is False

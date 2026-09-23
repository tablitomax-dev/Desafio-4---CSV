"""Testes do catalogo de dados (app/catalog/catalog.py)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.catalog import Catalog, DicionarioDados

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _catalog() -> Catalog:
    return Catalog.carregar(FIXTURES / "dicionario.json")


def test_carregar_dicionario_da_fixture():
    cat = _catalog()
    assert len(cat.tabelas) == 2
    assert {t.nome for t in cat.tabelas} == {"notas_fiscais", "notas_fiscais_itens"}


def test_tabela_itens_tem_colunas_de_item():
    cat = _catalog()
    col = cat.coluna_por_canonico("notas_fiscais_itens", "valor_total")
    assert col is not None
    assert col.tipo == "decimal"
    assert col.agregavel is True


def test_coluna_carrega_campos():
    cat = _catalog()
    col = cat.tabela("notas_fiscais").colunas[0]
    assert col.canonico == "chave_acesso"
    assert col.tipo == "identificador"
    assert col.fuzzy_permitido is False
    assert col.regra_busca == "exato"


def test_coluna_textual_fuzzy_permitido():
    cat = _catalog()
    col = cat.coluna_por_canonico("notas_fiscais", "razao_social_emitente")
    assert col is not None
    assert col.fuzzy_permitido is True
    assert col.regra_busca == "fuzzy_controlado"


def test_coluna_por_canonico_inexistente():
    cat = _catalog()
    assert cat.coluna_por_canonico("notas_fiscais", "nao_existe") is None


def test_rejeita_regra_busca_invalida():
    data = {
        "tabelas": [
            {
                "nome": "t",
                "fonte": "f.csv",
                "colunas": [
                    {"origem": "X", "canonico": "x", "tipo": "texto", "regra_busca": "aleatorio"}
                ],
            }
        ]
    }
    with pytest.raises(ValidationError):
        DicionarioDados.model_validate(data)

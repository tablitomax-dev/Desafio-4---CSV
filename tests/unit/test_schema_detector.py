"""Testes do detector de schema (app/ingestion/schema_detector.py)."""

from pathlib import Path

from app.catalog.catalog import Catalog
from app.ingestion.schema_detector import detectar_tabela

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _catalog() -> Catalog:
    return Catalog.carregar(FIXTURES / "dicionario.json")


def test_detecta_tabela_pelos_cabecalhos():
    cat = _catalog()
    headers = ["RAZÃO SOCIAL EMITENTE", "CNPJ DESTINATÁRIO", "VALOR NOTA FISCAL", "DATA EMISSÃO"]
    t = detectar_tabela(cat, headers)
    assert t is not None
    assert t.nome == "notas_fiscais"


def test_detecta_tabela_itens():
    cat = _catalog()
    headers = [
        "RAZÃO SOCIAL EMITENTE",
        "CNPJ DESTINATÁRIO",
        "NÚMERO PRODUTO",
        "DESCRIÇÃO DO PRODUTO/SERVIÇO",
        "CFOP",
        "VALOR TOTAL",
    ]
    t = detectar_tabela(cat, headers)
    assert t is not None
    assert t.nome == "notas_fiscais_itens"


def test_nao_detecta_sem_correspondencia():
    cat = _catalog()
    assert detectar_tabela(cat, ["COLUNA X", "OUTRA COISA"]) is None

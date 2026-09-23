"""Testes da normalizacao deterministica (app/ingestion/normalizer.py)."""

from app.catalog.catalog import ColunaDict
from app.ingestion.normalizer import (
    normalizar_data,
    normalizar_decimal,
    normalizar_texto,
    normalizar_valor,
)


def test_normalizar_texto_remove_acento_caixa_e_trim():
    assert normalizar_texto("  Acme Industrial LTDA  ") == "acme industrial ltda"
    assert normalizar_texto("SÃO PAULO") == "sao paulo"


def test_normalizar_data_dd_mm_aaaa():
    assert normalizar_data("02/01/2025") == "2025-01-02"


def test_normalizar_data_iso_preservada():
    assert normalizar_data("2025-01-02") == "2025-01-02"


def test_normalizar_data_invalida_retorna_none():
    assert normalizar_data("não-data") is None


def test_normalizar_decimal_br():
    assert normalizar_decimal("1.234,56") == 1234.56


def test_normalizar_decimal_ponto_decimal():
    # Formato US/ISO (ponto como separador decimal), usado nos CSVs de NFs.
    assert normalizar_decimal("522.5") == 522.5
    assert normalizar_decimal("6712.16") == 6712.16
    assert normalizar_decimal("499.0") == 499.0


def test_normalizar_decimal_misto_us():
    # Virgula como milhar e ponto como decimal (formato US com milhar).
    assert normalizar_decimal("1,234.56") == 1234.56


def test_normalizar_decimal_milhar_sem_decimal():
    # Ponto como milhar, sem parte decimal (formato BR).
    assert normalizar_decimal("1.234") == 1234
    assert normalizar_decimal("1.234.567") == 1234567


def test_normalizar_decimal_virgula_decimal_br():
    assert normalizar_decimal("1234,56") == 1234.56


def test_normalizar_valor_despacha_por_tipo_decimal():
    col = ColunaDict(origem="VALOR", canonico="v", tipo="decimal", regra_parse="decimal_br")
    assert normalizar_valor("1.234,56", col) == 1234.56


def test_normalizar_valor_despacha_por_tipo_data():
    col = ColunaDict(origem="DATA", canonico="d", tipo="data", regra_parse="dd/mm/yyyy")
    assert normalizar_valor("02/01/2025", col) == "2025-01-02"


def test_normalizar_valor_nan_retorna_none():
    col = ColunaDict(origem="X", canonico="x", tipo="texto")
    assert normalizar_valor(None, col) is None

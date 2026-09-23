"""Testes da extracao segura de ZIP (app/ingestion/zip_processor.py)."""

import io
import zipfile

import pytest

from app.ingestion.zip_processor import extrair_zip


def _zip(files: list[tuple[str, str]]) -> io.BytesIO:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, content in files:
            z.writestr(name, content)
    b.seek(0)
    return b


def test_extrai_csv_e_json():
    buf = _zip([("a.csv", "x"), ("dic.json", "{}")])
    saida = extrair_zip(buf)
    assert set(saida) == {"a.csv", "dic.json"}


def test_rejeita_zip_slip():
    buf = _zip([("../escape.csv", "x")])
    with pytest.raises(ValueError):
        extrair_zip(buf)


def test_rejeita_extensao_invalida():
    buf = _zip([("mal.exe", "x")])
    with pytest.raises(ValueError):
        extrair_zip(buf)


def test_rejeita_zip_vazio():
    buf = _zip([])
    with pytest.raises(ValueError):
        extrair_zip(buf)

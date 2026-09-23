"""Leitura de CSV como texto (dtype str), com deteccao de encoding/delimitador."""

from __future__ import annotations

import io

import pandas as pd


def _detectar_encoding(buf: io.BytesIO) -> str:
    raw = buf.read()
    buf.seek(0)
    try:
        raw.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


class CsvReader:
    """Le um CSV mantendo os valores como texto (sem inferencia de tipos)."""

    def ler(self, buf: io.BytesIO) -> pd.DataFrame:
        enc = _detectar_encoding(buf)
        return pd.read_csv(buf, sep=None, engine="python", encoding=enc, dtype=str)

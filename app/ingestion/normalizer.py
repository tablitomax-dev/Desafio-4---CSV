"""Normalizacao deterministica de dados sujos (texto, data e numero)."""

from __future__ import annotations

import math
import unicodedata
from datetime import datetime
from typing import Any

from app.catalog.catalog import ColunaDict
from app.catalog.rules import normalizacao_para

_FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S")


def normalizar_texto(valor: Any) -> str:
    """Remove acentos (NFD), caixa baixa, trim e colapsa espacos."""
    s = str(valor)
    decomposto = unicodedata.normalize("NFD", s)
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.lower().split())


def normalizar_decimal(valor: Any) -> float | None:
    """Converte decimal para float, suportando formatos BR (1.234,56) e US/ISO (1234.56).

    Heuristica: quando ha ponto e virgula, o ultimo separador e o decimal. Quando ha
    apenas um tipo de separador, ele e tratado como decimal se houver 1-2 digitos apos
    a ultima ocorrencia; caso contrario, como separador de milhar.
    """
    s = str(valor).strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    tem_ponto = "." in s
    tem_virgula = "," in s
    if tem_ponto and tem_virgula:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tem_virgula:
        _, _, dec = s.partition(",")
        if 0 < len(dec) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tem_ponto:
        _, _, dec = s.rpartition(".")
        if not (0 < len(dec) <= 2):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def normalizar_data(valor: Any) -> str | None:
    """Converte datas BR (dd/mm/aaaa) e ISO para formato ISO (aaaa-mm-dd)."""
    s = str(valor).strip()
    if not s:
        return None
    for fmt in _FORMATOS_DATA:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _vazio(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    return str(valor).strip().lower() in {"", "nan", "none", "null"}


def normalizar_valor(valor: Any, coluna: ColunaDict) -> Any:
    """Normaliza um valor conforme a estrategia de tipo da coluna."""
    if _vazio(valor):
        return None
    estrategia = normalizacao_para(coluna)
    if estrategia == "numerico":
        return normalizar_decimal(valor)
    if estrategia == "data":
        return normalizar_data(valor)
    if estrategia == "identificador":
        s = str(valor).strip()
        return s if s else None
    return normalizar_texto(valor)

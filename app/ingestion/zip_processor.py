"""Extracao segura de arquivos de um ZIP (contra zip-slip, tamanho e extensoes)."""

from __future__ import annotations

import io
import posixpath
import zipfile

_EXTENSOES = frozenset({".csv", ".json"})
_MAX_TAMANHO_TOTAL = 500 * 1024 * 1024  # 500 MB
_MAX_ARQUIVOS = 50


def _sanitizar(nome: str) -> str:
    """Normaliza o caminho do membro e rejeita tentativa de zip-slip."""
    limpo = posixpath.normpath(nome.replace("\\", "/"))
    partes = limpo.split("/")
    if ".." in partes or limpo.startswith("/"):
        raise ValueError(f"Caminho invalido no ZIP: {nome}")
    return limpo


def extrair_zip(zip_bytes: io.BytesIO) -> dict[str, io.BytesIO]:
    """Extrai arquivos .csv e .json de um ZIP com validacoes de seguranca."""
    resultado: dict[str, io.BytesIO] = {}
    with zipfile.ZipFile(zip_bytes) as arquivo:
        nomes = arquivo.namelist()
        if not nomes:
            raise ValueError("ZIP vazio.")
        if len(nomes) > _MAX_ARQUIVOS:
            raise ValueError(f"ZIP com mais de {_MAX_ARQUIVOS} arquivos.")
        total = 0
        for info in arquivo.infolist():
            if info.is_dir():
                continue
            nome = _sanitizar(info.filename)
            ext = posixpath.splitext(nome)[1].lower()
            if ext not in _EXTENSOES:
                raise ValueError(f"Extensao nao permitida no ZIP: {nome}")
            total += info.file_size
            if total > _MAX_TAMANHO_TOTAL:
                raise ValueError("ZIP excede o tamanho maximo permitido.")
            resultado[nome] = io.BytesIO(arquivo.read(info))
    return resultado

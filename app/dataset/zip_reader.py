"""Leitura segura de um ZIP, preservando nomes duplicados (lista, nao dict).

O `extrair_zip` original retornava um dict indexado pelo nome, o que fazia dois
arquivos com o mesmo nome se sobrescreverem. Aqui retornamos uma lista de
(nome, bytes) para tratar duplicados explicitamente.
"""

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


class ZipReader:
    """Extrai arquivos .csv/.json de um ZIP com validacoes de seguranca."""

    def __init__(
        self,
        max_tamanho_total: int = _MAX_TAMANHO_TOTAL,
        max_arquivos: int = _MAX_ARQUIVOS,
    ) -> None:
        self._max_tamanho_total = max_tamanho_total
        self._max_arquivos = max_arquivos

    def ler(self, zip_bytes: io.BytesIO) -> list[tuple[str, bytes]]:
        """Retorna lista de (nome, bytes) preservando nomes duplicados."""
        resultado: list[tuple[str, bytes]] = []
        with zipfile.ZipFile(zip_bytes) as arquivo:
            nomes = arquivo.namelist()
            if not nomes:
                raise ValueError("ZIP vazio.")
            if len(nomes) > self._max_arquivos:
                raise ValueError(f"ZIP com mais de {self._max_arquivos} arquivos.")
            total = 0
            for info in arquivo.infolist():
                if info.is_dir():
                    continue
                nome = _sanitizar(info.filename)
                ext = posixpath.splitext(nome)[1].lower()
                if ext not in _EXTENSOES:
                    raise ValueError(f"Extensao nao permitida no ZIP: {nome}")
                total += info.file_size
                if total > self._max_tamanho_total:
                    raise ValueError("ZIP excede o tamanho maximo permitido.")
                resultado.append((nome, arquivo.read(info)))
        return resultado

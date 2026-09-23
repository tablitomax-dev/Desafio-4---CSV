"""Identidade do dataset: dataset_id (carga/sessao) e content_fingerprint canonico.

`dataset_id` identifica a carga/sessao (ex.: uuid). `content_fingerprint` e um
hash canonico do CONTEUDO, calculado a partir de um manifesto deterministico
(nome normalizado + tamanho + hash do conteudo de cada arquivo, ordenado
lexicograficamente). Assim, dois ZIPs com os mesmos CSVs (mesmo que com ordem,
compressao ou timestamps diferentes) produzem o mesmo fingerprint.
"""

from __future__ import annotations

import hashlib
import posixpath
import uuid


def _normalizar_nome(nome: str) -> str:
    """Normaliza o nome do arquivo para o manifesto (caminho posix, minusculas)."""
    return posixpath.normpath(nome.replace("\\", "/")).lower()


def calcular_content_fingerprint(arquivos: list[tuple[str, bytes]]) -> str:
    """Calcula o hash canonico do conteudo a partir de uma lista (nome, bytes).

    O manifesto e deterministico: cada entrada e `nome|tamanho|sha256`, e as
    entradas sao ordenadas lexicograficamente pelo nome normalizado.
    """
    manifesto: list[str] = []
    for nome, conteudo in arquivos:
        nome_norm = _normalizar_nome(nome)
        digest = hashlib.sha256(conteudo).hexdigest()
        manifesto.append(f"{nome_norm}|{len(conteudo)}|{digest}")
    manifesto.sort()
    bloco = "\n".join(manifesto).encode("utf-8")
    return hashlib.sha256(bloco).hexdigest()


def gerar_dataset_id() -> str:
    """Gera um identificador unico de carga/sessao (uuid4 hex)."""
    return uuid.uuid4().hex

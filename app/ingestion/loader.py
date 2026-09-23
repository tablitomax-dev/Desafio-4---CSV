"""Carga de CSVs (de um ZIP) em tabelas DuckDB com normalizacao deterministica."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from app.catalog.catalog import Catalog, DicionarioDados, TabelaDict
from app.catalog.rules import TIPOS_TEMPORAIS
from app.ingestion.dicionario_generator import gerar_tabela
from app.ingestion.normalizer import normalizar_valor
from app.ingestion.zip_processor import extrair_zip


def _detectar_encoding(buf: io.BytesIO) -> str:
    raw = buf.read()
    buf.seek(0)
    try:
        raw.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def ler_csv(buf: io.BytesIO) -> pd.DataFrame:
    """Le o CSV com deteccao de encoding/delimitador, mantendo valores como texto."""
    enc = _detectar_encoding(buf)
    return pd.read_csv(buf, sep=None, engine="python", encoding=enc, dtype=str)


def carregar_dataframe(con: Any, df: pd.DataFrame, tabela: TabelaDict) -> None:
    """Cria a tabela no DuckDB com colunas canonicas normalizadas + originais preservadas.

    Colunas temporais (data/datetime) sao tipadas como DATE/TIMESTAMP na tabela,
    para que o SQL gerado pelo agente (ex.: `BETWEEN DATE '...'`) funcione. Sem
    isso, a coluna ficaria como VARCHAR e o DuckDB rejeitaria a comparacao.
    """
    colunas = {c.origem: c for c in tabela.colunas if c.origem in df.columns}
    if not colunas:
        raise ValueError(f"Nenhuma coluna do dicionario encontrada para a tabela {tabela.nome}")

    out: dict[str, Any] = {}
    for origem, coluna in colunas.items():
        raw = df[origem]
        out[f"{coluna.canonico}_origem"] = raw
        out[coluna.canonico] = raw.map(lambda v: normalizar_valor(v, coluna))

    novo = pd.DataFrame(out)
    con.register("__nova", novo)

    # Monta o SELECT com CAST explicito para colunas temporais, preservando a
    # ordem original (para cada coluna: `_origem` seguida da canonica).
    selecao: list[str] = []
    for coluna in tabela.colunas:
        origem_col = f"{coluna.canonico}_origem"
        if origem_col in novo.columns:
            selecao.append(f'"{origem_col}"')
        if coluna.canonico not in novo.columns:
            continue
        if coluna.tipo in TIPOS_TEMPORAIS:
            tipo = "TIMESTAMP" if coluna.tipo == "datetime" else "DATE"
            selecao.append(f'CAST("{coluna.canonico}" AS {tipo}) AS "{coluna.canonico}"')
        else:
            selecao.append(f'"{coluna.canonico}"')

    con.execute(
        f'CREATE OR REPLACE TABLE "{tabela.nome}" AS SELECT {", ".join(selecao)} FROM __nova'
    )


def processar_zip(con: Any, zip_bytes: io.BytesIO) -> tuple[Catalog, list[str]]:
    """Extrai o ZIP, gera o dicionario de dados automaticamente e carrega os CSVs.

    O usuario envia apenas CSVs; o dicionario (schema/tipos/regras) e inferido aqui.
    """
    arquivos = extrair_zip(zip_bytes)
    dados: list[tuple[str, pd.DataFrame]] = []
    for nome, buf in arquivos.items():
        if nome.endswith(".csv"):
            dados.append((nome, ler_csv(buf)))
    if not dados:
        raise ValueError("Nenhum CSV encontrado no ZIP")

    tabelas = [gerar_tabela(nome, df) for nome, df in dados]
    catalog = Catalog(DicionarioDados(tabelas=tabelas))

    tabelas_carregadas: list[str] = []
    for (nome, df), tabela in zip(dados, tabelas):
        carregar_dataframe(con, df, tabela)
        tabelas_carregadas.append(tabela.nome)

    return catalog, tabelas_carregadas

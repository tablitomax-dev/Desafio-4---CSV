"""Validacao manual da ingestao com CSV real (encoding/delimitador/desempenho).

Uso:
    uv run python spike/validar_ingestao_real.py <caminho_do_csv>
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from app.catalog.catalog import Catalog
from app.ingestion.loader import carregar_dataframe, ler_csv
from app.ingestion.schema_detector import detectar_tabela
from app.query.duckdb_client import DuckDBClient


def main() -> None:
    csv_path = Path(sys.argv[1])
    catalog = Catalog.carregar(Path("tests/fixtures/dicionario.json"))

    with open(csv_path, "rb") as f:
        buf = io.BytesIO(f.read())
    df = ler_csv(buf)
    tabela = detectar_tabela(catalog, list(df.columns))
    print(f"arquivo: {csv_path.name}")
    print(f"tabela detectada: {tabela.nome if tabela else None} | linhas: {len(df)}")
    if tabela is None:
        sys.exit("Schema nao reconhecido.")

    client = DuckDBClient()
    try:
        carregar_dataframe(client.con, df, tabela)
        n = client.execute(f"SELECT count(*) AS n FROM {tabela.nome}").linhas[0][0]
        col_valor = "valor_total" if tabela.nome == "notas_fiscais_itens" else "valor_nota_fiscal"
        total = client.execute(
            f"SELECT SUM({col_valor}) AS total, "
            f"COUNT(DISTINCT razao_social_emitente) AS fornecedores FROM {tabela.nome}"
        ).linhas[0]
        print(f"no duckdb: {n} linhas | total R$ {total[0]:,.2f} | fornecedores: {total[1]}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

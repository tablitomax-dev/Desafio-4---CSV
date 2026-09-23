"""Acesso read-only ao DuckDB — unica camada de acesso ao banco.

A ingestao (Etapa 2) escreve via `con` (conexao subjacente); a consulta usa
`execute`, que rejeita operacoes de escrita.
"""

from __future__ import annotations

import duckdb

from app.contracts import Resultado

_WRITE_KEYWORDS = frozenset(
    {
        "insert",
        "update",
        "delete",
        "create",
        "drop",
        "alter",
        "truncate",
        "replace",
        "merge",
        "copy",
        "attach",
        "detach",
        "comment",
        "pragma",
    }
)


class DuckDBClient:
    """Gerencia a conexao DuckDB e executa consultas read-only."""

    def __init__(
        self,
        con: duckdb.DuckDBPyConnection | None = None,
        dataset_id: str | None = None,
    ) -> None:
        self.con = con if con is not None else duckdb.connect(
            config={"enable_external_access": True}
        )
        self.dataset_id = dataset_id

    def execute(self, sql: str, params: list | None = None) -> Resultado:
        """Executa uma consulta read-only e retorna `Resultado` (colunas + linhas).

        `params` sao passados como parametros posicionais (seguro contra injection).
        """
        stripped = sql.strip()
        if not stripped:
            raise ValueError("SQL vazio.")
        first = stripped.split(maxsplit=1)[0].lower()
        if first in _WRITE_KEYWORDS:
            raise ValueError(f"Operacao de escrita nao permitida na consulta: {first!r}")

        # Allowlist de schemas: o agente consulta apenas dados tratados
        # (curated.* e meta.*). A camada staging (dados brutos) nao e exposta.
        if "staging." in stripped.lower():
            raise ValueError(
                "Acesso a dados brutos (staging) nao permitido na consulta."
            )

        cursor = self.con.execute(sql, params) if params is not None else self.con.execute(sql)
        colunas = [desc[0] for desc in cursor.description] if cursor.description else []
        linhas = [list(row) for row in cursor.fetchall()] if cursor.description else []
        return Resultado(colunas=colunas, linhas=linhas)

    def close(self) -> None:
        """Fecha a conexao."""
        self.con.close()

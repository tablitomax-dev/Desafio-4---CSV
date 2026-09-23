"""Carga da camada staging: dados brutos proximos do CSV, sem regra de negocio."""

from __future__ import annotations

from typing import Any

import pandas as pd


class StagingLoader:
    """Carrega o CSV bruto em `staging.raw_<nome>`, preservando valores originais."""

    def carregar(self, con: Any, nome_canonico: str, df: pd.DataFrame) -> None:
        con.register("__staging", df)
        con.execute(
            f'CREATE OR REPLACE TABLE "staging"."raw_{nome_canonico}" '
            "AS SELECT * FROM __staging"
        )

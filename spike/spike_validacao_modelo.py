"""
Spike de validação — Desafio 4 I2A2.

Valida a stack de IA com escopo fechado antes de codar o produto.
Uso (a partir da raiz do projeto):

    uv run python spike/spike_validacao_modelo.py --checar-modelo
    uv run python spike/spike_validacao_modelo.py --checar-structured
    uv run python spike/spike_validacao_modelo.py --sql-referencia --csv fixtures/nf_amostra.csv
    uv run python spike/spike_validacao_modelo.py --threshold-fuzzy --csv fixtures/nf_amostra.csv
    uv run python spike/spike_validacao_modelo.py --carga-grande --csv <arquivo_grande.csv>

Depende de `OPENROUTER_API_KEY` no ambiente (`.env`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Carga de .env
load_dotenv()

MODEL = os.getenv("MODEL", "openai/gpt-5.6-luna-pro")
PROVIDER = os.getenv("PROVIDER", "openai")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Perguntas de referência (SQL grounded)
REFERENCIA: list[dict[str, str]] = [
    {"pergunta": "Qual é o maior fornecedor (por valor)?"},
    {"pergunta": "Qual é o total por mês?"},
    {"pergunta": "Quais são os 5 maiores fornecedores?"},
    {"pergunta": "Como foi o crescimento por categoria?"},
]


def checar_modelo() -> None:
    """Valida o slug do modelo no OpenRouter com o provider indicado."""
    try:
        from openai import OpenAI

        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY"))
        models = client.models.list()
        slugs = [m.id for m in models.data]
        if MODEL in slugs:
            print(f"[OK] Modelo '{MODEL}' existe no OpenRouter.")
        else:
            print(f"[FALHOU] Modelo '{MODEL}' NAO encontrado.")
            print("Modelos contendo 'luna' ou similares:")
            for s in slugs:
                if "luna" in s or "gpt-5" in s:
                    print("   -", s)
        print(f"Provider configurado: {PROVIDER}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha ao consultar modelo: {exc!r}")
        sys.exit(1)


def checar_structured() -> None:
    """Valida structured output + tool-calling via Pydantic AI."""
    try:
        from pydantic import BaseModel, Field
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        class ChartSpec(BaseModel):
            chart_type: str = Field(pattern="^(bar|line|pie|scatter)$")
            x: str
            y: str
            title: str

        class Resposta(BaseModel):
            output_kind: str = Field(pattern="^(text|table|chart)$")
            texto: str | None = None
            chart: ChartSpec | None = None

        model = OpenAIChatModel(
            MODEL,
            provider=OpenAIProvider(
                base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY")
            ),
        )
        agent = Agent(model, output_type=Resposta, system_prompt="Seja conciso.")

        @agent.tool_plain
        def tool_soma(a: int, b: int) -> int:
            """Soma dois inteiros (tool de teste)."""
            return a + b

        # Teste 1: structured output
        r1 = agent.run_sync("Resuma em uma frase. output_kind=text, texto='ok'.")
        print(f"[structured] output_kind={r1.output.output_kind} texto={r1.output.texto!r}")

        # Teste 2: tool-calling
        r2 = agent.run_sync("Use a tool_soma para somar 3 e 4.")
        print(f"[tool-calling] tipo={type(r2.output).__name__} valor={r2.output!r}")

        print("[OK] Structured output + tool-calling funcionando.")
    except Exception as exc:  # noqa: BLE001
        print(f"[FALHOU] Pydantic AI structured/tool: {exc!r}")
        sys.exit(1)


def _carregar_csv(csv_path: Path):
    import duckdb
    import pandas as pd

    # Deteccao de encoding: utf-8-sig (BOM) com fallback latin-1
    enc = "utf-8-sig"
    try:
        csv_path.read_bytes().decode(enc)
    except UnicodeDecodeError:
        enc = "latin-1"

    # sep=None (sniffing) + decimal BR (virgula) — normalizacao basica de dados sujos
    df = pd.read_csv(csv_path, sep=None, engine="python", encoding=enc, decimal=",")
    con = duckdb.connect(config={"enable_external_access": True})
    con.register("tmp_df", df)
    con.execute("CREATE TABLE amostra AS SELECT * FROM tmp_df")
    return con


def sql_referencia(csv_path: Path) -> None:
    """Gera e executa SQL (simulado/real) para as perguntas de referência."""

    con = _carregar_csv(csv_path)
    print(f"Linhas carregadas: {con.execute('SELECT count(*) FROM amostra').fetchone()[0]}")

    # Exemplo grounded: total por RAZÃO SOCIAL EMITENTE
    queries = {
        "total por fornecedor": (
            'SELECT "RAZÃO SOCIAL EMITENTE", SUM("VALOR NOTA FISCAL") AS total '
            "FROM amostra GROUP BY 1 ORDER BY total DESC LIMIT 5"
        ),
    }
    for nome, q in queries.items():
        try:
            rows = con.execute(q).fetchall()
            print(f"[SQL] {nome}: {len(rows)} linhas — primeiro: {rows[0] if rows else None}")
        except Exception as exc:  # noqa: BLE001
            print(f"[SQL] {nome} FALHOU: {exc!r}")


def threshold_fuzzy(csv_path: Path) -> None:
    """Calibra threshold de fuzzy em dados sujos, sem falso positivo em chaves."""
    con = _carregar_csv(csv_path)
    print("[PROGRESSIVO] 1) normalizacao (lower+trim) ja resolve caixa/espaco:")
    try:
        rows = con.execute(
            """
            SELECT DISTINCT lower(trim("RAZÃO SOCIAL EMITENTE")) AS nome
            FROM amostra
            WHERE lower(trim("RAZÃO SOCIAL EMITENTE")) LIKE '%acme%'
            """
        ).fetchall()
        for r in rows:
            print(f"   - {r[0]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"   [falhou] {exc!r}")

    print("[FUZZY] 2) levenshtein (distancia de edicao) para typos:")
    try:
        rows = con.execute(
            """
            SELECT "MUNICÍPIO EMITENTE",
                   levenshtein(lower(trim("MUNICÍPIO EMITENTE")), 'sao paulo') AS dist
            FROM amostra
            WHERE "MUNICÍPIO EMITENTE" IS NOT NULL
            LIMIT 8
            """
        ).fetchall()
        for r in rows:
            print(f"   {r[0]!r} -> dist {r[1]}")
    except Exception as exc:  # noqa: BLE001
        print(f"   [falhou] {exc!r}")
    print("[NOTA] Calibrar threshold com dados reais; exato em CNPJ/CHAVE.")


def carga_grande(csv_path: Path) -> None:
    """Valida carga e desempenho com CSV grande."""
    import time


    t0 = time.time()
    con = _carregar_csv(csv_path)
    t_load = time.time() - t0
    n = con.execute("SELECT count(*) FROM amostra").fetchone()[0]
    t0 = time.time()
    con.execute('SELECT count(*) FROM amostra').fetchall()
    t_query = time.time() - t0
    print(f"[CARGA] {n} linhas em {t_load:.2f}s; query simples em {t_query*1000:.0f}ms")


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        print("AVISO: OPENROUTER_API_KEY nao encontrada. Configure no .env.")

    p = argparse.ArgumentParser(description="Spike de validacao")
    p.add_argument("--checar-modelo", action="store_true")
    p.add_argument("--checar-structured", action="store_true")
    p.add_argument("--sql-referencia", action="store_true")
    p.add_argument("--threshold-fuzzy", action="store_true")
    p.add_argument("--carga-grande", action="store_true")
    p.add_argument("--csv", type=Path, default=Path("fixtures/nf_amostra.csv"))
    args = p.parse_args()

    tem_flag = (
        args.checar_modelo
        or args.checar_structured
        or args.sql_referencia
        or args.threshold_fuzzy
        or args.carga_grande
    )
    if not tem_flag:
        p.print_help()
        return

    if args.checar_modelo:
        checar_modelo()
    if args.checar_structured:
        checar_structured()
    if args.sql_referencia:
        sql_referencia(args.csv)
    if args.threshold_fuzzy:
        threshold_fuzzy(args.csv)
    if args.carga_grande:
        carga_grande(args.csv)


if __name__ == "__main__":
    main()

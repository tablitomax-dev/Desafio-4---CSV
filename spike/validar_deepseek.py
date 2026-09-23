"""Validacao do DeepSeek V4 Flash no OpenRouter e do roteamento de fallback.

Valida, com chamada real:
  1. se o slug `deepseek/deepseek-v4-flash-0731` existe no OpenRouter;
  2. quais sufixos de provider forcam a DeepInfra (plain, `:deepinfra`,
     `:deepinfra/fp4`) sem erro;
  3. se o modelo consegue chamar tools de verdade (structured output + tool-calling)
     via Pydantic AI contra um CSV grounded.

Uso (a partir da raiz):
    uv run python spike/validar_deepseek.py --modelo
    uv run python spike/validar_deepseek.py --providers
    uv run python spike/validar_deepseek.py --tool-calling

Depende de `OPENROUTER_API_KEY` no `.env`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "deepseek/deepseek-v4-flash-0731"

# Variantes de slug para tentar forcar a DeepInfra no OpenRouter.
CANDIDATOS = [
    MODEL,                                  # roteamento padrao do OpenRouter
    f"{MODEL}:deepinfra",                   # sufixo de provider (formato confirmado)
    f"{MODEL}:deepinfra/fp4",               # sufixo com variante de endpoint/quantizacao
]


def _client():
    from openai import OpenAI

    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY"))


def checar_modelo() -> None:
    """Confirma a existencia do slug no OpenRouter e lista similares."""
    try:
        models = _client().models.list()
        slugs = [m.id for m in models.data]
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha ao listar modelos: {exc!r}")
        sys.exit(1)

    if MODEL in slugs:
        print(f"[OK] Slug '{MODEL}' existe no OpenRouter.")
        return
    print(f"[FALHOU] Slug '{MODEL}' NAO encontrado. Similares contendo 'deepseek':")
    for s in slugs:
        if "deepseek" in s:
            print("   -", s)


def checar_providers() -> None:
    """Tenta uma completion curta com cada candidato de slug/provider."""
    client = _client()
    for slug in CANDIDATOS:
        try:
            resp = client.chat.completions.create(
                model=slug,
                messages=[{"role": "user", "content": "responda apenas: ok"}],
                max_tokens=64,
            )
            choice = resp.choices[0]
            content = choice.message.content
            saida = content.strip() if content else f"(sem content; finish={choice.finish_reason})"
            print(f"[OK] {slug!r} -> {saida!r}")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).splitlines()[0][:160]
            print(f"[FALHOU] {slug!r} -> {type(exc).__name__}: {msg}")


def checar_tool_calling(slug: str) -> None:
    """Valida structured output + tool-calling via Pydantic AI com CSV grounded."""
    from app.catalog.catalog import Catalog
    from app.query.duckdb_client import DuckDBClient

    csv_path = Path("tests/fixtures/nf_amostra.csv")
    cliente = DuckDBClient()
    catalog = Catalog.carregar(Path("tests/fixtures/dicionario.json"))

    import pandas as pd

    from app.ingestion.loader import carregar_dataframe

    df = pd.read_csv(csv_path, sep=None, engine="python", encoding="utf-8-sig", dtype=str)
    carregar_dataframe(cliente.con, df, catalog.tabela("notas_fiscais"))

    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    model = OpenAIChatModel(
        slug,
        provider=OpenAIProvider(
            base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY")
        ),
    )
    agent = Agent(model, retries=2, system_prompt="Responda apenas com o resultado.")


    def consultar(sql: str) -> dict:
        """Executa uma consulta read-only no DuckDB (grounded)."""
        if "notas_fiscais" not in sql.lower():
            raise ValueError("Consulta deve referenciar a tabela 'notas_fiscais'.")
        r = cliente.execute(sql)
        return {"colunas": r.colunas, "linhas": r.linhas}

    agent.tool_plain(consultar)

    pergunta = (
        "Use a tool consultar para retornar as 3 maiores razao_social_emitente por "
        "sum(valor_nota_fiscal). SQL: SELECT razao_social_emitente, "
        "SUM(valor_nota_fiscal) AS total FROM notas_fiscais GROUP BY 1 ORDER BY total DESC LIMIT 3."
    )
    try:
        r = agent.run_sync(pergunta)
        print(f"[tool-calling {slug!r}] -> {str(r.output)[:200]!r}")
        print("[OK] DeepSeek conseguiu chamar a tool de consulta.")
    except Exception as exc:  # noqa: BLE001
        print(f"[FALHOU tool-calling {slug!r}] -> {type(exc).__name__}: {exc!r}")
    finally:
        cliente.close()


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        print("AVISO: OPENROUTER_API_KEY nao encontrada. Configure no .env.")

    p = argparse.ArgumentParser(description="Validacao do DeepSeek V4 Flash no OpenRouter")
    p.add_argument("--modelo", action="store_true")
    p.add_argument("--providers", action="store_true")
    p.add_argument("--tool-calling", action="store_true")
    p.add_argument("--slug", type=str, default=f"{MODEL}:deepinfra")
    args = p.parse_args()

    if not any((args.modelo, args.providers, args.tool_calling)):
        p.print_help()
        return
    if args.modelo:
        checar_modelo()
    if args.providers:
        checar_providers()
    if args.tool_calling:
        checar_tool_calling(args.slug)


if __name__ == "__main__":
    main()

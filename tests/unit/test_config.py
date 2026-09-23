"""Testes de configuração (app/config.py)."""

import os

from app.config import Settings


def test_config_defaults():
    s = Settings(_env_file=None, openrouter_api_key="chave-teste")
    assert s.model == "deepseek/deepseek-v4-flash-0731:deepinfra/fp4"
    assert s.provider == "deepinfra/fp4"
    assert s.fallback_model == "openai/gpt-5.6-luna-pro"
    assert s.fallback_provider == "openai"
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.openrouter_api_key == "chave-teste"
    assert s.temperature == 0.0


def test_config_sobrescreve_por_variavel_de_ambiente():
    os.environ["MODEL"] = "outro/modelo:deepinfra"
    os.environ["PROVIDER"] = "deepinfra"
    os.environ["FALLBACK_MODEL"] = "outro/fallback"
    os.environ["FALLBACK_PROVIDER"] = "openai"
    try:
        s = Settings(_env_file=None, openrouter_api_key="chave-teste")
        assert s.model == "outro/modelo:deepinfra"
        assert s.provider == "deepinfra"
        assert s.fallback_model == "outro/fallback"
        assert s.fallback_provider == "openai"
    finally:
        os.environ.pop("MODEL", None)
        os.environ.pop("PROVIDER", None)
        os.environ.pop("FALLBACK_MODEL", None)
        os.environ.pop("FALLBACK_PROVIDER", None)


def test_config_chave_vazia_por_padrao():
    s = Settings(_env_file=None)
    assert s.openrouter_api_key == ""

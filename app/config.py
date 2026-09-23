"""Configuracao central da aplicacao (modelo/provider/slugs via ambiente)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao lida de variaveis de ambiente e do arquivo `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Modelo primario (ex.: deepseek/deepseek-v4-flash-0731:deepinfra/fp4)
    model: str = "deepseek/deepseek-v4-flash-0731:deepinfra/fp4"
    provider: str = "deepinfra/fp4"

    # Temperatura das chamadas de LLM. Em tarefas analiticas/de tool-calling o
    # valor 0 reduz a variancia entre execucoes (mesmo modelo, mesma pergunta
    # -> resultado mais estavel), sem eliminar o nao-determinismo por completo.
    temperature: float = 0.0

    # Modelo fallback para quando o primario esgota retries de tool
    fallback_model: str = "openai/gpt-5.6-luna-pro"
    fallback_provider: str = "openai"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


settings = Settings()

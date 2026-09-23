# Desafio 4 I2A2 — Consulta de CSV em linguagem natural

MVP para consultar dados de notas fiscais em CSVs via linguagem natural.

**Stack**: Python · Streamlit · DuckDB · Pydantic AI · Plotly · ReportLab

## Setup

```bash
uv sync                 # instala dependências em .venv
uv run python spike/spike_validacao_modelo.py --checar-modelo  # Etapa 0 (spike)
uv run streamlit run app/main.py                              # aplicação
```

> Configuração (modelo/provider/API key) em `.env` (copie de `.env.example`).

## Documentação de arquitetura

Ver `.specs-fire/standards/system-architecture.md` e `.specs-fire/intents/consulta-csv-linguagem-natural/`.

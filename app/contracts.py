"""Contratos tipados de dominio/aplicacao.

Nao confundir com schema de banco: aqui ficam os modelos de resposta do fluxo
de consulta e os schemas declarativos usados pelo agente e pela apresentacao.
"""

from typing import Literal

from pydantic import BaseModel

OutputKind = Literal["text", "table", "chart"]
ChartType = Literal["bar", "line", "pie", "scatter", "area"]

# Status da analise semantica da pergunta (gate semantico via LLM).
StatusSemantica = Literal["consulta", "ambigua", "maliciosa", "fora_de_escopo"]

# Granularidade de uma tabela: uma linha por nota (cabecalho) ou por item.
Granularidade = Literal["nota", "item"]

# Severidade de um problema de qualidade/ingestao.
Severidade = Literal["blocking", "warning", "info"]


class AnaliseSemantica(BaseModel):
    """Classificacao semantica da pergunta do usuario.

    - `consulta`: pergunta legitima sobre os dados; segue para o agente.
    - `ambigua`: pode ter multiplas interpretacoes; `interpretacoes` traz >= 2.
    - `maliciosa`: intencao maliciosa/proibida (ataque, fraude, escrita, etc.).
    - `fora_de_escopo`: nao diz respeito aos arquivos carregados.
    """

    status: StatusSemantica
    interpretacoes: list[str] = []
    motivo: str | None = None


class ChartSpec(BaseModel):
    """Especificacao declarativa de grafico (render e deterministico no Streamlit/Plotly)."""

    chart_type: ChartType
    x: str
    y: str
    title: str = ""


class Resultado(BaseModel):
    """Resultado de uma consulta: colunas + linhas."""

    colunas: list[str]
    linhas: list[list]


class RespostaAgente(BaseModel):
    """Resposta final do agente, renderizada de forma deterministica."""

    output_kind: OutputKind
    texto: str | None = None
    colunas: list[str] | None = None
    linhas: list[list] | None = None
    chart: ChartSpec | None = None


class Relationship(BaseModel):
    """Relacionamento semantico entre duas tabelas (master-detail por chave)."""

    from_tabela: str
    to_tabela: str
    chave: str
    tipo: Literal["master_detail"] = "master_detail"


class Issue(BaseModel):
    """Problema de qualidade/ingestao com severidade e localizacao opcional."""

    severidade: Severidade
    codigo: str
    mensagem: str
    tabela: str | None = None
    linha: int | None = None


class QualityReport(BaseModel):
    """Relatorio de qualidade do dataset (issues + metricas)."""

    issues: list[Issue] = []
    metricas: dict[str, int | float | str | None] = {}

    @property
    def bloqueantes(self) -> list[Issue]:
        return [i for i in self.issues if i.severidade == "blocking"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severidade == "warning"]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.severidade == "info"]

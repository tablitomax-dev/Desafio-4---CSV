"""Testes das tools do agente (app/agent/tools.py)."""

from pathlib import Path

import pytest
from pydantic_ai.exceptions import ModelRetry

from app.agent.tools import ToolsNF
from app.catalog.catalog import (
    Catalog,
    ColunaDict,
    DicionarioDados,
    TabelaDict,
)
from app.query.duckdb_client import DuckDBClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def cliente() -> DuckDBClient:
    c = DuckDBClient()
    c.con.execute("CREATE SCHEMA curated")
    c.con.execute(
        'CREATE TABLE "curated"."notas_fiscais" ('
        "razao_social_emitente VARCHAR, cnpj_destinatario VARCHAR, municipio_emitente VARCHAR, "
        "uf_emitente VARCHAR)"
    )
    c.con.execute(
        'INSERT INTO "curated"."notas_fiscais" VALUES '
        "('acme industrial ltda', '11122233000101', 'sao paulo', 'sp'), "
        "('acme quimica', '22233344000155', 'campinas', 'sp'), "
        "('beta sa', '33344455000166', 'curitiba', 'pr')"
    )
    yield c
    c.close()


def _tools(cliente: DuckDBClient) -> ToolsNF:
    return ToolsNF(cliente, Catalog.carregar(FIXTURES / "dicionario.json"))


def test_esquema_lista_tabelas_e_colunas(cliente):
    esquema = _tools(cliente).esquema()
    tabelas = {t["tabela"] for t in esquema}
    assert "curated.notas_fiscais" in tabelas
    notas = next(t for t in esquema if t["tabela"] == "curated.notas_fiscais")
    canonicos = {c["coluna"] for c in notas["colunas"]}
    assert "razao_social_emitente" in canonicos


def test_consultar_select(cliente):
    r = _tools(cliente).consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    assert "razao_social_emitente" in r["colunas"]
    assert len(r["linhas"]) == 3


def test_consultar_rejeita_sql_invalido(cliente):
    # SQL de escrita: bloqueado com ModelRetry (o framework retenta a tool).
    with pytest.raises(ModelRetry):
        _tools(cliente).consultar("DELETE FROM curated.notas_fiscais")


def test_consultar_erro_em_agregacao_invalida_gera_retry(cliente):
    # Coluna nao agregada fora do GROUP BY: levanta ModelRetry (em vez de
    # lancar ValueError cru que abortaria a run sem chance de autocorrecao).
    with pytest.raises(ModelRetry, match="GROUP BY"):
        _tools(cliente).consultar(
            "SELECT municipio_emitente, COUNT(*) FROM curated.notas_fiscais"
        )


def test_consultar_sem_truncamento(cliente):
    r = _tools(cliente).consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    assert r["truncado"] is False
    assert r["total_linhas"] == 3
    assert len(r["linhas"]) == 3


def test_ultimo_resultado_none_antes_de_consultar(cliente):
    assert _tools(cliente).ultimo_resultado is None


def test_consultar_guarda_ultimo_resultado(cliente):
    tools = _tools(cliente)
    tools.consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    ultimo = tools.ultimo_resultado
    assert ultimo is not None
    assert "razao_social_emitente" in ultimo["colunas"]
    assert len(ultimo["linhas"]) == 3


def test_consultar_invalido_nao_sobrescreve_ultimo_resultado(cliente):
    tools = _tools(cliente)
    tools.consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    with pytest.raises(ModelRetry):
        tools.consultar("DELETE FROM curated.notas_fiscais")
    ultimo = tools.ultimo_resultado
    assert ultimo is not None
    assert len(ultimo["linhas"]) == 3


def test_consultar_limita_linhas_para_o_modelo(cliente, monkeypatch):
    monkeypatch.setattr("app.agent.tools.MAX_ROWS", 2)
    r = _tools(cliente).consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    assert r["truncado"] is True
    assert r["total_linhas"] == 3
    assert len(r["linhas"]) == 2


def test_buscar_textual_match_exato(cliente):
    r = _tools(cliente).buscar_textual(
        "curated.notas_fiscais", "razao_social_emitente", "acme"
    )
    assert "acme industrial ltda" in r
    assert "acme quimica" in r


def test_buscar_textual_fuzzy_por_typo(cliente):
    r = _tools(cliente).buscar_textual(
        "curated.notas_fiscais", "municipio_emitente", "sao pauo"
    )
    assert "sao paulo" in r


def test_buscar_textual_identificador_devolve_orientacao(cliente):
    # Em vez de lancar erro interno (que vazava "fuzzy proibido" ao usuario),
    # a tool orienta o modelo a usar filtro exato / GROUP BY na coluna.
    r = _tools(cliente).buscar_textual("curated.notas_fiscais", "cnpj_destinatario", "111")
    assert isinstance(r, list) and r
    texto = " ".join(r).lower()
    assert "grupo" in texto or "agrup" in texto or "filtro" in texto or "exato" in texto


def test_buscar_textual_categoria_sem_match_nao_lanca(cliente):
    # Coluna de categoria (ex.: uf_emitente) nao tem fuzzy; sem match exato,
    # devolve lista vazia em vez de erro interno.
    assert _tools(cliente).buscar_textual("curated.notas_fiscais", "uf_emitente", "zz") == []


def test_buscar_textual_categoria_match_exato(cliente):
    r = _tools(cliente).buscar_textual("curated.notas_fiscais", "uf_emitente", "sp")
    assert r == ["sp"]


def test_consultar_0_linhas_com_filtro_caixa_alta_da_dica_de_normalizacao(cliente):
    # WHERE uf_emitente = 'SP' nao acha nada (dados em minusculas). A tool deve
    # devolver uma dica para o modelo usar LOWER() e autocorrigir, evitando que
    # o usuario receba "não encontrei dados" por causa de maiusculas/minusculas.
    r = _tools(cliente).consultar(
        "SELECT * FROM curated.notas_fiscais WHERE uf_emitente = 'SP'"
    )
    assert r["linhas"] == []
    assert "dica" in r
    assert "LOWER" in r["dica"].upper()


def test_consultar_0_linhas_sem_filtro_texto_nao_da_dica(cliente):
    r = _tools(cliente).consultar(
        "SELECT * FROM curated.notas_fiscais WHERE razao_social_emitente = 'nao_existe'"
    )
    assert r["linhas"] == []
    assert "dica" not in r


def test_buscar_textual_termo_vazio(cliente):
    assert (
        _tools(cliente).buscar_textual("curated.notas_fiscais", "razao_social_emitente", "")
        == []
    )


def test_buscar_textual_coluna_inexistente(cliente):
    with pytest.raises(ModelRetry):
        _tools(cliente).buscar_textual("curated.notas_fiscais", "coluna_fantasma", "x")


# --- estatisticas / detectar_outliers -------------------------------------


def _catalog_com_valor() -> Catalog:
    """Catalogo com uma coluna numerica (valor_nota_fiscal) para testes de stats."""
    tabela = TabelaDict(
        nome="notas_fiscais",
        fonte="nf_cabecalho.csv",
        colunas=[
            ColunaDict(origem="CHAVE", canonico="chave_acesso", tipo="identificador"),
            ColunaDict(origem="RAZAO", canonico="razao_social_emitente", tipo="texto"),
            ColunaDict(origem="UF", canonico="uf_emitente", tipo="categoria", agregavel=True),
            ColunaDict(
                origem="VALOR",
                canonico="valor_nota_fiscal",
                tipo="decimal",
                agregavel=True,
            ),
        ],
    )
    return Catalog(DicionarioDados(tabelas=[tabela]))


# 16 valores: 15 normais (~100) e 1 outlier forte (3000). Com media ~283 e
# desvio ~700, o limite superior fica ~2390: apenas o 3000 e outlier.
_VALORES = [
    (100, "empresa a", "sp"), (105, "empresa a", "sp"), (95, "empresa a", "sp"),
    (110, "empresa a", "sp"), (102, "empresa b", "rj"), (98, "empresa b", "rj"),
    (108, "empresa b", "rj"), (97, "empresa b", "rj"), (103, "empresa c", "mg"),
    (101, "empresa c", "mg"), (96, "empresa c", "mg"), (99, "empresa c", "mg"),
    (104, "empresa d", "pr"), (107, "empresa d", "pr"), (100, "empresa d", "pr"),
    (3000, "empresa e", "sp"),
]


@pytest.fixture
def cliente_valores() -> tuple[DuckDBClient, Catalog]:
    c = DuckDBClient()
    c.con.execute("CREATE SCHEMA curated")
    c.con.execute(
        'CREATE TABLE "curated"."notas_fiscais" ('
        "chave_acesso VARCHAR, razao_social_emitente VARCHAR, "
        "uf_emitente VARCHAR, valor_nota_fiscal DOUBLE)"
    )
    for i, (valor, empresa, uf) in enumerate(_VALORES):
        c.con.execute(
            "INSERT INTO curated.notas_fiscais VALUES (?, ?, ?, ?)",
            [f"chave{i:03d}", empresa, uf, valor],
        )
    yield c, _catalog_com_valor()
    c.close()


def _tools_valores(cliente_valores) -> ToolsNF:
    cliente, catalog = cliente_valores
    return ToolsNF(cliente, catalog)


def test_estatisticas_calcula_metricas(cliente_valores):
    r = _tools_valores(cliente_valores).estatisticas(
        "notas_fiscais", "valor_nota_fiscal"
    )
    assert "erro" not in r
    est = r["estatisticas"]
    assert est["contagem_nao_nulos"] == 16
    assert est["min"] == 95
    assert est["max"] == 3000
    assert est["media"] == pytest.approx(round(4525 / 16, 2))
    assert est["mediana"] is not None


def test_estatisticas_coluna_nao_numerica_gera_retry(cliente_valores):
    with pytest.raises(ModelRetry):
        _tools_valores(cliente_valores).estatisticas("notas_fiscais", "uf_emitente")


def test_estatisticas_tabela_inexistente_gera_retry(cliente_valores):
    with pytest.raises(ModelRetry):
        _tools_valores(cliente_valores).estatisticas(
            "tabela_fantasma", "valor_nota_fiscal"
        )


def test_detectar_outliers_identifica_valor_fora_do_padrao(cliente_valores):
    r = _tools_valores(cliente_valores).detectar_outliers(
        "notas_fiscais", "valor_nota_fiscal"
    )
    assert "erro" not in r
    assert r["total_outliers"] == 1
    assert r["linhas"][0][-1] == 3000
    assert r["limite_superior"] < 3000
    assert r["limite_inferior"] is not None


def test_detectar_outliers_coluna_nao_numerica_gera_retry(cliente_valores):
    with pytest.raises(ModelRetry):
        _tools_valores(cliente_valores).detectar_outliers(
            "notas_fiscais", "razao_social_emitente"
        )


def test_detectar_outliers_guarda_ultimo_resultado(cliente_valores):
    # Fallback deterministico: o pipeline reusa o ultimo resultado quando o
    # modelo devolve tabela vazia apesar de a tool ter retornado linhas.
    tools = _tools_valores(cliente_valores)
    tools.detectar_outliers("notas_fiscais", "valor_nota_fiscal")
    ultimo = tools.ultimo_resultado
    assert ultimo is not None
    assert "valor_nota_fiscal" in ultimo["colunas"]
    assert len(ultimo["linhas"]) == 1


def test_detectar_outliers_sem_dispersao_devolve_vazio(cliente_valores):
    # Todos os valores iguais: desvio padrao 0 -> sem outliers, sem erro.
    cliente, _ = cliente_valores
    cliente.con.execute("DELETE FROM curated.notas_fiscais")
    for i in range(5):
        cliente.con.execute(
            "INSERT INTO curated.notas_fiscais VALUES (?, 'x', 'sp', 100)",
            [f"c{i}"],
        )
    r = ToolsNF(cliente, _catalog_com_valor()).detectar_outliers(
        "notas_fiscais", "valor_nota_fiscal"
    )
    assert "erro" not in r
    assert r["total_outliers"] == 0
    assert r["linhas"] == []


def test_estatisticas_tabela_vazia_nao_estoura(cliente_valores):
    # Tabela sem linhas: a agregacao devolve contagem 0 e NULLs, sem crash.
    cliente, _ = cliente_valores
    cliente.con.execute("DELETE FROM curated.notas_fiscais")
    r = ToolsNF(cliente, _catalog_com_valor()).estatisticas(
        "notas_fiscais", "valor_nota_fiscal"
    )
    assert "erro" not in r
    assert r["estatisticas"]["contagem_nao_nulos"] == 0
    assert r["estatisticas"]["media"] is None


def test_detectar_outliers_tabela_vazia_nao_estoura(cliente_valores):
    # Tabela sem linhas: sem outliers, sem erro de index/unpack.
    cliente, _ = cliente_valores
    cliente.con.execute("DELETE FROM curated.notas_fiscais")
    r = ToolsNF(cliente, _catalog_com_valor()).detectar_outliers(
        "notas_fiscais", "valor_nota_fiscal"
    )
    assert "erro" not in r
    assert r["total_outliers"] == 0
    assert r["media"] is None


# --- resumo_financeiro -------------------------------------------------------


def test_resumo_financeiro_calcula_totais(cliente_valores):
    r = _tools_valores(cliente_valores).resumo_financeiro()
    assert "erro" not in r
    assert r["total_notas"] == 16
    assert r["valores_cabecalho"]["valor_nota_fiscal"] == 4525.0


def test_resumo_financeiro_guarda_ultimo_resumo(cliente_valores):
    tools = _tools_valores(cliente_valores)
    tools.resumo_financeiro()
    assert tools.ultimo_resumo is not None
    assert tools.ultimo_resumo["total_notas"] == 16


def test_resumo_financeiro_sem_tabela_gera_retry(cliente_valores):
    cliente, _ = cliente_valores
    vazio = Catalog(DicionarioDados(tabelas=[]))
    with pytest.raises(ModelRetry):
        ToolsNF(cliente, vazio).resumo_financeiro()


def test_limpar_ultimo_resultado_limpa_resultado_e_resumo(cliente_valores):
    tools = _tools_valores(cliente_valores)
    tools.consultar(
        "SELECT chave_acesso FROM curated.notas_fiscais ORDER BY 1"
    )
    tools.resumo_financeiro()
    assert tools.ultimo_resultado is not None
    assert tools.ultimo_resumo is not None

    tools.limpar_ultimo_resultado()

    assert tools.ultimo_resultado is None
    assert tools.ultimo_resumo is None


# --- validacao column-aware --------------------------------------------------


def test_consultar_rejeita_tabela_inexistente(cliente):
    # SQL gerado pelo LLM com tabela fantasma: ModelRetry (o framework retenta).
    with pytest.raises(ModelRetry, match="nao existe"):
        _tools(cliente).consultar("SELECT * FROM curated.tabela_fantasma")


def test_consultar_aceita_cte_com_nome_de_tabela(cliente):
    # CTE com o mesmo nome de uma tabela nao pode gerar falso "tabela inexistente".
    r = _tools(cliente).consultar(
        "WITH notas_fiscais AS (SELECT razao_social_emitente "
        "FROM curated.notas_fiscais) SELECT * FROM notas_fiscais"
    )
    assert len(r["linhas"]) == 3


def _cliente_com_data():
    c = DuckDBClient()
    c.con.execute("CREATE SCHEMA curated")
    c.con.execute(
        'CREATE TABLE "curated"."notas_fiscais" ('
        "chave_acesso VARCHAR, data_emissao DATE)"
    )
    c.con.execute(
        "INSERT INTO curated.notas_fiscais VALUES ('c1', DATE '2024-06-15')"
    )
    tabela = TabelaDict(
        nome="notas_fiscais",
        fonte="nf_cabecalho.csv",
        colunas=[
            ColunaDict(origem="CHAVE", canonico="chave_acesso", tipo="identificador"),
            ColunaDict(origem="DATA", canonico="data_emissao", tipo="data"),
        ],
    )
    return c, Catalog(DicionarioDados(tabelas=[tabela]))


def test_consultar_like_em_data_da_dica():
    # LIKE em coluna de data (tipo DATE) nao funciona; a tool orienta BETWEEN
    # antes de executar, em vez de devolver erro/SQL vazio ao modelo.
    c, catalog = _cliente_com_data()
    try:
        r = ToolsNF(c, catalog).consultar(
            "SELECT * FROM curated.notas_fiscais WHERE data_emissao LIKE '%2024%'"
        )
        assert r["linhas"] == []
        assert "dica" in r
        assert "BETWEEN" in r["dica"].upper()
        assert "data_emissao" in r["dica"]
    finally:
        c.close()


def test_metricas_contabilizam_modos_de_falha(cliente):
    tools = _tools(cliente)
    tools.consultar(
        "SELECT razao_social_emitente FROM curated.notas_fiscais ORDER BY 1"
    )
    assert tools.metricas["consultas"] == 1

    with pytest.raises(ModelRetry):
        tools.consultar("SELECT * FROM curated.tabela_fantasma")
    assert tools.metricas["tabela_inexistente"] == 1

    tools.consultar("SELECT * FROM curated.notas_fiscais WHERE uf_emitente = 'SP'")
    assert tools.metricas["dica_normalizacao"] == 1

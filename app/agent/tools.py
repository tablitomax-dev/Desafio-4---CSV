"""Tools do agente: consulta read-only, esquema e busca textual (fuzzy controlado).

O agente nao escreve fuzzy solto no SQL; usa `buscar_textual` de forma
deterministica. Nenhuma tool faz acesso direto a dados fora do `duckdb_client`.
"""

from __future__ import annotations

import logging
import re

from pydantic_ai.exceptions import ModelRetry

from app.agent.guardrails import validar_granularidade, validar_sql
from app.catalog.catalog import Catalog
from app.catalog.rules import (
    TIPOS_IDENTIFICADOR,
    TIPOS_NUMERICOS,
    TIPOS_TEMPORAIS,
    eh_identificador,
    permite_fuzzy,
)
from app.ingestion.normalizer import normalizar_texto
from app.query.duckdb_client import DuckDBClient

logger = logging.getLogger(__name__)

# Limite de linhas devolvidas ao modelo por chamada de tool. Evita que um
# resultado bruto gigante (ex.: "mostre todas as notas") seja reenviado
# inteiro ao LLM, o que inflaria o contexto e o custo por pergunta.
MAX_ROWS = 200

# Detecta comparacao de texto com literal em caixa alta/acentuado (ex.:
# WHERE uf_emitente = 'SP'). Como os dados sao normalizados em minusculas,
# esse filtro retorna 0 linhas; a dica orienta o modelo a usar LOWER().
_PADRAO_TEXTO_CAIXA_ALTA = re.compile(r"(?:=\s*|LIKE\s*)'[^']*[A-ZÀ-Ú]")


def _mascarar_strings(sql: str) -> str:
    """Substitui literais entre aspas simples por espacos.

    Evita que palavras dentro de strings (ex.: 'from x') sejam lidas como
    clausulas reais na extracao de tabelas.
    """
    return re.sub(r"'[^']*'", " ", sql)


def _referencias_tabelas(sql: str) -> list[str]:
    """Extrai nomes de tabelas referenciados em FROM/JOIN, ignorando CTEs.

    Remove aspas e literais antes de extrair. Nomes de CTE (`WITH x AS (...)` e
    `x AS (...)`) sao excluidos para nao gerar falso "tabela inexistente" em
    consultas com CTE (ex.: WITH stats AS (...) SELECT ... FROM stats).
    """
    s = re.sub(r'["`]', "", _mascarar_strings(sql))
    s = re.sub(r";", " ", s)
    ctes = set(re.findall(r"\bwith\s+([a-z_]\w*)", s, re.IGNORECASE))
    ctes |= set(re.findall(r"\b([a-z_]\w*)\s+as\s*\(", s, re.IGNORECASE))
    refs: list[str] = []
    for m in re.finditer(
        r"\b(?:from|join)\s+([a-z_]\w*(?:\.[a-z_]\w*)?)", s, re.IGNORECASE
    ):
        nome = m.group(1).lower()
        if nome not in ctes and nome not in refs:
            refs.append(nome)
    return refs


class ToolsNF:
    """Tools do agente de notas fiscais."""

    def __init__(
        self, cliente: DuckDBClient, catalog: Catalog, dataset_id: str | None = None
    ) -> None:
        self._cliente = cliente
        self._catalog = catalog
        self.dataset_id = dataset_id
        # Ultimo resultado (colunas+linhas) devolvido pela tool consultar. Usado
        # como fallback deterministico quando o LLM devolve tabela vazia apesar
        # de a consulta ter retornado dados (modelo falhou em propagar as linhas).
        self._ultimo_resultado: dict | None = None
        # Ultimo retorno de `resumo_financeiro`, para o agente conferir numeros
        # (e para a checagem anti-alucinacao saber quais numeros vieram da tool).
        self._ultimo_resumo: dict | None = None
        # Cache de tabelas existentes no banco (curated/meta) para validacao de
        # SQL column-aware sem consultar information_schema a cada chamada.
        self._tabelas_banco: frozenset[str] | None = None
        # Metricas observaveis por sessao (modos de falha) para orientar melhorias.
        self.metricas: dict[str, int] = {
            "consultas": 0,
            "erros_sql": 0,
            "tabela_inexistente": 0,
            "dica_normalizacao": 0,
            "dica_data": 0,
        }

    @property
    def ultimo_resultado(self) -> dict | None:
        """Ultimo resultado de `consultar`, para preenchimento defensivo no agente."""
        return self._ultimo_resultado

    @property
    def ultimo_resumo(self) -> dict | None:
        """Ultimo retorno de `resumo_financeiro`, para a checagem anti-alucinacao."""
        return self._ultimo_resumo

    def limpar_ultimo_resultado(self) -> None:
        """Limpa resultado/resumo das tools (chamado a cada nova pergunta).

        Evita que o fallback deterministico do agente reutilize dados de uma
        pergunta ANTERIOR — ex.: uma pergunta que legitima retorna 0 linhas
        nao pode receber as linhas da pergunta anterior como se fossem suas.
        """
        self._ultimo_resultado = None
        self._ultimo_resumo = None

    def _qualificar(self, nome: str) -> str:
        """Devolve o nome qualificado (curated.<nome>) de uma tabela do catalogo."""
        if "." in nome:
            return nome
        t = self._catalog.tabela(nome)
        return t.nome_qualificado if t else nome

    def _desqualificar(self, nome: str) -> str:
        """Remove o prefixo de schema (curated.) para resolver no catalogo."""
        return nome.split(".", 1)[-1] if "." in nome else nome

    def esquema(self) -> list[dict]:
        """Lista tabelas, colunas, granularidade e relacoes (para grounding do SQL).

        Os nomes de tabela sao expostos qualificados (ex.: `curated.nfs_cabecalho`)
        para que o SQL gerado pelo agente referencie as tabelas reais do DuckDB.
        """
        return [
            {
                "tabela": t.nome_qualificado,
                "granularidade": t.granularidade,
                "colunas": [
                    {
                        "coluna": c.canonico,
                        "tipo": c.tipo,
                        "regra_busca": c.regra_busca,
                        "agregavel": c.agregavel,
                    }
                    for c in t.colunas
                ],
            }
            for t in self._catalog.tabelas
        ] + [
            {
                "relacao": "master_detail",
                "from": self._qualificar(r.from_tabela),
                "to": self._qualificar(r.to_tabela),
                "chave": r.chave,
            }
            for r in self._catalog.relationships
        ]

    def consultar(self, sql: str) -> dict:
        """Executa uma consulta read-only no DuckDB e retorna colunas + linhas.

        Limita o numero de linhas devolvidas ao modelo (`MAX_ROWS`) para nao
        reenviar resultados brutos gigantes no contexto. Quando ha mais linhas,
        retorna `truncado=True` e `total_linhas` para o modelo informar o usuario.
        """
        validacao = validar_sql(sql)
        if not validacao.ok:
            raise ModelRetry(validacao.motivo)
        granularidade = validar_granularidade(sql, self._catalog)
        if not granularidade.ok:
            raise ModelRetry(granularidade.motivo)
        # Tabela inexistente (erro classico do LLM): falha antes de executar,
        # com mensagem instrutiva para o modelo autocorrigir no retry.
        self._validar_tabelas(sql)
        # LIKE em coluna de data nao funciona (DuckDB pode nem aceitar o tipo):
        # orienta BETWEEN antes de executar, em vez de devolver erro/SQL vazio.
        dica_data = self._dica_data(sql)
        if dica_data:
            self.metricas["dica_data"] += 1
            self._ultimo_resultado = {"colunas": [], "linhas": []}
            return {
                "colunas": [],
                "linhas": [],
                "truncado": False,
                "total_linhas": 0,
                "dica": dica_data,
            }
        logger.info("SQL do agente: %s", sql)
        self.metricas["consultas"] += 1
        try:
            resultado = self._cliente.execute(sql)
        except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
            logger.warning("Erro ao executar SQL do agente: %s", exc)
            self.metricas["erros_sql"] += 1
            raise ModelRetry(
                f"Erro ao executar o SQL: {exc}. Revise o SQL (ex.: colunas nao "
                "agregadas devem estar no GROUP BY) e tente novamente."
            ) from exc
        logger.info("Resultado do SQL: %d linha(s)", len(resultado.linhas))
        linhas = resultado.linhas[:MAX_ROWS]
        # Guarda o resultado para o fallback deterministico do agente.
        self._ultimo_resultado = {"colunas": resultado.colunas, "linhas": linhas}
        retorno = {
            "colunas": resultado.colunas,
            "linhas": linhas,
            "truncado": len(resultado.linhas) > MAX_ROWS,
            "total_linhas": len(resultado.linhas),
        }
        # Filtro de texto em caixa alta/acentuado contra dados normalizados
        # (minusculas) devolve 0 linhas. Da uma dica para o modelo autocorrigir
        # com LOWER() em vez de concluir que "nao ha dados".
        if not linhas and _PADRAO_TEXTO_CAIXA_ALTA.search(sql):
            retorno["dica"] = (
                "0 linhas. Os dados de texto sao armazenados em minusculas e sem "
                "acentos (ex.: 'sp'). Compare com LOWER(): WHERE LOWER(coluna) = "
                "LOWER('SP') ou LOWER(coluna) = 'sp'."
            )
            self.metricas["dica_normalizacao"] += 1
        return retorno

    def _tabelas_existentes(self) -> frozenset[str]:
        """Tabelas/views existentes para validar FROM/JOIN.

        Consulta todos os schemas exceto os de sistema: o builder publica em
        `curated`/`meta`, mas o loader legado carrega em `main`. Aceita tanto o
        nome qualificado (`curated.nf_cabecalho`) quanto o simples
        (`nf_cabecalho`), que o DuckDB resolve via search_path. A camada
        `staging` (dados brutos) nunca e exposta ao SQL do agente.
        """
        if self._tabelas_banco is None:
            linhas = self._cliente.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
            ).linhas
            nomes: set[str] = set()
            for schema, nome in linhas:
                simples = str(nome).lower()
                if str(schema).lower() != "staging":
                    nomes.add(f"{schema}.{simples}")
                nomes.add(simples)
            self._tabelas_banco = frozenset(nomes)
        return self._tabelas_banco

    def _validar_tabelas(self, sql: str) -> None:
        """Levanta ValueError se o SQL referenciar tabela inexistente no banco.

        Erros de "tabela inexistente" sao comuns em SQL gerado por LLM. Checar
        de forma deterministica contra o banco (curated/meta) da uma mensagem
        instrutiva no retry, em vez de o modelo queimar tentativas as cegas.
        """
        existentes = self._tabelas_existentes()
        for ref in _referencias_tabelas(sql):
            if ref not in existentes:
                self.metricas["tabela_inexistente"] += 1
                raise ModelRetry(
                    f"Tabela {ref!r} nao existe no banco. Consulte o esquema() "
                    "para ver as tabelas e colunas disponiveis e refaca o SQL."
                )

    def _dica_data(self, sql: str) -> str | None:
        """Dica quando LIKE e aplicado a uma coluna de data.

        Datas sao armazenadas como data (ISO), nao texto: `LIKE '%06%'` nao
        funciona e a consulta retorna 0 linhas. A dica orienta usar BETWEEN.
        """
        if "like" not in sql.lower():
            return None
        s = sql.lower()
        for tabela in self._catalog.tabelas:
            for col in tabela.colunas:
                if col.tipo in TIPOS_TEMPORAIS and col.canonico in s:
                    return (
                        f"0 linhas. A coluna {col.canonico!r} e do tipo data "
                        "(ISO yyyy-mm-dd) e NAO aceita LIKE. Para periodos use "
                        f"BETWEEN: WHERE {col.canonico} BETWEEN 'aaaa-mm-dd' "
                        "AND 'aaaa-mm-dd'."
                    )
        return None

    def buscar_textual(
        self,
        tabela: str,
        coluna: str,
        termo: str,
        limite: int = 20,
        threshold: int | None = None,
    ) -> list[str]:
        """Busca textual progressiva (exato normalizado -> levenshtein) em coluna descritiva.

        Colunas de categoria/codigo nao usam fuzzy: fazem apenas match exato. Em
        identificadores (cnpj, chave, cfop...) a tool devolve uma orientacao para
        o modelo usar filtro exato/GROUP BY, em vez de lancar erro interno que
        vazaria detalhes de implementacao para o usuario.
        """
        tabela_obj = self._catalog.tabela(self._desqualificar(tabela))
        if tabela_obj is None:
            raise ModelRetry(f"Tabela {tabela!r} nao existe no catalogo.")
        col = self._catalog.coluna_por_canonico(tabela_obj.nome, coluna)
        if col is None:
            raise ModelRetry(f"Coluna {coluna!r} nao existe na tabela {tabela!r}.")

        if eh_identificador(col):
            return [
                "Essa coluna e um codigo/identificador (ex.: CNPJ, chave, NCM). "
                "Use filtro exato (WHERE <coluna> = valor) ou agrupe por ela "
                "(GROUP BY) em vez de busca textual."
            ]

        termo_norm = normalizar_texto(termo)
        if not termo_norm:
            return []

        qualificado = tabela_obj.nome_qualificado

        # 1) match exato normalizado (a coluna canonica ja esta normalizada no load)
        valores = self._cliente.execute(
            f'SELECT DISTINCT "{coluna}" FROM {qualificado} '
            f'WHERE "{coluna}" LIKE ? ORDER BY 1 LIMIT ?',
            [f"%{termo_norm}%", limite],
        ).linhas
        achados = [r[0] for r in valores if r[0]]
        if achados:
            return achados[:limite]

        # 2) fuzzy controlado apenas em colunas descritivas marcadas no dicionario.
        #    Colunas de categoria/codigo nao tem fuzzy: sem match exato, vazio.
        if not permite_fuzzy(col):
            return []

        # 3) fuzzy controlado (levenshtein), distancia por comprimento do termo
        dist = threshold if threshold is not None else max(1, len(termo_norm) // 3)
        fuzzy = self._cliente.execute(
            f'SELECT DISTINCT "{coluna}", levenshtein("{coluna}", ?) AS d '
            f'FROM {qualificado} WHERE levenshtein("{coluna}", ?) <= ? ORDER BY d LIMIT ?',
            [termo_norm, termo_norm, dist, limite],
        ).linhas
        return [r[0] for r in fuzzy if r[0]][:limite]

    def _coluna_numerica(self, tabela: str, coluna: str):
        """Resolve tabela+coluna no catalogo; retorna (tabela, coluna) ou None.

        Exige que a coluna exista e seja numerica (numero/decimal). Colunas de
        texto/categoria/identificador nao fazem sentido em estatistica.
        """
        tabela_obj = self._catalog.tabela(self._desqualificar(tabela))
        if tabela_obj is None:
            return None
        col = self._catalog.coluna_por_canonico(tabela_obj.nome, coluna)
        if col is None or col.tipo not in TIPOS_NUMERICOS:
            return None
        return tabela_obj, col

    def estatisticas(self, tabela: str, coluna: str) -> dict:
        """Calcula estatisticas descritivas de uma coluna numerica.

        Retorna contagem, minimo, maximo, media, desvio padrao e quartis
        (q1/mediana/q3). Use para perguntas sobre distribuicao, dispersao,
        media, maior/menor valor ou variacao (ex.: "qual a media dos valores?",
        "como os valores estao distribuidos?"). NAO monte SQL de estatistica
        manualmente: use esta tool.
        """
        resolvido = self._coluna_numerica(tabela, coluna)
        if resolvido is None:
            raise ModelRetry(
                f"Coluna {coluna!r} nao e numerica ou nao existe na tabela "
                f"{tabela!r}. Consulte o esquema() para ver as colunas "
                "numericas (tipo numero/decimal)."
            )
        tabela_obj, _ = resolvido
        qualificado = tabela_obj.nome_qualificado
        sql = (
            f'SELECT COUNT(*) FILTER (WHERE "{coluna}" IS NOT NULL), '
            f'MIN("{coluna}"), MAX("{coluna}"), AVG("{coluna}"), STDDEV("{coluna}"), '
            f'quantile_cont("{coluna}", 0.25), quantile_cont("{coluna}", 0.5), '
            f'quantile_cont("{coluna}", 0.75) '
            f'FROM {qualificado}'
        )
        try:
            linhas = self._cliente.execute(sql).linhas
        except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
            raise ModelRetry(f"Erro ao calcular estatisticas: {exc}") from exc
        if not linhas:
            raise ModelRetry("Nenhum dado para calcular as estatisticas.")
        linha = linhas[0]
        if len(linha) < 8:
            raise ModelRetry(
                "Resultado inesperado ao calcular estatisticas "
                f"(esperava 8 valores, obteve {len(linha)}). Tente novamente."
            )
        n, minimo, maximo, media, dp, q1, mediana, q3 = linha[:8]

        def _num(v):
            return round(v, 2) if v is not None else None

        return {
            "tabela": qualificado,
            "coluna": coluna,
            "estatisticas": {
                "contagem_nao_nulos": n,
                "min": _num(minimo),
                "max": _num(maximo),
                "media": _num(media),
                "desvio_padrao": _num(dp),
                "q1": _num(q1),
                "mediana": _num(mediana),
                "q3": _num(q3),
            },
        }

    def detectar_outliers(self, tabela: str, coluna: str, desvios: int = 3) -> dict:
        """Identifica valores fora do padrao (outliers) em coluna numerica.

        Metodo deterministico: media +- N desvios padrao (default 3). Retorna a
        media, o desvio, os limites do intervalo aceitavel e as linhas que fogem
        dele (com chave/data/empresa/uf quando existirem). Use para perguntas
        como "nota fiscal com valor fora do padrao", "valor muito acima/abaixo
        da media", "anomalias", "discrepancia".
        """
        desvios = int(desvios)
        if desvios < 1:
            desvios = 1
        resolvido = self._coluna_numerica(tabela, coluna)
        if resolvido is None:
            raise ModelRetry(
                f"Coluna {coluna!r} nao e numerica ou nao existe na tabela "
                f"{tabela!r}. Consulte o esquema() para ver as colunas "
                "numericas (tipo numero/decimal)."
            )
        tabela_obj, _ = resolvido
        qualificado = tabela_obj.nome_qualificado

        # Colunas que ajudam a identificar a linha (chave, data, empresa, uf).
        candidatas = {
            "chave_acesso", "data_emissao", "razao_social_emitente",
            "uf_emitente", "nome_destinatario", "quantidade", "valor_total",
        }
        extras = [
            c.canonico
            for c in tabela_obj.colunas
            if c.canonico in candidatas and c.canonico != coluna
        ]
        projecao = ", ".join(f'"{c}"' for c in extras)
        projecao = f"{projecao}, " if projecao else ""

        sql = (
            f'WITH stats AS ('
            f'SELECT AVG("{coluna}") AS m, STDDEV("{coluna}") AS d FROM {qualificado}) '
            f'SELECT {projecao}"{coluna}" FROM {qualificado}, stats '
            f'WHERE "{coluna}" IS NOT NULL AND d IS NOT NULL AND d > 0 '
            f'AND ("{coluna}" > m + {desvios} * d OR "{coluna}" < m - {desvios} * d) '
            f'ORDER BY "{coluna}" DESC'
        )
        try:
            linhas = self._cliente.execute(sql).linhas
        except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
            raise ModelRetry(f"Erro ao detectar outliers: {exc}") from exc
        total = len(linhas)
        linhas = linhas[:MAX_ROWS]
        colunas_ret = extras + [coluna] if extras else [coluna]
        # Fallback deterministico do agente: se o LLM esquecer de anexar as
        # linhas, o pipeline reusa este resultado.
        self._ultimo_resultado = {"colunas": colunas_ret, "linhas": linhas}

        try:
            linhas_stats = self._cliente.execute(
                f'SELECT AVG("{coluna}"), STDDEV("{coluna}") FROM {qualificado}'
            ).linhas
        except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
            raise ModelRetry(f"Erro ao detectar outliers: {exc}") from exc
        if not linhas_stats or len(linhas_stats[0]) < 2:
            raise ModelRetry("Nenhum dado para detectar outliers.")
        media, dp = linhas_stats[0][0], linhas_stats[0][1]
        limite_sup = media + desvios * dp if media is not None and dp is not None else None
        limite_inf = media - desvios * dp if media is not None and dp is not None else None

        def _num(v):
            return round(v, 2) if v is not None else None

        return {
            "tabela": qualificado,
            "coluna": coluna,
            "metodo": f"media +- {desvios} desvio(s) padrao",
            "media": _num(media),
            "desvio_padrao": _num(dp),
            "limite_inferior": _num(limite_inf),
            "limite_superior": _num(limite_sup),
            "colunas": colunas_ret,
            "linhas": linhas,
            "total_outliers": total,
            "truncado": total > MAX_ROWS,
        }

    def resumo_financeiro(self) -> dict:
        """Calcula totais GERAIS do dataset (notas e itens) de forma deterministica.

        Retorna o total de notas (COUNT DISTINCT da chave), o periodo coberto e
        a soma de cada coluna numerica agregavel do cabecalho (ex.:
        valor_nota_fiscal) e dos itens. Use para perguntas sobre total/quantidade
        de notas, valor total do periodo ou numero de itens — nunca monte esse
        SQL manualmente. NAO use quando a pergunta tiver filtros (periodo,
        empresa, estado): nesse caso use consultar() com SQL e WHERE.
        """
        tabelas = self._catalog.tabelas
        cabecalho = next(
            (t for t in tabelas if t.granularidade == "nota"), tabelas[0] if tabelas else None
        )
        if cabecalho is None:
            raise ModelRetry(
                "Nenhuma tabela de notas no catalogo para calcular totais."
            )
        itens = next((t for t in tabelas if t.granularidade == "item"), None)
        qualificado = cabecalho.nome_qualificado

        def _num(v):
            return round(v, 2) if v is not None else None

        try:
            chaves = [
                c.canonico
                for c in cabecalho.colunas
                if c.tipo in TIPOS_IDENTIFICADOR
            ]
            chave = next((c for c in chaves if "chave" in c), chaves[0] if chaves else None)
            if chave:
                total_notas = self._cliente.execute(
                    f'SELECT COUNT(DISTINCT "{chave}") FROM {qualificado}'
                ).linhas[0][0]
            else:
                total_notas = self._cliente.execute(
                    f"SELECT COUNT(*) FROM {qualificado}"
                ).linhas[0][0]

            periodo: dict[str, str | None] = {}
            datas = [c.canonico for c in cabecalho.colunas if c.tipo in TIPOS_TEMPORAIS]
            if datas:
                d = datas[0]
                linha = self._cliente.execute(
                    f'SELECT MIN("{d}"), MAX("{d}") FROM {qualificado}'
                ).linhas[0]
                periodo = {"inicio": linha[0], "fim": linha[1]}

            valores_cabecalho = {}
            for c in cabecalho.colunas:
                if c.tipo in TIPOS_NUMERICOS:
                    v = self._cliente.execute(
                        f'SELECT SUM("{c.canonico}") FROM {qualificado}'
                    ).linhas[0][0]
                    valores_cabecalho[c.canonico] = _num(v)
        except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
            raise ModelRetry(f"Erro ao calcular o resumo financeiro: {exc}") from exc

        resumo: dict = {
            "tabela": qualificado,
            "metodo": "totais gerais do dataset (sem filtros)",
            "total_notas": total_notas,
            "periodo": periodo,
            "valores_cabecalho": valores_cabecalho,
        }
        if itens is not None:
            qualificado_itens = itens.nome_qualificado
            try:
                total_itens = self._cliente.execute(
                    f"SELECT COUNT(*) FROM {qualificado_itens}"
                ).linhas[0][0]
                valores_itens = {}
                for c in itens.colunas:
                    if c.tipo in TIPOS_NUMERICOS:
                        v = self._cliente.execute(
                            f'SELECT SUM("{c.canonico}") FROM {qualificado_itens}'
                        ).linhas[0][0]
                        valores_itens[c.canonico] = _num(v)
            except Exception as exc:  # noqa: BLE001 - ModelRetry dispara o retry do framework
                raise ModelRetry(
                    f"Erro ao calcular os totais dos itens: {exc}"
                ) from exc
            resumo.update(
                {
                    "tabela_itens": qualificado_itens,
                    "total_itens": total_itens,
                    "valores_itens": valores_itens,
                }
            )
        # Guarda para o agente conferir os numeros citados na resposta e para a
        # checagem anti-alucinacao saber quais valores vieram de uma tool.
        self._ultimo_resumo = resumo
        return resumo

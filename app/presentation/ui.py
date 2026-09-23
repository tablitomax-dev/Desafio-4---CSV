"""Interface Streamlit: Fiscal AI — chat analitico de notas fiscais (CSV).

Layout premium Apple-like: cabecalho compacto, sidebar de dados, historico de
conversa com graficos/tabelas/indicadores e campo de pergunta fixo no rodape.
"""

from __future__ import annotations

import io
from datetime import datetime

import streamlit as st

from app.catalog.catalog import Catalog
from app.dataset.builder import DatasetBuilder
from app.dataset.context import DatasetContext
from app.dataset.dataset_publisher import DatasetPublisher
from app.presentation import filtros as filtros_mod
from app.presentation.filtros import ColunasFiltro, Filtros
from app.presentation.metricas import calcular as calcular_metricas
from app.presentation.renderers import (
    formatar_moeda,
    formatar_numero,
    formatar_tabela,
    grafico_rapido_tabela,
    render_grafico,
    render_tabela,
    render_texto,
)
from app.presentation.styles import aplicar_css

# Perguntas de exemplo (tela inicial / sugestoes).
_SUGESTOES = [
    "Qual foi o faturamento total?",
    "Mostre as vendas por estado.",
    "Quais produtos tiveram maior valor?",
    "Gere um gráfico das categorias mais vendidas.",
    "Existe alguma nota fiscal com valor fora do padrão?",
]

_ICONE_BRAND = """
<svg width="26" height="26" viewBox="0 0 24 24" fill="none"
     xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle">
  <rect x="4" y="3" width="16" height="18" rx="2.5" fill="#007AFF" fill-opacity="0.15"
        stroke="#007AFF" stroke-width="1.5"/>
  <path d="M8 8h8M8 12h8M8 16h5" stroke="#007AFF" stroke-width="1.6"
        stroke-linecap="round"/>
</svg>
"""


def _carregar_estado() -> None:
    if "dataset_context" not in st.session_state:
        st.session_state.dataset_context = None
    if "historico" not in st.session_state:
        st.session_state.historico = []
    if "metricas" not in st.session_state:
        st.session_state.metricas = None
    if "tema" not in st.session_state:
        st.session_state.tema = "claro"
    if "filtros" not in st.session_state:
        st.session_state.filtros = Filtros()
    if "cols_filtro" not in st.session_state:
        st.session_state.cols_filtro = None
    if "grafico_idx" not in st.session_state:
        st.session_state.grafico_idx = None


def _ctx() -> DatasetContext | None:
    return st.session_state.dataset_context


def _status_header(dataset_carregado: bool) -> tuple[bool, str, str]:
    """Deriva o badge do header a partir do estado atual.

    Retorna (carregado, texto, classe_css). O status so fica verde APOS o
    processamento do arquivo; apenas selecionar o ZIP no uploader nao muda o
    badge (o usuario ainda precisa clicar em 'Processar arquivo').
    """
    if dataset_carregado:
        return True, "Dados carregados", "ok"
    return False, "Nenhum arquivo carregado", "warn"


def _aviso_sessao_reiniciada(
    dataset_carregado: bool, arquivo_presente: bool, carga_anterior: bool
) -> bool:
    """True quando a sessao foi reiniciada apos um carregamento anterior.

    O marcador `carga_anterior` sobrevive ao reinicio (fica na URL), entao so
    exibimos o aviso quando realmente houve dados antes e eles se perderam.
    """
    return not dataset_carregado and not arquivo_presente and carga_anterior


def _render_header() -> None:
    escuro = st.session_state.tema == "escuro"
    carregado, status, cls = _status_header(_ctx() is not None)

    c_brand, c_ops = st.columns([4, 1], vertical_alignment="center")
    with c_brand:
        st.markdown(
            f"""
            <div class="app-header">
              <span class="brand-icon">{_ICONE_BRAND}</span>
              <div>
                <p class="brand-title">Fiscal AI</p>
                <p class="brand-desc">Converse com seus dados fiscais</p>
              </div>
              <span class="status-badge {cls}"><span class="dot"></span>{status}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_ops:
        icone_tema = ":material/light_mode:" if escuro else ":material/dark_mode:"
        if st.button(icone_tema, key="tema_btn", help="Alternar tema claro/escuro"):
            st.session_state.tema = "escuro" if not escuro else "claro"
            st.rerun()
        with st.popover(":material/more_vert:", help="Mais opções"):
            if st.button(
                "Limpar conversa", icon=":material/delete_sweep:", use_container_width=True
            ):
                st.session_state.historico = []
                st.rerun()
            if st.button("Nova análise", icon=":material/refresh:", use_container_width=True):
                st.session_state.historico = []
                st.session_state.metricas = None
                st.rerun()
            st.download_button(
                "Exportar análise (.txt)",
                data=_gerar_exportacao().encode("utf-8"),
                file_name="analise_fiscal.txt",
                mime="text/plain",
                icon=":material/file_download:",
                use_container_width=True,
                key="export_tudo",
            )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### :material/upload_file: Carregar dados")
        arquivo = st.file_uploader(
            "ZIP com os arquivos CSV", type=["zip"], key="zip", label_visibility="collapsed"
        )
        if arquivo is not None:
            if st.button("Processar arquivo", type="primary", use_container_width=True):
                try:
                    buf = io.BytesIO(arquivo.read())
                    resultado = DatasetBuilder().construir(buf)
                    if not resultado.ok:
                        msgs = "; ".join(i.mensagem for i in resultado.errors)
                        st.error(f"Falha ao processar: {msgs}")
                    else:
                        novo = resultado.dataset
                        # Troca atomica do contexto inteiro (fecha a conexao anterior).
                        st.session_state.dataset_context = DatasetPublisher().trocar_ativo(
                            _ctx(), novo
                        )
                        st.session_state.historico = []
                        st.session_state.filtros = Filtros()
                        st.session_state.cols_filtro = filtros_mod.detectar(novo.catalog)
                        st.session_state.grafico_idx = None
                        st.session_state.metricas = calcular_metricas(
                            novo.client, novo.catalog
                        )
                        # Marcador persistente na URL: sobrevive a refresh/reinicio
                        # e permite avisar o usuario quando a sessao foi reiniciada.
                        st.query_params["fiscalai"] = "carregado"
                        st.toast("Dados carregados com sucesso!", icon=":material/check_circle:")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Falha ao processar: {exc}")

        _render_info_arquivo()
        _render_filtros()

        st.divider()
        if st.button("Limpar conversa", icon=":material/chat_bubble_outline:",
                     use_container_width=True):
            st.session_state.historico = []
            st.rerun()


def _recalcular_metricas() -> None:
    ctx = _ctx()
    if ctx is None:
        return
    cols = st.session_state.cols_filtro
    where = filtros_mod.clausula_where(cols, st.session_state.filtros) if cols else ""
    st.session_state.metricas = calcular_metricas(
        ctx.client, ctx.catalog, where=where
    )


def _render_filtros() -> None:
    ctx = _ctx()
    if ctx is None:
        return
    cols: ColunasFiltro | None = st.session_state.cols_filtro
    filtros = st.session_state.filtros
    if cols is None:
        return
    cliente = ctx.client
    with st.expander("Filtros", icon=":material/filter_list:"):
        if cols.uf:
            try:
                opcoes = filtros_mod.opcoes(cliente, cols.tabela, cols.uf)
            except Exception:  # noqa: BLE001
                opcoes = []
            if opcoes:
                filtros.uf = st.multiselect(
                    "UF", opcoes, default=list(filtros.uf), key="f_uf"
                )
        if cols.natureza:
            try:
                opcoes = filtros_mod.opcoes(cliente, cols.tabela, cols.natureza)
            except Exception:  # noqa: BLE001
                opcoes = []
            if opcoes:
                filtros.natureza = st.multiselect(
                    "Natureza da operação", opcoes,
                    default=list(filtros.natureza), key="f_nat",
                )
        if cols.data:
            try:
                rango = filtros_mod.intervalo(cliente, cols.tabela, cols.data)
            except Exception:  # noqa: BLE001
                rango = None
            if rango and rango[0] != rango[1]:
                d_ini_db = datetime.strptime(rango[0], "%Y-%m-%d").date()
                d_fim_db = datetime.strptime(rango[1], "%Y-%m-%d").date()
                ini_atual = (
                    datetime.strptime(filtros.inicio, "%Y-%m-%d").date()
                    if filtros.inicio else d_ini_db
                )
                fim_atual = (
                    datetime.strptime(filtros.fim, "%Y-%m-%d").date()
                    if filtros.fim else d_fim_db
                )
                dias = st.date_input(
                    "Período",
                    value=(ini_atual, fim_atual),
                    min_value=d_ini_db, max_value=d_fim_db, key="f_data",
                )
                if isinstance(dias, (tuple, list)) and len(dias) == 2:
                    filtros.inicio = dias[0].isoformat()
                    filtros.fim = dias[1].isoformat()
            else:
                filtros.inicio = filtros.fim = None

        if filtros.ativo():
            st.caption(f"**Filtros ativos:** {filtros_mod.descricao(filtros)}")
            if st.button("Limpar filtros", icon=":material/filter_alt_off:",
                         use_container_width=True):
                filtros.limpar()
                st.rerun()
    _recalcular_metricas()



def _render_info_arquivo() -> None:
    ctx = _ctx()
    if ctx is None:
        return
    catalog: Catalog = ctx.catalog
    st.markdown("### :material/info: Arquivo")
    cliente = ctx.client
    linhas_total = 0
    for tabela in catalog.tabelas:
        try:
            n = cliente.execute(f"SELECT COUNT(*) FROM {tabela.nome_qualificado}").linhas[0][0]
        except Exception:  # noqa: BLE001
            n = 0
        linhas_total += n
        st.caption(f"- **{tabela.nome}**: {n} registros · {len(tabela.colunas)} colunas")
    st.caption(f"**Total de registros:** {formatar_numero(linhas_total)}")


def _render_metricas() -> None:
    m = st.session_state.metricas
    if m is None:
        return

    def card(rotulo: str, valor: str) -> str:
        return (
            f'<div class="metric-card"><p class="metric-label">{rotulo}</p>'
            f'<p class="metric-value">{valor}</p></div>'
        )

    periodo = (
        f"{m.inicio} – {m.fim}" if (m.inicio and m.fim) else (m.inicio or m.fim or "—")
    )
    cards = [
        card("Valor total", _valor_calc(formatar_moeda, m.total)),
        card("Notas fiscais", _valor_calc(formatar_numero, m.quantidade)),
        card("Ticket médio", _valor_calc(formatar_moeda, m.ticket_medio)),
        card("Maior nota", _valor_calc(formatar_moeda, m.maior_nota)),
        card("Período", periodo),
    ]
    st.markdown(f'<div class="metric-row">{"".join(cards)}</div>', unsafe_allow_html=True)
    if m.linhas_cabecalho is not None or m.linhas_itens is not None:
        partes = []
        if m.linhas_cabecalho is not None:
            partes.append(f"**{formatar_numero(m.linhas_cabecalho)}** linhas de cabeçalho")
        if m.linhas_itens is not None:
            partes.append(f"**{formatar_numero(m.linhas_itens)}** linhas de itens")
        st.caption(" · ".join(partes))


def _valor_calc(fmt, v) -> str:
    return fmt(v) if v is not None else "—"


def _render_boas_vindas() -> None:
    st.markdown(
        """
        <div class="welcome">
          <h2>Converse com seus dados fiscais</h2>
          <p>Carregue um arquivo de notas fiscais (CSV) na barra lateral e faça
             perguntas em linguagem natural. O Fiscal AI responde com precisão e
             gera tabelas, indicadores e gráficos sob demanda.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _acoes_resposta(resposta, chave: str) -> None:
    if resposta.linhas:
        df = render_tabela(resposta)
        st.download_button(
            "Baixar tabela (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="analise_fiscal.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"dl_{chave}",
        )


def _desc_filtros() -> str:
    """Descricao legivel dos filtros ativos (para injetar no agente)."""
    if st.session_state.filtros.ativo():
        return filtros_mod.descricao(st.session_state.filtros)
    return ""


def _gerar_exportacao() -> str:
    """Monta o texto da analise completa (metricas + conversa) para export."""
    m = st.session_state.metricas
    blocos: list[str] = [f"Fiscal AI — análise {datetime.now():%d/%m/%Y %H:%M}", ""]
    if m is not None:
        blocos.append("Métricas:")
        blocos.append(f"- Valor total: {formatar_moeda(m.total) if m.total else '—'}")
        blocos.append(
            f"- Notas fiscais: {formatar_numero(m.quantidade) if m.quantidade else '—'}"
        )
        blocos.append(
            f"- Ticket médio: {formatar_moeda(m.ticket_medio) if m.ticket_medio else '—'}"
        )
        blocos.append(
            f"- Maior nota: {formatar_moeda(m.maior_nota) if m.maior_nota else '—'}"
        )
        periodo = (str(m.inicio), str(m.fim))
        blocos.append(
            f"- Período: {periodo[0] or '—'} a {periodo[1] or '—'}"
        )
        blocos.append("")
    for pergunta, resposta in st.session_state.historico:
        blocos.append(f"Q: {pergunta}")
        if resposta.output_kind == "text":
            blocos.append(f"A: {resposta.texto or ''}")
        else:
            df = render_tabela(resposta)
            blocos.append(f"A (tabela, {len(df)} linhas):")
            blocos.append(df.to_csv(index=False))
        blocos.append("")
    return "\n".join(blocos)


def _exibir_resposta(resposta, chave: str) -> None:
    if resposta.output_kind == "text":
        st.write(render_texto(resposta))
    elif resposta.output_kind == "table":
        if resposta.texto:
            st.caption(resposta.texto)
        st.dataframe(formatar_tabela(resposta), width="stretch")
        _acoes_resposta(resposta, chave)
    else:
        try:
            st.plotly_chart(render_grafico(resposta), width="stretch")
            _acoes_resposta(resposta, chave)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Não consegui exibir o gráfico: {exc}")

    if resposta.colunas:
        st.markdown(
            f'<div class="resp-footer">Colunas analisadas: '
            f'<b>{", ".join(resposta.colunas)}</b></div>',
            unsafe_allow_html=True,
        )


def _eh_erro(resposta) -> bool:
    return (
        resposta.output_kind == "text"
        and resposta.texto is not None
        and resposta.texto.strip().lower().startswith("ops")
    )


def _renderizar_historico() -> None:
    for idx, (pergunta, resposta) in enumerate(st.session_state.historico):
        with st.chat_message("user", avatar=":material/person:"):
            st.write(pergunta)
        with st.chat_message("assistant", avatar=":material/support_agent:"):
            _exibir_resposta(resposta, chave=f"h{idx}")
            if resposta.output_kind == "table":
                if st.button(
                    "Gráfico rápido", icon=":material/bar_chart:", key=f"gc_{idx}"
                ):
                    st.session_state.grafico_idx = (
                        idx if st.session_state.grafico_idx != idx else None
                    )
                    st.rerun()
                if st.session_state.grafico_idx == idx:
                    figura = grafico_rapido_tabela(resposta)
                    if figura is not None:
                        st.plotly_chart(figura, width="stretch")
            if _eh_erro(resposta):
                if st.button("Regenerar", icon=":material/refresh:", key=f"rg_{idx}"):
                    nova = _ctx().pipeline.perguntar(
                        pergunta,
                        filtros=_desc_filtros(),
                        historico=st.session_state.historico,
                    )
                    st.session_state.historico[idx] = (pergunta, nova)
                    st.rerun()


def _responder(pergunta: str) -> None:
    with st.chat_message("user", avatar=":material/person:"):
        st.write(pergunta)
    with st.chat_message("assistant", avatar=":material/support_agent:"):
        with st.spinner("Analisando seus dados..."):
            resposta = _ctx().pipeline.perguntar(
                pergunta,
                filtros=_desc_filtros(),
                historico=st.session_state.historico,
            )
        _exibir_resposta(resposta, chave=f"n{len(st.session_state.historico)}")
    st.session_state.historico.append((pergunta, resposta))


def _renderizar_sugestoes() -> str | None:
    # A sugestao selecionada e consumida via callback em chave separada, para
    # nao tentar modificar a chave do widget (st.pills) apos sua instanciacao.
    if "sugestao_pendente" not in st.session_state:
        st.session_state.sugestao_pendente = None

    def _consumir() -> None:
        st.session_state.sugestao_pendente = st.session_state.sugestoes

    st.pills(
        "Sugestão de perguntas",
        list(_SUGESTOES),
        key="sugestoes",
        on_change=_consumir,
    )
    pendente = st.session_state.sugestao_pendente
    st.session_state.sugestao_pendente = None
    return pendente


def main() -> None:
    st.set_page_config(
        page_title="Fiscal AI", page_icon=":material/document_scanner:", layout="wide"
    )
    _carregar_estado()
    aplicar_css()

    _render_header()
    _render_sidebar()

    if _ctx() is None:
        _render_boas_vindas()
        sugestao = _renderizar_sugestoes()
        if sugestao:
            st.info("Carregue um arquivo de notas fiscais na barra lateral para começar.")
        if _aviso_sessao_reiniciada(
            False,
            st.session_state.get("zip") is not None,
            st.query_params.get("fiscalai") == "carregado",
        ):
            st.warning(
                "Sua sessão anterior tinha dados carregados, mas a sessão foi "
                "reiniciada (recarregar a página ou reiniciar o servidor limpa o "
                "estado). Recarregue o arquivo ZIP na barra lateral para continuar."
            )
        # Campo de chat sempre visivel (desabilitado ate carregar os dados).
        st.chat_input(
            "Carregue um arquivo de notas fiscais para começar...", disabled=True
        )
        return

    _render_metricas()
    _renderizar_historico()
    sugestao = _renderizar_sugestoes()
    if sugestao:
        _responder(sugestao)

    pergunta = st.chat_input(
        "Pergunte sobre seus dados fiscais...", submit_mode="disable"
    )
    if pergunta:
        _responder(pergunta)


main() if __name__ == "__main__" else None

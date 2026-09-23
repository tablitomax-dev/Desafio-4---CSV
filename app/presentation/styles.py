"""Estilizacao da UI: tema premium Apple-like, com modo claro/escuro via CSS.

O tema de startup do Streamlit e claro (config.toml). O modo escuro e aplicado
em runtime injetando CSS: alem das variaveis proprias, SOBRESCREVEMOS as
variaveis nativas de tema do Streamlit (--background-color, --text-color,
--secondary-background-color, --primary-color) e o `color-scheme`, para que
botões, inputs, sidebar e popover acompanhem o modo escuro.
"""

from __future__ import annotations

import streamlit as st

CLARO = {
    "fundo": "#F5F5F7",
    "card": "#FFFFFF",
    "texto": "#1D1D1F",
    "texto_sec": "#6E6E73",
    "acento": "#007AFF",
    "borda": "#E5E5EA",
    "sucesso": "#34C759",
    "erro": "#FF3B30",
    "chat_user": "#007AFF",
    "chat_user_texto": "#FFFFFF",
    "chat_ai": "#FFFFFF",
    "header_bg": "rgba(255,255,255,0.85)",
    "scheme": "light",
}

ESCURO = {
    "fundo": "#0D0D0F",
    "card": "#1C1C1E",
    "texto": "#F2F2F7",
    "texto_sec": "#A1A1A6",
    "acento": "#0A84FF",
    "borda": "#2C2C2E",
    "sucesso": "#30D158",
    "erro": "#FF453A",
    "chat_user": "#0A84FF",
    "chat_user_texto": "#FFFFFF",
    "chat_ai": "#1C1C1E",
    "header_bg": "rgba(13,13,15,0.85)",
    "scheme": "dark",
}


def _css(t: dict) -> str:
    return f"""
    <style>
    :root, html, [data-testid="stAppViewContainer"], .stApp {{
        /* Variaveis proprias */
        --fundo: {t['fundo']};
        --card: {t['card']};
        --texto: {t['texto']};
        --texto-sec: {t['texto_sec']};
        --acento: {t['acento']};
        --borda: {t['borda']};
        --sucesso: {t['sucesso']};
        --erro: {t['erro']};
        --chat-user: {t['chat_user']};
        --chat-user-texto: {t['chat_user_texto']};
        --chat-ai: {t['chat_ai']};
        --header-bg: {t['header_bg']};
        --raio: 14px;
        --sombra: 0 1px 3px rgba(0,0,0,0.06), 0 4px 14px rgba(0,0,0,0.05);

        /* Sobrescreve o tema nativo do Streamlit (faz widgets seguirem o modo) */
        color-scheme: {t['scheme']};
        --primary-color: var(--acento);
        --background-color: var(--fundo);
        --secondary-background-color: var(--card);
        --text-color: var(--texto);
        --heading-color: var(--texto);
        --border-color: var(--borda);
    }}

    /* Fundo geral e fonte do sistema */
    .stApp,
    [data-testid="stAppViewContainer"] {{
        background: var(--fundo);
        color: var(--texto);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     "Helvetica Neue", Arial, sans-serif;
    }}
    h1, h2, h3, h4, .stMarkdown {{ color: var(--texto); }}

    /* Centraliza e limita a largura do conteudo principal (~1200px) */
    .block-container,
    [data-testid="stMainBlockContainer"] {{
        max-width: 1200px;
        margin: 0 auto;
        padding-top: 3.5rem;
        padding-bottom: 2rem;
    }}

    /* Sidebar: painel neutro, borda sutil */
    [data-testid="stSidebar"] {{
        background: var(--card);
        border-right: 1px solid var(--borda);
    }}
    [data-testid="stSidebar"] * {{ color: var(--texto); }}
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        color: var(--texto);
    }}

    /* Cabecalho premium: fundo translucido, borda inferior sutil */
    .app-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 20px;
        background: var(--header-bg);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid var(--borda);
        border-radius: var(--raio);
        margin-bottom: 18px;
    }}
    .app-header .brand-icon {{
        font-size: 26px;
        color: var(--acento);
        line-height: 1;
    }}
    .app-header .brand-title {{
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--texto);
        margin: 0;
        letter-spacing: -0.01em;
    }}
    .app-header .brand-desc {{
        font-size: 0.85rem;
        color: var(--texto-sec);
        margin: 0;
    }}

    /* Badge de status do arquivo no cabecalho */
    .status-badge {{
        margin-left: auto;
        font-size: 0.78rem;
        font-weight: 500;
        padding: 5px 12px;
        border-radius: 999px;
        background: var(--borda);
        color: var(--texto);
        white-space: nowrap;
    }}
    .status-badge.ok {{
        background: rgba(48,209,88,0.16);
        color: var(--sucesso);
    }}
    .status-badge.warn {{
        background: rgba(255,159,10,0.16);
        color: #FF9F0A;
    }}
    .status-badge .dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        background: currentColor;
    }}

    /* Baloes de chat */
    [data-testid="stChatMessage"] {{
        background: transparent;
    }}
    [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {{
        color: var(--texto);
    }}
    [data-testid="stChatMessage"][aria-label*="assistant"] {{
        background: var(--chat-ai);
        border-radius: 16px;
        padding: 12px 14px;
        box-shadow: var(--sombra);
    }}
    [data-testid="stChatMessage"][aria-label*="user"] [data-testid="stChatMessageContent"] {{
        color: var(--texto);
    }}

    /* Campo de chat fixo na parte inferior */
    [data-testid="stChatInput"] {{
        background: var(--card);
        border: 1px solid var(--borda);
        border-radius: 12px;
        box-shadow: var(--sombra);
        color: var(--texto);
    }}
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input {{ color: var(--texto); }}

    /* Botões nativos acompanham o modo (sem depender do tema fixo) */
    .stButton > button,
    .stDownloadButton > button {{
        background: var(--card);
        color: var(--texto);
        border: 1px solid var(--borda);
        border-radius: 10px;
    }}
    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        border-color: var(--acento);
    }}
    .stButton > button[kind="primary"] {{
        background: var(--acento);
        border-color: var(--acento);
        color: #fff;
    }}

    /* Popover / inputs */
    [data-testid="stPopover"] > button {{
        background: var(--card);
        border: 1px solid var(--borda);
        border-radius: 10px;
        color: var(--texto);
    }}

    /* Cards de metrica */
    .metric-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 14px 0 18px;
    }}
    .metric-card {{
        flex: 1 1 160px;
        min-width: 150px;
        background: var(--card);
        border: 1px solid var(--borda);
        border-radius: var(--raio);
        padding: 14px 16px;
        box-shadow: var(--sombra);
    }}
    .metric-card .metric-label {{
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--texto-sec);
        margin: 0;
    }}
    .metric-card .metric-value {{
        font-size: 1.35rem;
        font-weight: 600;
        color: var(--texto);
        margin: 4px 0 0;
        letter-spacing: -0.01em;
    }}

    /* Boas-vindas */
    .welcome {{
        text-align: center;
        padding: 48px 16px 24px;
    }}
    .welcome h2 {{
        font-size: 1.7rem;
        font-weight: 600;
        color: var(--texto);
        margin: 0 0 8px;
        letter-spacing: -0.02em;
    }}
    .welcome p {{
        color: var(--texto-sec);
        font-size: 1rem;
        margin: 0;
    }}

    /* Rodape das respostas (colunas usadas) */
    .resp-footer {{
        font-size: 0.8rem;
        color: var(--texto-sec);
        margin-top: 10px;
        border-top: 1px solid var(--borda);
        padding-top: 8px;
    }}

    /* Acessibilidade: foco visivel e suave */
    :focus-visible {{
        outline: 2px solid var(--acento);
        outline-offset: 2px;
    }}

    /* Transicoes suaves, sem excesso de animacao */
    [data-testid="stChatMessage"], .metric-card, .app-header,
    .stButton > button, .stDownloadButton > button {{
        transition: background .2s ease, color .2s ease, box-shadow .2s ease,
                    border-color .2s ease;
    }}

    @media (max-width: 768px) {{
        .metric-card {{ flex: 1 1 45%; }}
        .app-header {{ padding: 10px 14px; }}
        .welcome {{ padding: 28px 10px 16px; }}
    }}
    </style>
    """


def aplicar_css() -> None:
    """Aplica o CSS com base no modo atual (claro/escuro no session_state)."""
    tema = ESCURO if st.session_state.get("tema") == "escuro" else CLARO
    st.markdown(_css(tema), unsafe_allow_html=True)

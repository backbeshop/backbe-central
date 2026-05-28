import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date as dt_date
import calendar as cal_lib
import sqlite3, math, json
from pathlib import Path

from db import init_db, get_conn, rows_to_list, row_to_dict
from api_ns import (fetch_all_orders, fetch_all_customers, compute_sales,
                    compute_customers, fetch_all_products, parse_inventory)
from nubank_parser import parse_nubank_pdf
from notion_api import get_week_content, notion_ok, PLATAFORMA_ICON
from ics_export import build_ics, gcal_link


def _calc_preco_metro(t: dict) -> float:
    if t["unidade"] == "metro" and t["preco_metro"]:
        return float(t["preco_metro"])
    elif t["unidade"] == "kg" and t["preco_kg"] and t["peso_gsm"] and t["largura_m"]:
        return float(t["preco_kg"]) * float(t["peso_gsm"]) * float(t["largura_m"]) / 1000.0
    return 0.0


def _recalc_relatorio(conn, rel_id: int):
    itens = conn.execute(
        "SELECT quantidade, subtotal FROM relatorio_mae_itens WHERE relatorio_id=?", (rel_id,)
    ).fetchall()
    total_pecas = sum(i["quantidade"] for i in itens)
    total_costura = sum(i["subtotal"] for i in itens)
    conn.execute(
        "UPDATE relatorio_mae SET total_pecas=?, total_costura=? WHERE id=?",
        (total_pecas, total_costura, rel_id)
    )


def _brl(s) -> float:
    try:
        return float(str(s).replace("R$", "").replace("%", "").replace(".", "").replace(",", ".").strip())
    except Exception:
        return 0.0


# ── Setup ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Backbe Central",
    page_icon="b",
    layout="wide",
    initial_sidebar_state="expanded",
)

_FAVICON_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>
<text y='88' x='8' font-size='96' font-family='Georgia,serif' fill='%2387CEEB'
  font-style='italic' font-weight='bold'>b</text></svg>"""
st.markdown(
    f'<link rel="icon" type="image/svg+xml" '
    f'href="data:image/svg+xml,{_FAVICON_SVG}">',
    unsafe_allow_html=True,
)

NAVY      = "#111827"
PINK      = "#c96ba0"
GOLD      = "#b8860b"
BG        = "#F4F5F7"
SIDEBAR   = "#FFFFFF"
PURPLE    = "#7C3AED"

init_db()

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap');

/* ── Reset + Base ───────────────────────────────────────────── */
html, body, [class*="css"], .stApp, button, input, select, textarea {{
    font-family: 'DM Sans', -apple-system, sans-serif !important;
}}
.stApp {{ background: #F4F6FB !important; }}
.main .block-container {{
    padding: 1.4rem 1.6rem 3rem !important;
    background: #F4F6FB !important;
    max-width: 1440px;
}}

/* ── Sidebar — largura compacta + glassmorphism ─────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {{
    width: 190px !important;
    min-width: 190px !important;
    max-width: 190px !important;
    background: rgba(255,255,255,0.92) !important;
    backdrop-filter: blur(24px) !important;
    -webkit-backdrop-filter: blur(24px) !important;
    border-right: 1px solid rgba(201,107,160,0.10) !important;
}}
div[data-testid="stSidebarContent"] {{
    background: transparent !important;
    padding: 0 8px !important;
}}

/* ── Nav item label (seção) ─────────────────────────────────── */
.nav-section-label {{
    font-size: 9px; font-weight: 700; color: #C9D0D8;
    text-transform: uppercase; letter-spacing: 0.16em;
    padding: 0 6px; margin: 10px 0 1px 0;
}}

/* ── Nav item ativo (div) ───────────────────────────────────── */
.nav-active {{
    display: flex; align-items: center; gap: 8px;
    padding: 5px 8px 5px 9px;
    background: linear-gradient(90deg, #FDF2F8, #fff8fb);
    border-radius: 8px;
    border-left: 3px solid {PINK};
    margin: 0;
    cursor: default;
}}
.nav-active .nl {{ font-size: 12.5px; font-weight: 700; color: {PINK}; letter-spacing:-0.01em; }}

/* ── Botões nav (inativos) ──────────────────────────────────── */
section[data-testid="stSidebar"] .stButton,
div[data-testid="stSidebarContent"] .stButton {{
    margin: 0 !important;
    width: 100% !important;
}}
section[data-testid="stSidebar"] .stButton > button,
div[data-testid="stSidebarContent"] .stButton > button {{
    background: transparent !important;
    border: 0 !important;
    color: #6B7280 !important;
    border-radius: 8px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    align-items: center !important;
    padding: 5px 8px 5px 10px !important;
    letter-spacing: -0.01em !important;
    width: 100% !important;
    min-height: 0 !important;
    height: auto !important;
    line-height: 1.3 !important;
    transition: background 0.13s ease, color 0.13s ease !important;
}}
section[data-testid="stSidebar"] .stButton > button > div,
div[data-testid="stSidebarContent"] .stButton > button > div {{
    display: flex !important;
    justify-content: flex-start !important;
    align-items: center !important;
    text-align: left !important;
    width: 100% !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover,
div[data-testid="stSidebarContent"] .stButton > button:hover {{
    background: #FDF2F8 !important;
    color: {PINK} !important;
    transform: none !important;
}}
section[data-testid="stSidebar"] .stButton > button p,
div[data-testid="stSidebarContent"] .stButton > button p {{
    text-align: left !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    margin: 0 !important;
    color: inherit !important;
}}
/* ── Botão de ação (Atualizar) ─────────────────────────────── */
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"],
div[data-testid="stSidebarContent"] .stButton > button[data-testid="baseButton-primary"] {{
    background: #FDF2F8 !important;
    border: 1px solid #F9D2E9 !important;
    color: {PINK} !important;
    border-radius: 9px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    text-align: center !important;
    justify-content: center !important;
    padding: 9px 16px !important;
    margin-top: 2px !important;
}}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover,
div[data-testid="stSidebarContent"] .stButton > button[data-testid="baseButton-primary"]:hover {{
    background: #FCE7F3 !important;
    border-color: {PINK} !important;
}}

/* ── Typography ─────────────────────────────────────────────── */
h1 {{ color:{NAVY};font-size:22px !important;font-weight:800 !important;
     margin-bottom:0 !important;letter-spacing:-0.5px !important; }}
h2 {{ color:{NAVY};font-size:16px !important;font-weight:700 !important; }}
h3 {{ color:{NAVY};font-size:14px !important;font-weight:600 !important; }}

/* ── KPI Card pastel ────────────────────────────────────────── */
.kcard {{
    border-radius: 20px;
    padding: 22px 24px 20px;
    border: 1.5px solid transparent;
    position: relative;
    overflow: hidden;
    min-height: 128px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.05);
    transition: box-shadow 0.2s, transform 0.15s;
}}
.kcard:hover {{
    box-shadow: 0 8px 28px rgba(0,0,0,0.10);
    transform: translateY(-1px);
}}
.kcard-label {{
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.09em; margin-bottom: 8px;
}}
.kcard-val {{
    font-size: 34px; font-weight: 800; letter-spacing: -1.5px; line-height: 1;
    color: {NAVY};
}}
.kcard-sub {{
    font-size: 12px; margin-top: 10px; font-weight: 500; color: #6B7280;
}}
.kcard-delta {{
    display: inline-flex; align-items: center; margin-top: 10px;
    border-radius: 8px; padding: 3px 10px;
    font-size: 11px; font-weight: 700;
}}

/* ── Progress bar de meta (sobre fundo pastel) ──────────────── */
.goal-bar-wrap {{ margin-top: 14px; }}
.goal-bar-header {{
    display:flex; justify-content:space-between; align-items:center;
    font-size:11px; font-weight:600; margin-bottom:6px; color:#374151;
}}
.goal-bar-bg {{
    background: rgba(0,0,0,0.08);
    border-radius: 99px; height: 7px;
}}
.goal-bar-fill {{
    border-radius: 99px; height: 7px;
    transition: width 0.6s ease;
}}

/* ── White content card ─────────────────────────────────────── */
.wcard {{
    background: rgba(255,255,255,0.90);
    border-radius: 20px;
    padding: 22px 24px;
    border: 1px solid rgba(255,255,255,0.95);
    box-shadow: 0 2px 16px rgba(0,0,0,0.05);
}}
.wcard-title {{
    font-size: 15px; font-weight: 700; color: {NAVY}; margin-bottom: 4px;
}}
.wcard-sub {{
    font-size: 12px; color: #9CA3AF; font-weight: 400;
}}

/* ── KPI card branco legado ─────────────────────────────────── */
.kpi-card {{
    background: rgba(255,255,255,0.90); border-radius: 20px; padding: 20px 22px 18px;
    border: 1px solid rgba(255,255,255,0.95);
    box-shadow: 0 2px 14px rgba(0,0,0,0.05);
    transition: box-shadow 0.2s, transform 0.15s;
}}
.kpi-card:hover {{ box-shadow: 0 8px 24px rgba(0,0,0,0.09); transform: translateY(-1px); }}
.kpi-accent {{ width:40px; height:5px; border-radius:99px; margin-bottom:16px; }}
.kpi-label  {{ font-size:11px; font-weight:700; color:#9CA3AF; text-transform:uppercase;
               letter-spacing:0.09em; margin-bottom:4px; }}
.kpi-value  {{ font-size:34px; font-weight:800; color:{NAVY}; letter-spacing:-0.04em; line-height:1; }}
.kpi-sub    {{ font-size:12px; margin-top:6px; color:#9CA3AF; font-weight:400; }}

/* ── Progress bar branca (para cards brancos) ───────────────── */
.pbar-bg {{
    background: #F3F4F6; border-radius:99px; height:6px; margin-top:6px;
}}
.pbar-fill {{
    border-radius:99px; height:6px;
    transition: width 0.5s ease;
}}

/* ── Task / item cards ──────────────────────────────────────── */
.task-card {{
    background: white; border-radius: 14px; padding: 16px 18px;
    border: 0; box-shadow: 0 1px 6px rgba(0,0,0,0.05); margin-bottom: 10px;
}}
.task-title {{ font-size:13.5px;font-weight:600;color:{NAVY};line-height:1.4; }}
.task-note  {{ font-size:12px;color:#9CA3AF;margin-top:4px; }}

/* ── Chip tags ──────────────────────────────────────────────── */
.chip        {{ display:inline-flex;align-items:center;padding:3px 9px;
               border-radius:6px;font-size:11px;font-weight:600;letter-spacing:0.01em; }}
.chip-purple {{ background:#EDE9FE;color:#6D28D9; }}
.chip-pink   {{ background:#FCE7F3;color:#9D174D; }}
.chip-orange {{ background:#FFEDD5;color:#9A3412; }}
.chip-green  {{ background:#DCFCE7;color:#166534; }}
.chip-blue   {{ background:#DBEAFE;color:#1E40AF; }}
.chip-yellow {{ background:#FEF9C3;color:#854D0E; }}
.chip-gray   {{ background:#F3F4F6;color:#6B7280; }}

/* ── Badges ─────────────────────────────────────────────────── */
.bb-badge   {{ display:inline-flex;align-items:center;padding:3px 10px;
              border-radius:99px;font-size:11px;font-weight:600; }}
.badge-green  {{ background:#DCFCE7;color:#15803D; }}
.badge-red    {{ background:#FEE2E2;color:#B91C1C; }}
.badge-yellow {{ background:#FEF9C3;color:#92400E; }}
.badge-pink   {{ background:#FCE7F3;color:#9D174D; }}
.badge-blue   {{ background:#DBEAFE;color:#1E40AF; }}
.badge-gray   {{ background:#F3F4F6;color:#6B7280; }}
.badge-purple {{ background:#EDE9FE;color:#6D28D9; }}

/* ── Metrics ─────────────────────────────────────────────────── */
.stMetric {{
    background:white;border-radius:14px;padding:18px 20px !important;
    box-shadow:0 2px 10px rgba(0,0,0,0.06);border:0 !important;
}}
.stMetric label {{ color:#9CA3AF !important;font-size:11px !important;
                   font-weight:700 !important;text-transform:uppercase;letter-spacing:0.09em; }}
[data-testid="stMetricValue"] {{ color:{NAVY} !important;font-size:26px !important;font-weight:800 !important; }}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background:#F0F2F5;border-radius:12px;padding:4px;border:0;gap:2px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius:9px !important;font-weight:500 !important;
    font-size:13px !important;padding:7px 16px !important;color:#6B7280 !important;
}}
.stTabs [aria-selected="true"] {{
    background:white !important;color:{NAVY} !important;
    font-weight:700 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08) !important;
}}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button {{
    border-radius:10px !important;font-weight:600 !important;font-size:13px !important;
    border:0 !important;
}}
.stButton > button[kind="primary"] {{
    background:{PINK} !important;color:white !important;
}}
.stButton > button[kind="secondary"] {{
    border:1px solid #E5E7EB !important;color:{NAVY} !important;
    background:white !important;
}}

/* ── Misc ────────────────────────────────────────────────────── */
.stDataFrame {{ border-radius:14px !important;overflow:hidden !important;
               box-shadow:0 2px 8px rgba(0,0,0,0.05) !important; }}
.stAlert {{ border-radius:12px !important; }}
.streamlit-expanderHeader {{
    border-radius:10px !important;font-weight:600 !important;
    background:white !important;
}}
hr {{ border-color:#E8EAF0 !important; }}

/* ── CRM pills ───────────────────────────────────────────────── */
.pill-vip  {{ background:#FEF9C3;color:#713F12;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-ativo{{ background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-reat {{ background:#FFEDD5;color:#9A3412;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-perd {{ background:#F3F4F6;color:#6B7280;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}

/* ── Input / select / number_input ─────────────────────────── */
.stTextInput input, .stNumberInput input, .stSelectbox [data-baseweb="select"] {{
    border-radius: 10px !important;
    border: 1.5px solid #E5E7EB !important;
    background: white !important;
}}
.stTextInput input:focus, .stNumberInput input:focus {{
    border-color: {PINK} !important;
    box-shadow: 0 0 0 3px rgba(201,107,160,0.15) !important;
}}

/* ── Números nunca quebram linha ─────────────────────────────── */
[data-testid="stMarkdownContainer"] div[style*="font-weight:800"],
[data-testid="stMarkdownContainer"] div[style*="font-weight:900"],
[data-testid="stMarkdownContainer"] div[style*="font-weight: 800"],
[data-testid="stMarkdownContainer"] div[style*="font-weight: 900"] {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}}

/* ── Responsive — Tela estreita (≤ 780px) ──────────────────── */
@media (max-width: 780px) {{
  /* Empilha TUDO em coluna única — sem sobreposição */
  [data-testid="stHorizontalBlock"] {{
    flex-direction: column !important;
    gap: 12px !important;
  }}
  [data-testid="stColumn"] {{
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
    flex: 0 0 100% !important;
  }}
  .main .block-container {{ padding: 0.8rem 0.8rem 2rem !important; max-width: 100% !important; }}
  /* Cards compactos em largura total */
  .kcard {{
    padding: 14px 18px 13px !important;
    min-height: 0 !important;
    border-radius: 16px !important;
  }}
  .kcard-val {{ font-size: 26px !important; letter-spacing: -1px !important; }}
  .kcard-label {{ font-size: 10.5px !important; }}
  .kcard-sub {{ font-size: 11.5px !important; margin-top: 6px !important; }}
  .kcard-delta {{ font-size: 10.5px !important; padding: 2px 8px !important; }}
  .wcard {{ padding: 16px 16px !important; border-radius: 16px !important; }}
  .wcard-title {{ font-size: 13.5px !important; }}
  .kpi-value {{ font-size: 26px !important; }}
  /* Tabs compactas */
  .stTabs [data-baseweb="tab"] {{
    font-size: 12px !important;
    padding: 6px 12px !important;
  }}
  /* Goal bar */
  .goal-bar-header {{ font-size: 10.5px !important; }}
  /* Métricas nativas */
  [data-testid="stMetricValue"] {{ font-size: 24px !important; }}
  h1 {{ font-size: 20px !important; }}
}}
</style>
""", unsafe_allow_html=True)

# ── Navegação via session_state ───────────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "◆ Dashboard"

_NAV = [
    ("VISAO GERAL", [
        ("◆ Dashboard",          "Dashboard"),
        ("▷ Calendario",         "Calendário"),
    ]),
    ("LOJA", [
        ("▦ Produtos",           "Produtos"),
        ("◎ CRM — Clientes",     "CRM — Clientes"),
        ("⊟ Estoque",            "Estoque"),
    ]),
    ("PRODUCAO", [
        ("≋ Tecidos",            "Tecidos"),
        ("⊕ Aviamentos",         "Aviamentos"),
        ("⊞ Ordens de Producao", "Ordens de Producao"),
    ]),
    ("FINANCEIRO", [
        ("▣ Financeiro",         "Financeiro"),
        ("↗ Crescimento",        "Crescimento"),
        ("◉ Relatorio Mae",      "Relatorio Mae"),
        ("⊛ Declaracao MEI",     "Declaracao MEI"),
    ]),
]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown(f"""
<div style="padding:8px 4px 12px 4px">
  <div style="display:flex;align-items:center;gap:8px">
    <div style="width:38px;height:38px;background:white;
                border-radius:11px;display:flex;align-items:center;
                justify-content:center;flex-shrink:0;
                box-shadow:0 2px 10px rgba(135,206,235,0.35);
                border:1.5px solid #D6EFFA">
      <svg width="26" height="26" viewBox="0 0 26 26">
        <g transform="translate(13,13)">
          <ellipse cx="0" cy="-6" rx="4.5" ry="7" fill="#87CEEB"/>
          <ellipse cx="0" cy="-6" rx="4.5" ry="7" fill="#87CEEB" transform="rotate(72)"/>
          <ellipse cx="0" cy="-6" rx="4.5" ry="7" fill="#87CEEB" transform="rotate(144)"/>
          <ellipse cx="0" cy="-6" rx="4.5" ry="7" fill="#87CEEB" transform="rotate(216)"/>
          <ellipse cx="0" cy="-6" rx="4.5" ry="7" fill="#87CEEB" transform="rotate(288)"/>
          <circle cx="0" cy="0" r="5.5" fill="#87CEEB"/>
        </g>
      </svg>
    </div>
    <div>
      <div style="font-size:17px;font-weight:800;color:{NAVY};
                  letter-spacing:-0.5px;line-height:1.1">Backbe</div>
      <div style="font-size:9px;color:#B0B8C4;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.18em;margin-top:1px">CENTRAL</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # Navegação agrupada
    for _sec, _items in _NAV:
        st.markdown(f'<div class="nav-section-label">{_sec}</div>',
                    unsafe_allow_html=True)
        for _key, _label in _items:
            if st.session_state["pagina"] == _key:
                st.markdown(
                    f'<div class="nav-active"><span class="nl">{_label}</span></div>',
                    unsafe_allow_html=True)
            else:
                if st.button(_label, key=f"_nav_{_key}",
                             use_container_width=True):
                    st.session_state["pagina"] = _key
                    st.rerun()

    # Configurações
    st.markdown("""
<div style="height:1px;background:#F0F2F5;margin:10px 0 2px 0"></div>
<div class="nav-section-label">CONFIGURACOES</div>
""", unsafe_allow_html=True)
    if st.button("↺  Atualizar Nuvemshop", use_container_width=True,
                 type="primary", key="_btn_update_ns"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""<div style="font-size:10.5px;color:#B0B8C4;
                               text-align:center;margin-top:8px">
                   dados atualizados a cada 1h</div>""",
                unsafe_allow_html=True)

pagina = st.session_state["pagina"]

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Buscando pedidos na Nuvemshop...")
def load_ns_data():
    orders = fetch_all_orders()
    prod_list, monthly = compute_sales(orders)
    customers = compute_customers(orders)
    return orders, prod_list, monthly, customers

with st.spinner("Conectando à Nuvemshop..."):
    try:
        ns_orders, ns_products, ns_monthly, ns_customers = load_ns_data()
        ns_ok = True
    except Exception as e:
        st.error(f"Erro ao conectar com Nuvemshop: {e}")
        ns_orders, ns_products, ns_monthly, ns_customers = [], [], {}, []
        ns_ok = False

# ══════════════════════════════════════════════════════════════════════════════
#  PAGINA 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "◆ Dashboard":

    # ── dados base ───────────────────────────────────────────────────────────
    ANO_DASH = 2026
    MESES_NOME_D = ["Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    MESES_ABR_D  = ["Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"]

    hoje   = datetime.now()
    mes_at = hoje.month

    # receita por mês somente 2026
    rev_2026 = {}
    ped_2026 = {}
    for m_key, d in ns_monthly.items():
        try:
            yr, mn = int(m_key[:4]), int(m_key[5:7])
        except Exception:
            continue
        if yr == ANO_DASH:
            rev_2026[mn] = d["revenue"]
            ped_2026[mn] = d.get("orders", 0)

    total_rev    = sum(d["revenue"] for d in ns_monthly.values())
    total_orders = len(ns_orders)
    ticket_medio = total_rev / total_orders if total_orders else 0
    months_sorted = sorted(ns_monthly.keys())

    rev_atual = rev_2026.get(mes_at, 0)
    rev_ant   = rev_2026.get(mes_at - 1, 0)
    ped_atual = ped_2026.get(mes_at, 0)
    fat_ano   = sum(rev_2026.values())
    ped_ano   = sum(ped_2026.values())
    ticket_ano = fat_ano / ped_ano if ped_ano else 0

    delta_pct   = ((rev_atual - rev_ant) / rev_ant * 100) if rev_ant else 0
    delta_icon  = "↑" if delta_pct >= 0 else "↓"
    delta_color = "#16A34A" if delta_pct >= 0 else "#DC2626"

    segs = {"VIP": 0, "Ativo": 0, "Reativar": 0, "Perdido": 0}
    for c in ns_customers:
        segs[c["segmento"]] = segs.get(c["segmento"], 0) + 1

    conn_d = get_conn()
    ordens_raw = rows_to_list(conn_d.execute(
        "SELECT status, COUNT(*) as cnt FROM ordens_producao WHERE status != 'pronto' GROUP BY status"
    ).fetchall())
    n_urgentes = conn_d.execute(
        "SELECT COUNT(*) FROM ordens_producao WHERE prioridade='urgente' AND status != 'pronto'"
    ).fetchone()[0]

    # ── metas ────────────────────────────────────────────────────────────────
    metas_rows = rows_to_list(conn_d.execute("SELECT chave, valor FROM metas").fetchall())
    metas = {r["chave"]: r["valor"] for r in metas_rows}
    conn_d.close()
    total_em_prod = sum(o["cnt"] for o in ordens_raw)

    meta_fat      = metas.get("fat_mensal", 8000)
    meta_fat_prox = metas.get("fat_mensal_prox", 15000)
    meta_fat_anual= metas.get("fat_anual", 150000)
    meta_ped      = metas.get("pedidos_mensal", 60)
    meta_vip      = metas.get("clientes_vip", 25)
    meta_ticket   = metas.get("ticket_medio", 220)

    # progresso mês atual
    ped_mes = ns_monthly.get(months_sorted[-1], {}).get("orders", 0) if months_sorted else 0
    prog_fat    = min(rev_atual / meta_fat * 100, 100) if meta_fat else 0
    prog_ped    = min(ped_mes  / meta_ped  * 100, 100) if meta_ped else 0
    prog_vip    = min(segs["VIP"] / meta_vip * 100, 100) if meta_vip else 0
    prog_ticket = min(ticket_medio / meta_ticket * 100, 100) if meta_ticket else 0
    prog_anual  = min(fat_ano / meta_fat_anual * 100, 100) if meta_fat_anual else 0

    # ── banner: meta mensal batida → upgrade automático ──────────────────────
    if rev_atual > 0 and rev_atual >= meta_fat and meta_fat <= 8000:
        if "meta_upgrade_feito" not in st.session_state:
            st.session_state.meta_upgrade_feito = False
        if not st.session_state.meta_upgrade_feito:
            st.markdown(f"""
<div style="background:linear-gradient(135deg,#ECFDF5,#D1FAE5);
            border:1.5px solid #6EE7B7;border-radius:16px;
            padding:18px 22px;margin-bottom:22px;
            display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
  <div>
    <div style="font-size:16px;font-weight:800;color:#065F46">
      Meta de R$8.000 batida! 🎉
    </div>
    <div style="font-size:13px;color:#047857;margin-top:3px">
      Faturamento atual: <strong>R${rev_atual:,.0f}</strong> —
      defina a nova meta de <strong>R${meta_fat_prox:,.0f}</strong>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
            _col_yes, _col_no = st.columns([1, 4])
            with _col_yes:
                if st.button("Sim, atualizar para R$15k", type="primary",
                             key="btn_upgrade_meta"):
                    _conn_upg = get_conn()
                    _conn_upg.execute(
                        "UPDATE metas SET valor=? WHERE chave='fat_mensal'",
                        (meta_fat_prox,))
                    _conn_upg.commit()
                    _conn_upg.close()
                    st.session_state.meta_upgrade_feito = True
                    st.success("Meta atualizada para R$15.000!")
                    st.rerun()

    # ── header ───────────────────────────────────────────────────────────────
    MESES_PT_D = ["janeiro","fevereiro","marco","abril","maio","junho",
                  "julho","agosto","setembro","outubro","novembro","dezembro"]
    hoje = datetime.now()
    hora = hoje.hour
    saudacao = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;
            margin-bottom:24px;flex-wrap:wrap;gap:12px">
  <div>
    <div style="font-size:13px;color:#6B7280;font-weight:500;margin-bottom:3px">
      {saudacao}, <strong style="color:{NAVY}">Isabela</strong>
    </div>
    <div style="font-size:clamp(18px,3vw,26px);font-weight:800;color:{NAVY};
                letter-spacing:-0.8px;line-height:1.15">
      Visao Geral do Negocio
    </div>
    <div style="font-size:12px;color:#9CA3AF;margin-top:4px">
      {hoje.strftime('%d')} de {MESES_PT_D[hoje.month-1]} de {hoje.year}
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <div style="background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);
                padding:7px 14px;display:flex;align-items:center;gap:7px;white-space:nowrap">
      <div style="width:8px;height:8px;background:#10B981;border-radius:50%;flex-shrink:0"></div>
      <span style="font-size:12px;color:#374151;font-weight:600">Nuvemshop conectada</span>
    </div>
    <div style="background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);
                padding:7px 14px;white-space:nowrap">
      <span style="font-size:12px;color:#374151;font-weight:600">
        Meta: <strong style="color:{PINK}">R${meta_fat:,.0f}</strong>
        &nbsp;·&nbsp; Anual: <strong style="color:{GOLD}">R${fat_ano/1000:.1f}k&thinsp;/&thinsp;R${meta_fat_anual/1000:.0f}k</strong>
        &nbsp;<span style="color:#6B7280">({prog_anual:.0f}%)</span>
      </span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── tabs mensal / anual ───────────────────────────────────────────────────
    def _pbar_goal(label, pct, color=PINK):
        w = max(4, round(pct))
        return f"""<div class="goal-bar-wrap">
  <div class="goal-bar-header"><span>{label}</span><span>{pct:.0f}%</span></div>
  <div class="goal-bar-bg"><div class="goal-bar-fill" style="width:{w}%;background:{color}"></div></div>
</div>"""

    tab_mensal, tab_anual = st.tabs([
        f"◉  Mensal — {MESES_NOME_D[mes_at-1]} {ANO_DASH}",
        f"↗  Anual — {ANO_DASH}"
    ])

    # ══ TAB MENSAL ════════════════════════════════════════════════════════════
    with tab_mensal:

        # ── Linha 1: Faturamento + Pedidos ───────────────────────────────────
        k1, k2 = st.columns(2, gap="medium")

        with k1:
            st.markdown(f"""
<div class="kcard" style="background:#FFF0F6;border-color:#FFADD0">
  <div class="kcard-label" style="color:{PINK}">Faturamento — {MESES_NOME_D[mes_at-1]}</div>
  <div class="kcard-val">R${rev_atual/1000:.1f}k</div>
  <div class="kcard-sub">Meta R${meta_fat/1000:.0f}k</div>
  {_pbar_goal(f"R${rev_atual:,.0f} de R${meta_fat:,.0f}", prog_fat, PINK)}
  <div class="kcard-delta" style="background:#FCE7F3;color:{PINK}">{delta_icon} {abs(delta_pct):.1f}% vs mes ant.</div>
</div>""", unsafe_allow_html=True)

        with k2:
            st.markdown(f"""
<div class="kcard" style="background:#EFF6FF;border-color:#93C5FD">
  <div class="kcard-label" style="color:#2563EB">Pedidos — {MESES_NOME_D[mes_at-1]}</div>
  <div class="kcard-val">{ped_atual}</div>
  <div class="kcard-sub">Meta: {int(meta_ped)} pedidos</div>
  {_pbar_goal(f"{ped_atual} de {int(meta_ped)}", prog_ped, "#2563EB")}
  <div class="kcard-delta" style="background:#DBEAFE;color:#1D4ED8">ticket R${ticket_medio:.0f}</div>
</div>""", unsafe_allow_html=True)

        # ── Linha 2: Clientes VIP + Ticket Médio ─────────────────────────────
        k3, k4 = st.columns(2, gap="medium")

        with k3:
            st.markdown(f"""
<div class="kcard" style="background:#FFFBEB;border-color:#FCD34D">
  <div class="kcard-label" style="color:#92400E">Clientes VIP</div>
  <div class="kcard-val">{segs['VIP']}</div>
  <div class="kcard-sub">Meta: {int(meta_vip)} VIPs</div>
  {_pbar_goal(f"{segs['VIP']} de {int(meta_vip)}", prog_vip, GOLD)}
  <div class="kcard-delta" style="background:#FEF9C3;color:#92400E">{segs['Reativar']} para reativar</div>
</div>""", unsafe_allow_html=True)

        with k4:
            st.markdown(f"""
<div class="kcard" style="background:#F5F3FF;border-color:#DDD6FE">
  <div class="kcard-label" style="color:#7C3AED">Ticket Medio</div>
  <div class="kcard-val">R${ticket_medio:.0f}</div>
  <div class="kcard-sub">Meta: R${meta_ticket:.0f}</div>
  {_pbar_goal(f"R${ticket_medio:.0f} de R${meta_ticket:.0f}", prog_ticket, "#7C3AED")}
  <div class="kcard-delta" style="background:#EDE9FE;color:#6D28D9">{len(ns_customers)} clientes</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # ── gráfico 2026 + alertas ────────────────────────────────────────────
        chart_col, alert_col = st.columns([2, 1], gap="large")

        with chart_col:
            months_2026 = sorted([m for m in ns_monthly if m.startswith("2026")])
            st.markdown(f"""
<div class="wcard" style="padding-bottom:6px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
    <div>
      <div class="wcard-title">Faturamento — {ANO_DASH}</div>
      <div class="wcard-sub">Receita bruta mensal · ano atual</div>
    </div>
    <span style="background:#F0F2F5;color:#6B7280;padding:5px 14px;
                 border-radius:10px;font-size:11px;font-weight:700">
      R${fat_ano/1000:.1f}k acumulado
    </span>
  </div>
""", unsafe_allow_html=True)
            if months_2026:
                df_m26 = pd.DataFrame([
                    {"Mes": MESES_ABR_D[int(m[5:7])-1],
                     "Receita": ns_monthly[m]["revenue"],
                     "Pedidos": ns_monthly[m].get("orders", 0)}
                    for m in months_2026
                ])
                fig_area = go.Figure()
                fig_area.add_trace(go.Scatter(
                    x=df_m26["Mes"], y=df_m26["Receita"],
                    fill="tozeroy", fillcolor="rgba(201,107,160,0.10)",
                    line=dict(color=PINK, width=3),
                    mode="lines+markers",
                    marker=dict(color="white", size=8,
                                line=dict(color=PINK, width=2.5)),
                    name="Faturamento",
                    hovertemplate="<b>%{x}</b>: R$%{y:,.0f}<extra></extra>",
                ))
                fig_area.add_hline(
                    y=meta_fat, line_dash="dot", line_color=GOLD,
                    line_width=1.5,
                    annotation_text=f"Meta R${meta_fat/1000:.0f}k",
                    annotation_font_size=10,
                    annotation_font_color=GOLD,
                )
                fig_area.update_layout(
                    height=260,
                    margin=dict(t=16, b=16, l=4, r=4),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False,
                               tickfont=dict(size=11, color="#98A2B3", family="DM Sans")),
                    yaxis=dict(showgrid=True, gridcolor="#F0F2F5",
                               tickprefix="R$",
                               tickfont=dict(size=10, color="#98A2B3", family="DM Sans"),
                               gridwidth=1),
                    showlegend=False,
                    font=dict(family="DM Sans"),
                )
                st.plotly_chart(fig_area, use_container_width=True)
            else:
                st.markdown(
                    '<div style="padding:50px 0;text-align:center;'
                    'color:#9CA3AF;font-size:13px">Sem dados 2026 ainda.</div>',
                    unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with alert_col:
            _reat_pct = min(segs['Reativar'] / max(len(ns_customers), 1) * 100, 100)
            st.markdown(f"""
<div class="wcard" style="height:100%;display:flex;flex-direction:column;gap:0">

  <!-- header -->
  <div style="display:flex;justify-content:space-between;align-items:center;
              margin-bottom:20px">
    <div style="font-size:14px;font-weight:700;color:{NAVY}">Resumo operacional</div>
    {'<span style="background:#FEE2E2;color:#DC2626;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700">'+str(n_urgentes)+' urgentes</span>' if n_urgentes > 0 else ''}
  </div>

  <!-- Para Reativar -->
  <div style="padding:14px 0;border-bottom:1px solid #F4F5F7">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;
                margin-bottom:8px">
      <div>
        <div style="font-size:11px;font-weight:600;color:#9CA3AF;
                    letter-spacing:0.04em;margin-bottom:4px">Para Reativar</div>
        <div style="font-size:32px;font-weight:800;color:{PINK};
                    line-height:1;letter-spacing:-1px">{segs['Reativar']}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:#9CA3AF">clientes</div>
        <div style="font-size:11px;color:#9CA3AF">60–180 dias</div>
      </div>
    </div>
    <div style="background:#F0F2F5;border-radius:99px;height:5px">
      <div style="width:{_reat_pct:.0f}%;background:{PINK};
                  border-radius:99px;height:5px"></div>
    </div>
    <div style="font-size:10px;color:#9CA3AF;margin-top:4px">
      {_reat_pct:.0f}% da base</div>
  </div>

  <!-- Em Produção -->
  <div style="padding:14px 0;border-bottom:1px solid #F4F5F7">
    <div style="display:flex;justify-content:space-between;align-items:flex-end">
      <div>
        <div style="font-size:11px;font-weight:600;color:#9CA3AF;
                    letter-spacing:0.04em;margin-bottom:4px">Em Producao</div>
        <div style="font-size:32px;font-weight:800;color:{GOLD};
                    line-height:1;letter-spacing:-1px">{total_em_prod}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:#9CA3AF">ordens</div>
        <div style="font-size:11px;color:{'#DC2626' if n_urgentes>0 else '#9CA3AF'}">
          {n_urgentes} urgente{'s' if n_urgentes!=1 else ''}</div>
      </div>
    </div>
  </div>

  <!-- Clientes VIP -->
  <div style="padding:14px 0 0">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;
                margin-bottom:8px">
      <div>
        <div style="font-size:11px;font-weight:600;color:#9CA3AF;
                    letter-spacing:0.04em;margin-bottom:4px">Clientes VIP</div>
        <div style="font-size:32px;font-weight:800;color:#16A34A;
                    line-height:1;letter-spacing:-1px">{segs['VIP']}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:#9CA3AF">meta</div>
        <div style="font-size:13px;font-weight:700;color:#16A34A">{int(meta_vip)}</div>
      </div>
    </div>
    <div style="background:#F0F2F5;border-radius:99px;height:5px">
      <div style="width:{prog_vip:.0f}%;background:#16A34A;
                  border-radius:99px;height:5px"></div>
    </div>
    <div style="font-size:10px;color:#9CA3AF;margin-top:4px">{prog_vip:.0f}% da meta</div>
  </div>

</div>
""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ── Top Produtos + Metas ──────────────────────────────────────────────
        b1_m, b2_m = st.columns([3, 2], gap="large")

        with b1_m:
            st.markdown(f"""
<div class="wcard">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <div>
      <div class="wcard-title">Top Produtos</div>
      <div class="wcard-sub">Receita acumulada — historico</div>
    </div>
    <span class="chip chip-gray">{len(ns_products)} produtos</span>
  </div>
""", unsafe_allow_html=True)
            for i, p in enumerate(ns_products[:8]):
                pct = p["revenue"] / total_rev * 100 if total_rev else 0
                bar_w = max(4, int(pct * 3.2))
                rank_bg    = PINK if i == 0 else (GOLD if i == 1 else (NAVY if i == 2 else "#E5E7EB"))
                rank_color = "white" if i < 3 else "#6B7280"
                st.markdown(f"""
  <div style="display:flex;align-items:center;gap:10px;
              padding:9px 0;border-bottom:1px solid #F0F2F5">
    <span style="min-width:24px;height:24px;background:{rank_bg};
                 color:{rank_color};border-radius:50%;display:flex;
                 align-items:center;justify-content:center;
                 font-size:11px;font-weight:800;flex-shrink:0">{i+1}</span>
    <div style="flex:1;min-width:0">
      <div style="font-size:12.5px;font-weight:600;color:{NAVY};
                  white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
        {p['produto'][:38]}
      </div>
      <div class="pbar-bg" style="margin-top:5px">
        <div class="pbar-fill" style="width:{bar_w}%;
          background:{'linear-gradient(90deg,'+PINK+',#e891c1)' if i==0 else (
          'linear-gradient(90deg,'+GOLD+',#d4a017)' if i==1 else
          '#CBD5E1')}"></div>
      </div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:12.5px;font-weight:700;color:{NAVY}">R${p['revenue']:,.0f}</div>
      <div style="font-size:10.5px;color:#9CA3AF">{p['units']} un · {pct:.0f}%</div>
    </div>
  </div>
""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with b2_m:
            conn_meta = get_conn()
            st.markdown(f"""
<div class="wcard">
  <div class="wcard-title" style="margin-bottom:4px">Metas do Mes</div>
  <div class="wcard-sub" style="margin-bottom:12px">Progresso em tempo real</div>
""", unsafe_allow_html=True)
            _meta_cfg = [
                ("fat_mensal",     "Faturamento",  f"R${meta_fat:,.0f}",  prog_fat,    PINK),
                ("pedidos_mensal", "Pedidos",       str(int(meta_ped)),     prog_ped,    "#2563EB"),
                ("clientes_vip",   "VIP alvo",      str(int(meta_vip)),     prog_vip,    GOLD),
                ("ticket_medio",   "Ticket medio",  f"R${meta_ticket:.0f}", prog_ticket, "#7C3AED"),
            ]
            for chave, lbl, val_str, prog, cor in _meta_cfg:
                st.markdown(f"""
  <div style="padding:10px 0;border-bottom:1px solid #F0F2F5">
    <div style="display:flex;justify-content:space-between;margin-bottom:5px">
      <span style="font-size:12px;font-weight:600;color:{NAVY}">{lbl}</span>
      <span style="font-size:12px;font-weight:700;color:{cor}">{val_str}</span>
    </div>
    <div class="pbar-bg">
      <div class="pbar-fill" style="width:{prog:.0f}%;background:{cor}"></div>
    </div>
    <div style="font-size:10px;color:#9CA3AF;margin-top:3px">{prog:.0f}% da meta</div>
  </div>
""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            with st.expander("Editar metas", expanded=False):
                new_fat    = st.number_input("Meta faturamento mensal (R$)",
                                             value=float(meta_fat), step=1000.0,
                                             key="meta_fat_inp")
                new_ped    = st.number_input("Meta pedidos por mes",
                                             value=float(meta_ped), step=5.0,
                                             key="meta_ped_inp")
                new_vip    = st.number_input("Meta clientes VIP",
                                             value=float(meta_vip), step=1.0,
                                             key="meta_vip_inp")
                new_ticket = st.number_input("Meta ticket medio (R$)",
                                             value=float(meta_ticket), step=10.0,
                                             key="meta_ticket_inp")
                if st.button("Salvar metas", type="primary", key="salvar_metas"):
                    for k, v in [("fat_mensal", new_fat), ("pedidos_mensal", new_ped),
                                  ("clientes_vip", new_vip), ("ticket_medio", new_ticket)]:
                        conn_meta.execute(
                            "UPDATE metas SET valor=? WHERE chave=?", (v, k))
                    conn_meta.commit()
                    st.success("Metas salvas!")
                    st.rerun()
            conn_meta.close()

    # ══ TAB ANUAL ════════════════════════════════════════════════════════════
    with tab_anual:

        # ── KPI cards anuais — grade 2×2 ─────────────────────────────────────
        a1, a2 = st.columns(2, gap="medium")
        meses_c_dados = max(len(ped_2026), 1)

        with a1:
            st.markdown(f"""
<div class="kcard" style="background:#FFF0F6;border-color:#FFADD0">
  <div class="kcard-label" style="color:{PINK}">Faturamento — {ANO_DASH}</div>
  <div class="kcard-val">R${fat_ano/1000:.1f}k</div>
  <div class="kcard-sub">{len([m for m in rev_2026 if rev_2026[m]>0])} meses com receita</div>
  {_pbar_goal(f"R${fat_ano:,.0f} de R${meta_fat_anual:,.0f}", prog_anual, PINK)}
</div>""", unsafe_allow_html=True)

        with a2:
            st.markdown(f"""
<div class="kcard" style="background:#EFF6FF;border-color:#93C5FD">
  <div class="kcard-label" style="color:#2563EB">Pedidos — {ANO_DASH}</div>
  <div class="kcard-val">{ped_ano}</div>
  <div class="kcard-sub">media de {ped_ano/meses_c_dados:.0f} por mes</div>
</div>""", unsafe_allow_html=True)

        a3, a4 = st.columns(2, gap="medium")

        with a3:
            st.markdown(f"""
<div class="kcard" style="background:#F5F3FF;border-color:#DDD6FE">
  <div class="kcard-label" style="color:#7C3AED">Ticket Medio — {ANO_DASH}</div>
  <div class="kcard-val">R${ticket_ano:.0f}</div>
  <div class="kcard-sub">baseado em pedidos do ano</div>
</div>""", unsafe_allow_html=True)

        with a4:
            st.markdown(f"""
<div class="kcard" style="background:#FFFBEB;border-color:#FCD34D">
  <div class="kcard-label" style="color:#92400E">Clientes na Base</div>
  <div class="kcard-val">{len(ns_customers)}</div>
  <div class="kcard-sub">{segs['VIP']} VIP · {segs['Ativo']} ativos</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # ── gráfico 12 meses + segmentos ──────────────────────────────────────
        ca, cs = st.columns([2, 1], gap="large")

        with ca:
            st.markdown(f"""
<div class="wcard" style="padding-bottom:6px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
    <div>
      <div class="wcard-title">Evolucao Anual — {ANO_DASH}</div>
      <div class="wcard-sub">Faturamento mensal · 12 meses</div>
    </div>
    <span style="background:#F0F2F5;color:#6B7280;padding:5px 14px;
                 border-radius:10px;font-size:11px;font-weight:700">
      R${fat_ano/1000:.1f}k acumulado
    </span>
  </div>
""", unsafe_allow_html=True)
            df_anual = pd.DataFrame([
                {"Mes": MESES_ABR_D[i], "Receita": rev_2026.get(i+1, 0),
                 "Pedidos": ped_2026.get(i+1, 0)}
                for i in range(12)
            ])
            fig_anual = go.Figure()
            fig_anual.add_trace(go.Bar(
                x=df_anual["Mes"], y=df_anual["Receita"],
                marker=dict(
                    color=[PINK if r > 0 else "#E5E7EB" for r in df_anual["Receita"]],
                    opacity=0.85,
                ),
                name="Faturamento",
                hovertemplate="<b>%{x}</b>: R$%{y:,.0f}<extra></extra>",
            ))
            fig_anual.add_hline(
                y=meta_fat, line_dash="dot", line_color=GOLD,
                line_width=1.5,
                annotation_text=f"Meta R${meta_fat/1000:.0f}k",
                annotation_font_size=10,
                annotation_font_color=GOLD,
            )
            fig_anual.update_layout(
                height=260,
                margin=dict(t=16, b=16, l=4, r=4),
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(showgrid=False,
                           tickfont=dict(size=11, color="#98A2B3", family="DM Sans")),
                yaxis=dict(showgrid=True, gridcolor="#F0F2F5",
                           tickprefix="R$",
                           tickfont=dict(size=10, color="#98A2B3", family="DM Sans"),
                           gridwidth=1),
                bargap=0.35, showlegend=False,
                font=dict(family="DM Sans"),
            )
            st.plotly_chart(fig_anual, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with cs:
            st.markdown(f"""
<div class="wcard">
  <div class="wcard-title" style="margin-bottom:4px">Saude da Base</div>
  <div class="wcard-sub" style="margin-bottom:8px">Segmentacao de clientes</div>
""", unsafe_allow_html=True)
            if ns_customers:
                fig_seg = go.Figure(go.Pie(
                    labels=list(segs.keys()),
                    values=list(segs.values()),
                    hole=0.60,
                    marker_colors=[GOLD, "#22C55E", PINK, "#D1D5DB"],
                    textinfo="none",
                    hovertemplate="<b>%{label}</b>: %{value}<extra></extra>",
                ))
                fig_seg.update_layout(
                    margin=dict(t=4, b=4, l=4, r=4),
                    height=160,
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    annotations=[dict(
                        text=f"<b>{len(ns_customers)}</b><br><span>clientes</span>",
                        x=0.5, y=0.5, font_size=14, font_color=NAVY,
                        showarrow=False, font=dict(family="DM Sans")
                    )]
                )
                st.plotly_chart(fig_seg, use_container_width=True)
            segs_data = [
                ("VIP",      segs['VIP'],      "#FEF9C3","#713F12", "◆"),
                ("Ativos",   segs['Ativo'],    "#DCFCE7","#15803D", "●"),
                ("Reativar", segs['Reativar'], "#FFEDD5","#92400E", "▲"),
                ("Perdidos", segs['Perdido'],  "#F3F4F6","#6B7280", "▪"),
            ]
            st.markdown(
                '<div style="display:flex;flex-direction:column;gap:5px;margin-top:4px">',
                unsafe_allow_html=True)
            for lbl, val, bg, fg, sym in segs_data:
                st.markdown(f"""
  <div style="display:flex;justify-content:space-between;align-items:center;
              padding:6px 10px;background:{bg};border-radius:8px">
    <span style="font-size:12px;font-weight:700;color:{fg}">{sym} {lbl}</span>
    <span style="font-size:13px;font-weight:800;color:{NAVY}">{val}</span>
  </div>
""", unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ── resumo mensal + tamanhos + scatter ────────────────────────────────
        t1, t2, t3 = st.columns([4, 3, 3], gap="large")

        with t1:
            st.markdown(f"""
<div class="wcard" style="padding-bottom:10px">
  <div class="wcard-title" style="margin-bottom:2px">Resumo Mensal — {ANO_DASH}</div>
  <div class="wcard-sub">Faturamento e pedidos por mes</div>
""", unsafe_allow_html=True)
            rows_anual = []
            for i in range(12):
                m_num = i + 1
                rev_m = rev_2026.get(m_num, 0)
                ped_m = ped_2026.get(m_num, 0)
                vs_meta = "—"
                if rev_m > 0 and meta_fat > 0:
                    diff = ((rev_m / meta_fat) - 1) * 100
                    vs_meta = f"+{diff:.0f}%" if diff >= 0 else f"{diff:.0f}%"
                rows_anual.append({
                    "Mes": MESES_ABR_D[i],
                    "Faturamento": f"R${rev_m:,.0f}" if rev_m > 0 else "—",
                    "Pedidos": ped_m if ped_m > 0 else "—",
                    "vs Meta": vs_meta,
                })
            df_resumo = pd.DataFrame(rows_anual)
            st.dataframe(df_resumo, use_container_width=True, hide_index=True, height=360)
            st.markdown("</div>", unsafe_allow_html=True)

        with t2:
            sizes_all = {}
            for p in ns_products:
                for s, q in (p.get("sizes") or {}).items():
                    sizes_all[s] = sizes_all.get(s, 0) + q
            st.markdown(f"""
<div class="wcard" style="padding-bottom:10px">
  <div class="wcard-title" style="margin-bottom:2px">Tamanhos mais vendidos</div>
  <div class="wcard-sub">Unidades por tamanho</div>
""", unsafe_allow_html=True)
            if sizes_all:
                df_sz = pd.DataFrame(
                    sorted(sizes_all.items(), key=lambda x: -x[1])[:8],
                    columns=["Tamanho", "Unidades"]
                )
                fig_sz = go.Figure(go.Bar(
                    x=df_sz["Tamanho"], y=df_sz["Unidades"],
                    marker=dict(
                        color=df_sz["Unidades"],
                        colorscale=[[0, "#E5E7EB"], [1, PINK]],
                        showscale=False,
                    ),
                    text=df_sz["Unidades"], textposition="outside",
                    textfont=dict(size=11, family="DM Sans"),
                ))
                fig_sz.update_layout(
                    height=220,
                    margin=dict(t=12, b=8, l=0, r=0),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False,
                               tickfont=dict(size=11, family="DM Sans")),
                    yaxis=dict(visible=False),
                    showlegend=False,
                    font=dict(family="DM Sans"),
                )
                st.plotly_chart(fig_sz, use_container_width=True)
            else:
                st.markdown('<div style="padding:30px 0;text-align:center;'
                            'color:#9CA3AF">Sem dados de tamanho.</div>',
                            unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with t3:
            st.markdown(f"""
<div class="wcard" style="padding-bottom:10px">
  <div class="wcard-title" style="margin-bottom:2px">Receita vs Pedidos</div>
  <div class="wcard-sub">Correlacao receita-volume</div>
""", unsafe_allow_html=True)
            if ns_monthly:
                df_sc = pd.DataFrame([
                    {"Mes": m[5:] + "/" + m[2:4],
                     "Receita": d["revenue"],
                     "Pedidos": d.get("orders", 0)}
                    for m, d in sorted(ns_monthly.items())
                ])
                fig_sc = go.Figure()
                fig_sc.add_trace(go.Bar(
                    x=df_sc["Mes"], y=df_sc["Pedidos"],
                    name="Pedidos", yaxis="y2",
                    marker_color=NAVY, opacity=0.25,
                    hovertemplate="%{y} pedidos<extra></extra>",
                ))
                fig_sc.add_trace(go.Scatter(
                    x=df_sc["Mes"], y=df_sc["Receita"],
                    name="Receita", mode="lines+markers",
                    line=dict(color=PINK, width=2.5),
                    marker=dict(color="white", size=7,
                                line=dict(color=PINK, width=2)),
                    hovertemplate="R$%{y:,.0f}<extra></extra>",
                ))
                fig_sc.update_layout(
                    height=220,
                    margin=dict(t=12, b=8, l=4, r=4),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False,
                               tickfont=dict(size=10, family="DM Sans"),
                               tickangle=-30),
                    yaxis=dict(showgrid=True, gridcolor="#F0F2F5",
                               tickprefix="R$",
                               tickfont=dict(size=10, family="DM Sans")),
                    yaxis2=dict(overlaying="y", side="right",
                                showgrid=False, visible=False),
                    showlegend=False,
                    font=dict(family="DM Sans"),
                )
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.markdown('<div style="padding:30px 0;text-align:center;'
                            'color:#9CA3AF">Sem dados.</div>',
                            unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 2 — CRM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "◎ CRM — Clientes":
    st.title("👥 CRM — Clientes Backbe")

    vip    = [c for c in ns_customers if c["segmento"] == "VIP"]
    ativos = [c for c in ns_customers if c["segmento"] == "Ativo"]
    reat   = [c for c in ns_customers if c["segmento"] == "Reativar"]
    perd   = [c for c in ns_customers if c["segmento"] == "Perdido"]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("⭐ VIP", len(vip), help="3+ pedidos e R$500+ gastos")
    k2.metric("✅ Ativos", len(ativos), help="Compraram nos últimos 60 dias")
    k3.metric("🔔 Reativar", len(reat), help="60–180 dias sem comprar")
    k4.metric("❌ Perdidos", len(perd), help="Mais de 180 dias sem comprar")

    st.divider()

    aba = st.tabs(["⭐ VIP", "✅ Ativos", "🔔 Reativar", "❌ Perdidos", "🔍 Buscar"])

    def render_cliente_table(customers, show_reativacao=False):
        if not customers:
            st.info("Nenhum cliente nesta categoria.")
            return
        rows = []
        for c in customers[:100]:
            rows.append({
                "Nome": c["name"],
                "Email": c["email"],
                "Pedidos": c["pedidos"],
                "Total gasto": f"R${c['gasto']:,.0f}",
                "Último pedido": c["ultimo"],
                "Dias sem comprar": c["days_since"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        if show_reativacao:
            st.info(f"💡 **{len(customers)} clientes para reativar** — enviar email com oferta exclusiva ou WhatsApp personalizado.")

    with aba[0]:
        st.subheader(f"⭐ Clientes VIP — {len(vip)} clientes")
        st.caption("3+ pedidos E R$500+ gastos — tratar com prioridade máxima")
        if vip:
            total_vip = sum(c["gasto"] for c in vip)
            avg_vip = total_vip / len(vip)
            st.metric("Receita total VIP", f"R${total_vip:,.0f}", help=f"Média R${avg_vip:.0f}/cliente")
        render_cliente_table(vip)

    with aba[1]:
        st.subheader(f"✅ Clientes Ativos — {len(ativos)}")
        st.caption("Compraram nos últimos 60 dias")
        render_cliente_table(ativos)

    with aba[2]:
        st.subheader(f"🔔 Para Reativar — {len(reat)}")
        st.caption("60–180 dias sem comprar — janela de recuperação")
        render_cliente_table(reat, show_reativacao=True)

    with aba[3]:
        st.subheader(f"❌ Clientes Perdidos — {len(perd)}")
        st.caption("Mais de 180 dias sem aparecer")
        render_cliente_table(perd)

    with aba[4]:
        st.subheader("🔍 Buscar cliente")
        busca = st.text_input("Nome ou email")
        if busca and len(busca) >= 2:
            resultados = [c for c in ns_customers
                          if busca.lower() in c["name"].lower()
                          or busca.lower() in c["email"].lower()]
            if resultados:
                for c in resultados[:20]:
                    badge = {"VIP": "⭐", "Ativo": "✅", "Reativar": "🔔", "Perdido": "❌"}.get(c["segmento"], "")
                    with st.expander(f"{badge} {c['name']} — {c['email']}"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Pedidos", c["pedidos"])
                        col2.metric("Total gasto", f"R${c['gasto']:,.0f}")
                        col3.metric("Último pedido", c["ultimo"])
                        # Notas CRM
                        conn = get_conn()
                        existing = conn.execute("SELECT notas FROM clientes_crm WHERE ns_id=?", (c["id"],)).fetchone()
                        notas = existing["notas"] if existing else ""
                        nova_nota = st.text_area("Notas / observações", value=notas or "", key=f"nota_{c['id']}")
                        if st.button("💾 Salvar nota", key=f"salvar_{c['id']}"):
                            conn.execute("""
                                INSERT INTO clientes_crm (ns_id, nome, email, notas, atualizado_em)
                                VALUES (?,?,?,?,datetime('now'))
                                ON CONFLICT(ns_id) DO UPDATE SET notas=excluded.notas, atualizado_em=excluded.atualizado_em
                            """, (c["id"], c["name"], c["email"], nova_nota))
                            conn.commit()
                            st.success("Nota salva!")
                        conn.close()
            else:
                st.warning("Nenhum cliente encontrado.")

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 3 — TECIDOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "≋ Tecidos":
    st.title("🧵 Gestão de Tecidos")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Estoque", "➕ Cadastrar Tecido", "✏️ Editar Tecidos", "🛒 Onde Comprar", "⚖️ Tabela kg → metro"])

    conn = get_conn()

    with tab1:
        st.subheader("Estoque de Tecidos")
        tecidos = rows_to_list(conn.execute("SELECT * FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())

        if not tecidos:
            st.info("Nenhum tecido cadastrado ainda.")
        else:
            # ── Mapeamento de cores para CSS ──────────────────────────────────
            _COLOR_CSS = {
                "azul": "#3B82F6", "branco": "#F1F5F9", "rosa": "#F472B6",
                "preto": "#1F2937", "verde": "#22C55E", "amarelo": "#EAB308",
                "vermelho": "#EF4444", "cinza": "#9CA3AF", "bege": "#D4B896",
                "vinho": "#7C2D12", "lilás": "#A855F7", "laranja": "#F97316",
                "marinho": "#1E3A5F", "nude": "#DEB887", "caramelo": "#B5651D",
                "creme": "#FFF8E7", "off-white": "#FAF9F6", "prata": "#C0C0C0",
                "dourado": "#B8860B", "bordo": "#800020", "coral": "#FF6B6B",
                "terracota": "#C1724F", "areia": "#C2B280",
            }
            _WORDS_COR = set(_COLOR_CSS.keys())

            def _split_familia(nome: str):
                """Separa 'Two Way Azul' em ('Two Way', 'azul')."""
                parts = nome.rsplit(" ", 1)
                if len(parts) == 2 and parts[1].strip().lower() in _WORDS_COR:
                    return parts[0].strip(), parts[1].strip().lower()
                return nome.strip(), None

            # Agrupa tecidos por família
            _familias: dict = {}
            _sem_grupo: list = []
            for t in tecidos:
                familia, cor = _split_familia(t["nome"])
                if cor:
                    _familias.setdefault(familia, []).append((cor, t))
                else:
                    # Tenta usar o campo 'cor' do banco
                    cor_db = (t.get("cor") or "").strip().lower()
                    if cor_db:
                        _familias.setdefault(t["nome"], []).append((cor_db, t))
                    else:
                        _sem_grupo.append(t)

            # ── Cards por família ─────────────────────────────────────────────
            for familia, variantes in sorted(_familias.items()):
                estoque_total = sum(float(t["estoque"] or 0) for _, t in variantes)
                un_ref = variantes[0][1]["estoque_unidade"] or "m"

                # Cabeçalho da família
                st.markdown(f"""
                <div style="margin:16px 0 8px 0">
                  <span style="font-size:15px;font-weight:700;color:#1a2f4a">{familia}</span>
                  <span style="font-size:12px;color:#6B7280;margin-left:8px">
                    — {len(variantes)} cor(es) · {estoque_total:.1f} {un_ref} total
                  </span>
                </div>""", unsafe_allow_html=True)

                # Chips de cor com estoque
                chips_html = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:4px">'
                for cor, t in sorted(variantes, key=lambda x: x[0]):
                    pm = _calc_preco_metro(t)
                    bg = _COLOR_CSS.get(cor, "#E5E7EB")
                    text_col = "#FFFFFF" if cor in {"azul", "preto", "marinho", "vinho", "verde"} else "#1F2937"
                    est = float(t["estoque"] or 0)
                    un = t["estoque_unidade"] or "m"
                    baixo = est < 5
                    border = "2px solid #EF4444" if baixo else "1.5px solid #E5E7EB"
                    chips_html += f"""
                    <div style="border:{border};border-radius:12px;padding:10px 14px;
                                background:white;min-width:130px;box-shadow:0 1px 4px rgba(0,0,0,.06)">
                      <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
                        <div style="width:16px;height:16px;border-radius:50%;background:{bg};
                                    border:1px solid rgba(0,0,0,.15);flex-shrink:0"></div>
                        <span style="font-size:13px;font-weight:600;color:#374151;
                                     text-transform:capitalize">{cor}</span>
                        {"<span style='font-size:10px;color:#EF4444;font-weight:700'>BAIXO</span>" if baixo else ""}
                      </div>
                      <div style="font-size:17px;font-weight:800;color:#1a2f4a">{est:.1f} {un}</div>
                      <div style="font-size:11px;color:#9CA3AF">R${pm:.2f}/m</div>
                    </div>"""
                chips_html += "</div>"
                st.markdown(chips_html, unsafe_allow_html=True)

                # Atualizar estoque de cada variante
                with st.expander("Atualizar estoque", expanded=False):
                    for cor, t in sorted(variantes, key=lambda x: x[0]):
                        col_l, col_r = st.columns([2, 1])
                        novo_est = col_l.number_input(
                            f"Estoque — {cor}",
                            value=float(t["estoque"] or 0),
                            step=0.5, key=f"est_{t['id']}"
                        )
                        if col_r.button("Salvar", key=f"save_est_{t['id']}"):
                            conn.execute("UPDATE tecidos SET estoque=? WHERE id=?",
                                         (novo_est, t["id"]))
                            conn.commit()
                            st.success(f"Estoque de {t['nome']} atualizado!")
                            st.rerun()

                st.markdown(
                    "<div style='height:1px;background:#F3F4F6;margin:12px 0'></div>",
                    unsafe_allow_html=True
                )

            # ── Tecidos sem grupo de cor ──────────────────────────────────────
            if _sem_grupo:
                st.markdown("**Outros tecidos**")
                for t in _sem_grupo:
                    preco_m = _calc_preco_metro(t)
                    with st.expander(
                        f"**{t['nome']}** — {t['tipo']} | "
                        f"R${preco_m:.2f}/m | {t['estoque']} {t['estoque_unidade']}"
                    ):
                        c1, c2 = st.columns(2)
                        c1.metric("Preço/metro", f"R${preco_m:.2f}")
                        c2.metric("Estoque", f"{t['estoque']} {t['estoque_unidade']}")
                        col_est, col_btn = st.columns([2, 1])
                        novo_est = col_est.number_input(
                            "Atualizar estoque", value=float(t["estoque"]),
                            step=0.5, key=f"est_{t['id']}"
                        )
                        if col_btn.button("Salvar", key=f"save_est_{t['id']}"):
                            conn.execute("UPDATE tecidos SET estoque=? WHERE id=?",
                                         (novo_est, t["id"]))
                            conn.commit()
                            st.success("Estoque atualizado!")
                            st.rerun()

    with tab2:
        st.subheader("Cadastrar / Editar Tecido")
        with st.form("form_tecido"):
            c1, c2 = st.columns(2)
            nome  = c1.text_input("Nome do tecido*")
            tipo  = c2.selectbox("Tipo", ["tecido", "malha", "jeans", "cetim", "forro", "outro"])

            c3, c4 = st.columns(2)
            unidade = c3.selectbox("Unidade de compra", ["metro", "kg"])
            cor = c4.text_input("Cor/variação")

            c5, c6, c7, c8 = st.columns(4)
            preco_metro = c5.number_input("Preço/metro (R$)", min_value=0.0, step=0.5,
                                          disabled=(unidade == "kg"), value=0.0)
            preco_kg    = c6.number_input("Preço/kg (R$)", min_value=0.0, step=0.5,
                                          disabled=(unidade == "metro"), value=0.0)
            peso_gsm    = c7.number_input("Peso GSM (g/m²)", min_value=0.0, step=10.0, value=200.0,
                                          help="Gramatura do tecido por m². Para malhas é essencial.")
            largura     = c8.number_input("Largura rolo (m)", min_value=0.5, max_value=3.0,
                                          step=0.1, value=1.5)

            c9, c10 = st.columns(2)
            estoque = c9.number_input("Estoque inicial", min_value=0.0, step=0.5, value=0.0)
            est_un  = c10.selectbox("Unidade estoque", ["metros", "kg", "unidades"])
            obs = st.text_area("Observações")

            submitted = st.form_submit_button("✅ Cadastrar Tecido", type="primary")
            if submitted and nome:
                try:
                    conn.execute("""
                        INSERT INTO tecidos (nome, tipo, unidade, preco_kg, preco_metro, peso_gsm,
                                            largura_m, cor, estoque, estoque_unidade, observacoes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, (nome, tipo,
                          unidade,
                          preco_kg if unidade == "kg" else None,
                          preco_metro if unidade == "metro" else None,
                          peso_gsm, largura, cor, estoque, est_un, obs))
                    conn.commit()
                    st.success(f"✅ Tecido **{nome}** cadastrado!")
                    st.rerun()
                except Exception as e:
                    if "UNIQUE" in str(e).upper():
                        st.error(f"❌ Já existe um tecido com o nome **{nome}**. Escolha outro nome ou edite o existente na aba ✏️ Editar Tecidos.")
                    else:
                        st.error(f"Erro ao cadastrar: {e}")

    with tab3:
        st.subheader("✏️ Editar Tecidos")
        tecidos_all = rows_to_list(conn.execute("SELECT * FROM tecidos ORDER BY nome").fetchall())
        if not tecidos_all:
            st.info("Nenhum tecido cadastrado.")
        else:
            df_tec = pd.DataFrame([{
                "ID": t["id"],
                "Nome": t["nome"],
                "Tipo": t["tipo"] or "",
                "Unidade": t["unidade"] or "metro",
                "R$/kg": float(t["preco_kg"] or 0),
                "R$/metro": float(t["preco_metro"] or 0),
                "GSM": float(t["peso_gsm"] or 0),
                "Largura m": float(t["largura_m"] or 1.5),
                "Cor": t["cor"] or "",
                "Estoque": float(t["estoque"] or 0),
                "Un. Estoque": t["estoque_unidade"] or "metros",
                "Ativo": bool(t["ativo"]),
            } for t in tecidos_all])
            edited_tec = st.data_editor(
                df_tec,
                use_container_width=True,
                hide_index=True,
                height=min(40 + 36 * len(df_tec), 3000),
                disabled=["ID"],
                column_config={
                    "R$/kg": st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "R$/metro": st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "GSM": st.column_config.NumberColumn(format="%.0f g/m²", step=10.0),
                    "Largura m": st.column_config.NumberColumn(format="%.2f m", step=0.1),
                    "Ativo": st.column_config.CheckboxColumn(),
                },
                key="edit_tecidos_tab"
            )
            if st.button("💾 Salvar tecidos", key="save_tec_edit", type="primary"):
                try:
                    for _, row in edited_tec.iterrows():
                        conn.execute("""
                            UPDATE tecidos SET nome=?, tipo=?, unidade=?, preco_kg=?, preco_metro=?,
                            peso_gsm=?, largura_m=?, cor=?, estoque=?, estoque_unidade=?, ativo=?
                            WHERE id=?
                        """, (
                            row["Nome"], row["Tipo"], row["Unidade"],
                            float(row["R$/kg"]) if row["R$/kg"] else None,
                            float(row["R$/metro"]) if row["R$/metro"] else None,
                            float(row["GSM"]) if row["GSM"] else None,
                            float(row["Largura m"]), row["Cor"],
                            float(row["Estoque"]), row["Un. Estoque"],
                            1 if row["Ativo"] else 0, int(row["ID"])
                        ))
                    conn.commit()
                    st.success("✅ Tecidos atualizados!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    if "UNIQUE" in str(e).upper():
                        st.error("❌ Nome duplicado: dois tecidos não podem ter o mesmo nome. Corrija e salve novamente.")
                    else:
                        st.error(f"Erro ao salvar: {e}")

            # ── Excluir tecido ─────────────────────────────────────────────
            st.divider()
            st.markdown("#### 🗑️ Excluir Tecido")
            st.caption("A exclusão é permanente e remove o tecido de todas as referências.")
            nomes_tec = [t["nome"] for t in tecidos_all]
            tec_del = st.selectbox("Selecionar tecido para excluir", ["— escolha —"] + nomes_tec, key="tec_del_sel")
            if tec_del != "— escolha —":
                tec_del_obj = next(t for t in tecidos_all if t["nome"] == tec_del)
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.warning(f"⚠️ Excluir **{tec_del}** permanentemente?")
                if col_d2.button("🗑️ Confirmar exclusão", key="tec_del_btn", type="primary"):
                    conn.execute("DELETE FROM tecidos WHERE id=?", (tec_del_obj["id"],))
                    conn.commit()
                    st.success(f"✅ Tecido **{tec_del}** excluído.")
                    st.rerun()

    with tab4:
        st.subheader("🛒 Onde Comprar — Fornecedores por Tecido")
        tecidos_lista = rows_to_list(conn.execute("SELECT id, nome FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())

        if not tecidos_lista:
            st.info("Nenhum tecido cadastrado ainda. Cadastre tecidos primeiro.")
        else:
            # ── Formulário de novo fornecedor ──────────────────────────────
            with st.expander("➕ Adicionar fornecedor", expanded=False):
                f1, f2 = st.columns(2)
                tec_forn_sel = f1.selectbox(
                    "Tecido", [t["nome"] for t in tecidos_lista], key="forn_tec"
                )
                forn_nome = f2.text_input("Nome do fornecedor*", key="forn_nome")

                f3, f4, f5 = st.columns(3)
                forn_contato = f3.text_input("Contato (WhatsApp/tel)", key="forn_contato")
                forn_cidade  = f4.text_input("Cidade", key="forn_cidade")
                forn_site    = f5.text_input("Site / Instagram", key="forn_site")
                forn_obs     = st.text_area("Observações (preço atual, prazo, mínimo...)", key="forn_obs")

                if st.button("✅ Salvar fornecedor", type="primary", key="forn_save") and forn_nome:
                    tec_id_forn = next(t["id"] for t in tecidos_lista if t["nome"] == tec_forn_sel)
                    conn.execute("""
                        INSERT INTO tecidos_fornecedores
                        (tecido_id, fornecedor, contato, cidade, site, observacoes)
                        VALUES (?,?,?,?,?,?)
                    """, (tec_id_forn, forn_nome, forn_contato, forn_cidade, forn_site, forn_obs))
                    conn.commit()
                    st.success(f"✅ Fornecedor **{forn_nome}** adicionado!")
                    st.rerun()

            st.divider()

            # ── Lista de fornecedores agrupados por tecido ─────────────────
            fornecedores = rows_to_list(conn.execute("""
                SELECT f.*, t.nome AS tecido_nome
                FROM tecidos_fornecedores f
                JOIN tecidos t ON t.id = f.tecido_id
                ORDER BY t.nome, f.fornecedor
            """).fetchall())

            if not fornecedores:
                st.info("Nenhum fornecedor cadastrado ainda. Use o formulário acima para adicionar.")
            else:
                # Agrupa por tecido
                por_tecido = {}
                for f in fornecedores:
                    por_tecido.setdefault(f["tecido_nome"], []).append(f)

                for tec_nome, flist in sorted(por_tecido.items()):
                    st.markdown(f"##### 🧵 {tec_nome}")
                    for forn in flist:
                        with st.container():
                            col_info, col_del = st.columns([10, 1])
                            with col_info:
                                partes = [f"**{forn['fornecedor']}**"]
                                if forn.get("cidade"):      partes.append(f"📍 {forn['cidade']}")
                                if forn.get("contato"):     partes.append(f"📞 {forn['contato']}")
                                if forn.get("site"):        partes.append(f"🔗 {forn['site']}")
                                st.markdown(" · ".join(partes))
                                if forn.get("observacoes"):
                                    st.caption(forn["observacoes"])
                            if col_del.button("🗑️", key=f"del_forn_{forn['id']}", help="Excluir fornecedor"):
                                conn.execute("DELETE FROM tecidos_fornecedores WHERE id=?", (forn["id"],))
                                conn.commit()
                                st.rerun()
                    st.markdown("")

    with tab5:
        st.subheader("⚖️ Conversão kg → metro (para malhas)")
        st.info("""
        **Fórmula:** Preço/metro = Preço/kg × (GSM × Largura) / 1000

        Exemplo: Malha crepe a R$35/kg, 200 g/m², 1.5m largura
        → **R$35 × (200 × 1.5) / 1000 = R$35 × 0.3 = R$10,50/metro**
        """)
        st.subheader("Simulador")
        s1, s2, s3 = st.columns(3)
        sim_pkg    = s1.number_input("Preço/kg (R$)", min_value=1.0, value=35.0, step=1.0)
        sim_gsm    = s2.number_input("GSM (g/m²)", min_value=50.0, value=200.0, step=10.0)
        sim_larg   = s3.number_input("Largura (m)", min_value=0.5, value=1.5, step=0.1)
        preco_calc = sim_pkg * (sim_gsm * sim_larg) / 1000
        st.metric("Preço por metro calculado", f"R${preco_calc:.2f}", help="Preço equivalente em metros lineares")

        st.divider()
        st.subheader("Referência de GSM por tipo de malha")
        gsm_ref = pd.DataFrame([
            ("Jersey fino", "80–130 g/m²", "Roupas leves, camisetas"),
            ("Ribana", "150–200 g/m²", "Barras, punhos, golas"),
            ("Crepe malha", "180–220 g/m²", "Calças, blusas femininas"),
            ("Moletinho", "220–280 g/m²", "Conjuntos, looks casuais"),
            ("Moletom grosso", "300–400 g/m²", "Peças de frio"),
            ("Neoprene", "250–350 g/m²", "Saias, macacões"),
        ], columns=["Tipo", "GSM", "Uso típico"])
        st.dataframe(gsm_ref, hide_index=True, use_container_width=True)

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 4 — ORDENS DE PRODUÇÃO
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⊞ Ordens de Producao":
    st.title("🏭 Ordens de Produção")

    conn = get_conn()
    STATUS_LABELS = {
        "modelagem": "✏️ Modelagem",
        "corte":     "✂️ Corte",
        "costura":   "🪡 Costura",
        "acabamento":"🔧 Acabamento",
        "pronto":    "✅ Pronto",
    }
    STATUS_ORDER = list(STATUS_LABELS.keys())
    STATUS_COLORS = {
        "modelagem": "#9E9E9E",
        "corte":     "#2196F3",
        "costura":   "#FF9800",
        "acabamento":"#9C27B0",
        "pronto":    "#4CAF50",
    }

    tab_lista, tab_nova, tab_costura = st.tabs(["📋 Ordens Ativas", "➕ Nova Ordem", "🪡 Tabela de Costura"])

    # ── Lista de ordens ──
    with tab_lista:
        ordens = rows_to_list(conn.execute("""
            SELECT op.*, t.nome as tecido_nome, cs.nome as costureira_nome
            FROM ordens_producao op
            LEFT JOIN tecidos t ON t.id = op.tecido_id
            LEFT JOIN costureiras cs ON cs.id = op.costureira_id
            ORDER BY
                CASE status WHEN 'modelagem' THEN 0 WHEN 'corte' THEN 1
                             WHEN 'costura' THEN 2 WHEN 'acabamento' THEN 3
                             WHEN 'pronto' THEN 4 END,
                data_entrada DESC
        """).fetchall())

        if not ordens:
            st.info("Nenhuma ordem de produção cadastrada ainda.")
        else:
            # Kanban summary
            st.subheader("Visão Geral")
            cols = st.columns(5)
            for i, (k, label) in enumerate(STATUS_LABELS.items()):
                cnt = sum(1 for o in ordens if o["status"] == k)
                pcs = sum(o["quantidade"] for o in ordens if o["status"] == k)
                cols[i].metric(label, f"{cnt} ordens", f"{pcs} peças")

            st.divider()

            # Filter
            filtro_status = st.multiselect(
                "Filtrar por status",
                options=list(STATUS_LABELS.keys()),
                default=[s for s in STATUS_ORDER if s != "pronto"],
                format_func=lambda x: STATUS_LABELS[x]
            )

            for o in ordens:
                if o["status"] not in filtro_status:
                    continue
                color = STATUS_COLORS.get(o["status"], "#ccc")
                label = STATUS_LABELS.get(o["status"], o["status"])
                with st.expander(
                    f"{label} | **{o['produto']}** — {o['quantidade']} peças | "
                    f"{o['tecido_nome'] or 'sem tecido'} | "
                    f"{'R$' + str(round(o['custo_total'],2)) if o['custo_total'] else 'custo pendente'}"
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Costureira:** {o['costureira_nome'] or '—'}")
                    c2.write(f"**Tecido:** {o['tecido_metros'] or 0:.1f}m de {o['tecido_nome'] or '—'}")
                    c3.write(f"**Entrada:** {o['data_entrada'][:10]}")
                    c4.write(f"**Prevista:** {o['data_prevista'] or '—'}")

                    if o["custo_total"]:
                        cs1, cs2, cs3, cs4 = st.columns(4)
                        cs1.metric("Tecido", f"R${o['custo_tecido'] or 0:.2f}")
                        cs2.metric("Costura", f"R${o['custo_costura'] or 0:.2f}")
                        cs3.metric("Aviamentos", f"R${o['custo_aviamentos'] or 0:.2f}")
                        cs4.metric("Total/peça", f"R${(o['custo_total'] or 0)/o['quantidade']:.2f}")

                    if o["observacoes"]:
                        st.caption(f"📝 {o['observacoes']}")

                    # Change status
                    idx = STATUS_ORDER.index(o["status"]) if o["status"] in STATUS_ORDER else 0
                    new_status = st.select_slider(
                        "Avançar status",
                        options=STATUS_ORDER,
                        value=o["status"],
                        format_func=lambda x: STATUS_LABELS[x],
                        key=f"status_{o['id']}"
                    )
                    if new_status != o["status"]:
                        conclusao = datetime.now().strftime("%Y-%m-%d") if new_status == "pronto" else None
                        conn.execute(
                            "UPDATE ordens_producao SET status=?, data_conclusao=? WHERE id=?",
                            (new_status, conclusao, o["id"])
                        )
                        conn.commit()
                        st.success(f"Status atualizado para **{STATUS_LABELS[new_status]}**!")
                        st.rerun()

    # ── Nova ordem ──
    with tab_nova:
        st.subheader("Nova Ordem de Produção")

        tecidos_list     = rows_to_list(conn.execute("SELECT * FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())
        costureiras_list = rows_to_list(conn.execute("SELECT * FROM costureiras WHERE ativa=1").fetchall())
        costura_precos   = rows_to_list(conn.execute("SELECT * FROM costura_precos ORDER BY categoria").fetchall())
        catalogo_prod    = rows_to_list(conn.execute(
            "SELECT * FROM produtos_backbe WHERE ativo=1 ORDER BY nome"
        ).fetchall())

        with st.form("form_ordem"):
            # ── Produto ────────────────────────────────────────────────────
            st.markdown("#### Produto")
            c0a, c0b = st.columns([3, 1])
            _cat_nomes = ["(digitar nome livre)"] + [p["nome"] for p in catalogo_prod]
            prod_sel = c0a.selectbox("Selecionar do catálogo", _cat_nomes)
            ref = c0b.text_input("Referência (ex: BL-001)")

            # Se escolheu um produto do catálogo, pré-carrega dados
            _prod_cat = None
            if prod_sel != "(digitar nome livre)":
                _prod_cat = next((p for p in catalogo_prod if p["nome"] == prod_sel), None)

            produto = prod_sel if prod_sel != "(digitar nome livre)" else \
                      st.text_input("Nome do produto*", placeholder="Ex: Calça Itália")

            c3, c4, c5 = st.columns(3)
            quantidade  = c3.number_input("Quantidade (peças)", min_value=1, value=10, step=1)
            prioridade  = c4.selectbox("Prioridade", ["normal", "urgente", "baixa"])
            data_prev   = c5.date_input("Data prevista de entrega",
                                         value=datetime.today() + timedelta(days=14))

            # ── Tecido ─────────────────────────────────────────────────────
            st.markdown("#### Tecido")
            # Sugestão de metragem do catálogo (metros/peça × quantidade)
            _metros_sugerido = 0.0
            if _prod_cat and _prod_cat.get("metragem_cm") and _prod_cat["metragem_cm"] > 0:
                _metros_sugerido = round(_prod_cat["metragem_cm"] / 100 * quantidade, 2)

            c6, c7 = st.columns(2)
            tec_opts = {t["nome"]: t for t in tecidos_list}
            tec_nome = c6.selectbox("Tecido utilizado nesta produção",
                                    ["(sem tecido)"] + list(tec_opts.keys()))
            metros = c7.number_input(
                "Metros necessários (total)",
                min_value=0.0, step=0.1,
                value=_metros_sugerido,
                help="Pré-preenchido do catálogo se disponível"
            )

            custo_tec = 0.0
            if tec_nome != "(sem tecido)" and tec_nome in tec_opts:
                t_obj = tec_opts[tec_nome]
                pm = _calc_preco_metro(t_obj)
                custo_tec = round(pm * metros, 2)
                custo_tec_unit = round(custo_tec / quantidade, 2) if quantidade else 0
                st.markdown(
                    f"<div style='background:#EFF6FF;border-radius:8px;padding:8px 12px;"
                    f"font-size:13px;color:#1D4ED8'>"
                    f"Tecido: R${pm:.2f}/m × {metros:.1f}m = <b>R${custo_tec:.2f}</b> total"
                    f" &nbsp;|&nbsp; <b>R${custo_tec_unit:.2f}/peça</b></div>",
                    unsafe_allow_html=True
                )

            # ── Costura ────────────────────────────────────────────────────
            st.markdown("#### Costura")
            c8, c9 = st.columns(2)
            cos_opts = {c["nome"]: c for c in costureiras_list}
            cos_nome = c8.selectbox("Costureira", ["(a definir)"] + list(cos_opts.keys()))
            cat_opts = {cp["categoria"]: cp for cp in costura_precos}
            cat_cos  = c9.selectbox("Categoria da peça", list(cat_opts.keys()))

            custo_cos_unit = 0.0
            if cat_cos in cat_opts:
                cp_obj = cat_opts[cat_cos]
                if cos_nome != "(a definir)" and cos_nome in cos_opts:
                    tipo_cos = cos_opts[cos_nome]["tipo"]
                    custo_cos_unit = cp_obj["preco_mae"] if tipo_cos == "mae" else cp_obj["preco_terc"]
                    st.markdown(
                        f"<div style='background:#F0FDF4;border-radius:8px;padding:8px 12px;"
                        f"font-size:13px;color:#166534'>"
                        f"Costura ({cos_nome}): <b>R${custo_cos_unit:.2f}/peça</b>"
                        f" = R${custo_cos_unit*quantidade:.2f} total</div>",
                        unsafe_allow_html=True
                    )

            # ── Outros custos ──────────────────────────────────────────────
            st.markdown("#### Outros custos")
            c10, c11, c12 = st.columns(3)
            custo_corte = c10.number_input("Corte (R$/peça)", min_value=0.0, step=0.5, value=3.0)
            custo_avia  = c11.number_input("Aviamentos (R$/peça)", min_value=0.0, step=0.5, value=8.0)
            custo_emb   = c12.number_input("Embalagem (R$/peça)", min_value=0.0, step=0.5, value=10.0)

            custo_tec_unit_calc = (custo_tec / quantidade) if quantidade else 0
            custo_total_unit    = custo_tec_unit_calc + custo_cos_unit + custo_corte + custo_avia + custo_emb
            custo_total_total   = custo_total_unit * quantidade

            # ── Resumo CMV + sugestão de preço ────────────────────────────
            if custo_total_unit > 0:
                preco_min   = round(custo_total_unit * 2.0, 2)
                preco_ideal = round(custo_total_unit * 3.5, 2)
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#FFF0F6,#F5F3FF);
                            border-radius:12px;padding:14px 18px;margin-top:12px;
                            border:1.5px solid #DDD6FE">
                  <div style="font-size:11px;font-weight:700;color:#7C3AED;
                               text-transform:uppercase;letter-spacing:.05em;
                               margin-bottom:8px">Custo de Produção — CMV</div>
                  <div style="display:flex;gap:28px;flex-wrap:wrap">
                    <div>
                      <div style="font-size:22px;font-weight:900;color:#1a2f4a">
                        R${custo_total_unit:.2f}
                      </div>
                      <div style="font-size:11px;color:#6B7280">CMV / peça</div>
                    </div>
                    <div>
                      <div style="font-size:22px;font-weight:900;color:#374151">
                        R${custo_total_total:.2f}
                      </div>
                      <div style="font-size:11px;color:#6B7280">CMV total lote</div>
                    </div>
                    <div style="border-left:1.5px solid #DDD6FE;padding-left:20px">
                      <div style="font-size:13px;color:#6B7280">
                        Preço mínimo (2×) &nbsp;<b style="color:#B91C1C">R${preco_min:.2f}</b>
                      </div>
                      <div style="font-size:13px;color:#6B7280">
                        Preço ideal (3,5×) &nbsp;<b style="color:#059669">R${preco_ideal:.2f}</b>
                      </div>
                    </div>
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div style='background:#F9FAFB;border-radius:8px;padding:10px 14px;"
                    "font-size:13px;color:#9CA3AF'>Preencha os custos acima para ver o CMV.</div>",
                    unsafe_allow_html=True
                )

            obs = st.text_area("Observações")
            submitted = st.form_submit_button("Lançar Produção", type="primary")

            if submitted and produto and produto != "(digitar nome livre)":
                tec_id = tec_opts[tec_nome]["id"] if tec_nome in tec_opts else None
                cos_id = cos_opts[cos_nome]["id"] if cos_nome in cos_opts else None
                conn.execute("""
                    INSERT INTO ordens_producao
                    (produto, referencia, quantidade, tecido_id, tecido_metros,
                     costureira_id, status, prioridade, custo_tecido, custo_costura,
                     custo_corte, custo_aviamentos, custo_embalagem, custo_total,
                     data_prevista, observacoes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    produto, ref, quantidade, tec_id, metros,
                    cos_id, "modelagem", prioridade, custo_tec, custo_cos_unit * quantidade,
                    custo_corte * quantidade, custo_avia * quantidade, custo_emb * quantidade,
                    custo_total_total, str(data_prev), obs
                ))
                conn.commit()
                st.success(f"✅ Ordem de produção **{produto}** lançada! {quantidade} peças → Modelagem")
                st.rerun()

    # ── Tabela de costura ──
    with tab_costura:
        st.subheader("🪡 Tabela de Preços de Costura")
        st.caption("Mãe costureira = valores da planilha | Terceirizada = –30% do valor")

        precos = rows_to_list(conn.execute("SELECT * FROM costura_precos ORDER BY categoria").fetchall())

        edited = st.data_editor(
            pd.DataFrame(precos)[["id","categoria","descricao","preco_mae","preco_terc"]].rename(columns={
                "id": "ID", "categoria": "Categoria", "descricao": "Descrição",
                "preco_mae": "Mãe (R$)", "preco_terc": "Terceirizada (R$)"
            }),
            use_container_width=True,
            hide_index=True,
            height=min(40 + 36 * len(precos), 1200),
            disabled=["ID", "Terceirizada (R$)"],
            column_config={
                "Mãe (R$)": st.column_config.NumberColumn(format="R$%.2f"),
                "Terceirizada (R$)": st.column_config.NumberColumn(format="R$%.2f"),
            },
            key="tabela_costura"
        )

        if st.button("💾 Salvar alterações na tabela"):
            for _, row in edited.iterrows():
                preco_mae = row["Mãe (R$)"]
                preco_terc = round(preco_mae * 0.7, 2)
                conn.execute(
                    "UPDATE costura_precos SET preco_mae=?, preco_terc=?, categoria=?, descricao=? WHERE id=?",
                    (preco_mae, preco_terc, row["Categoria"], row["Descrição"], row["ID"])
                )
            conn.commit()
            st.success("✅ Tabela salva! Terceirizadas calculadas automaticamente (–30%).")
            st.rerun()

        st.divider()
        st.subheader("Gerenciar Costureiras")
        costureiras = rows_to_list(conn.execute("SELECT * FROM costureiras").fetchall())
        df_cos = pd.DataFrame(costureiras).rename(columns={"id":"ID","nome":"Nome","tipo":"Tipo","ativa":"Ativa"})
        st.dataframe(df_cos, hide_index=True, use_container_width=True)

        with st.form("nova_costureira"):
            col_n, col_t = st.columns(2)
            new_name = col_n.text_input("Nome da costureira")
            new_tipo = col_t.selectbox("Tipo", ["mae", "terceirizada"])
            if st.form_submit_button("➕ Adicionar"):
                if new_name:
                    conn.execute("INSERT INTO costureiras (nome, tipo) VALUES (?,?)", (new_name, new_tipo))
                    conn.commit()
                    st.success(f"Costureira **{new_name}** adicionada!")
                    st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 5 — CALCULADORA CMV
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "◇ Calculadora CMV":
    st.title("💰 Calculadora de CMV — Custo por Peça")

    conn = get_conn()
    tecidos_list  = rows_to_list(conn.execute("SELECT * FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())
    costura_precos = rows_to_list(conn.execute("SELECT * FROM costura_precos ORDER BY categoria").fetchall())
    conn.close()

    with st.form("form_cmv"):
        st.subheader("Informações da Peça")
        c1, c2 = st.columns(2)
        produto_nome = c1.text_input("Nome do produto")
        cat_cos = c2.selectbox("Categoria (para costura)", [cp["categoria"] for cp in costura_precos])

        st.subheader("🧵 Tecidos")
        st.caption("Adicione até 3 tecidos")
        linhas_tec = []
        tec_opts = {t["nome"]: t for t in tecidos_list}
        tec_nomes = ["(nenhum)"] + list(tec_opts.keys())

        for i in range(3):
            ca, cb, cc = st.columns([3, 2, 1])
            tn = ca.selectbox(f"Tecido {i+1}", tec_nomes, key=f"t{i}")
            tm = cb.number_input(f"Metros/peça", min_value=0.0, step=0.1, value=0.0, key=f"m{i}")
            if tn != "(nenhum)" and tm > 0 and tn in tec_opts:
                t_obj = tec_opts[tn]
                pm = _calc_preco_metro(t_obj)
                linhas_tec.append({"nome": tn, "metros": tm, "preco_m": pm, "custo": round(pm * tm, 2)})
                cc.metric("Custo", f"R${pm * tm:.2f}")

        st.subheader("🔩 Aviamentos e outros custos")
        c3, c4, c5, c6 = st.columns(4)
        corte     = c3.number_input("Corte (R$)", min_value=0.0, value=3.0, step=0.5)
        aviamentos = c4.number_input("Aviamentos (R$)", min_value=0.0, value=8.0, step=0.5)
        embalagem = c5.number_input("Embalagem (R$)", min_value=0.0, value=10.0, step=0.5)
        adicional = c6.number_input("Custo adicional (R$)", min_value=0.0, value=0.0, step=0.5)

        st.subheader("🪡 Costura")
        c7, c8 = st.columns(2)
        tipo_cos = c7.radio("Tipo de costureira", ["Mãe", "Terceirizada"], horizontal=True)
        cp_sel = next((cp for cp in costura_precos if cp["categoria"] == cat_cos), None)
        if cp_sel:
            preco_cos = cp_sel["preco_mae"] if tipo_cos == "Mãe" else cp_sel["preco_terc"]
            c8.metric(f"Costura ({tipo_cos})", f"R${preco_cos:.2f}")
        else:
            preco_cos = 0.0
            preco_cos = c8.number_input("Costura manual (R$)", min_value=0.0, value=0.0, step=0.5)

        st.subheader("⚙️ Overhead")
        overhead_pct = st.slider("Overhead (%)", min_value=0, max_value=20, value=10,
                                  help="Energia, aluguel, depreciação sobre subtotal")

        calcular = st.form_submit_button("🧮 Calcular CMV", type="primary")

    if calcular:
        custo_tec = sum(l["custo"] for l in linhas_tec)
        subtotal = custo_tec + corte + aviamentos + embalagem + adicional + preco_cos
        overhead_val = subtotal * overhead_pct / 100
        cmv = subtotal + overhead_val

        preco_min   = round(cmv * 2.0, 2)
        preco_3x    = round(cmv * 3.0, 2)
        preco_ideal = round(cmv * 3.5, 2)

        st.divider()
        st.subheader(f"Resultado — {produto_nome or 'Peça'}")

        # Breakdown
        col_res, col_prec = st.columns(2)
        with col_res:
            st.markdown("**Composição do CMV**")
            items = []
            for l in linhas_tec:
                items.append({"Item": f"Tecido: {l['nome']} ({l['metros']:.1f}m)", "Valor": f"R${l['custo']:.2f}"})
            items += [
                {"Item": "Corte", "Valor": f"R${corte:.2f}"},
                {"Item": f"Costura ({tipo_cos})", "Valor": f"R${preco_cos:.2f}"},
                {"Item": "Aviamentos", "Valor": f"R${aviamentos:.2f}"},
                {"Item": "Embalagem", "Valor": f"R${embalagem:.2f}"},
            ]
            if adicional > 0:
                items.append({"Item": "Custo adicional", "Valor": f"R${adicional:.2f}"})
            items.append({"Item": f"Overhead ({overhead_pct}%)", "Valor": f"R${overhead_val:.2f}"})
            items.append({"Item": "━━ CMV TOTAL", "Valor": f"**R${cmv:.2f}**"})
            st.table(pd.DataFrame(items))

        with col_prec:
            st.markdown("**Sugestão de Preço**")
            status_markup = "✅ Margem Boa" if cmv * 3.5 <= cmv * 4 else "✅"
            st.metric("Preço Mínimo (2x CMV)", f"R${preco_min:.2f}", help="Abaixo disso a margem é insustentável")
            st.metric("Markup 3,0x", f"R${preco_3x:.2f}", help="Mínimo saudável Backbe")
            st.metric("🎯 Preço Ideal (3,5x)", f"R${preco_ideal:.2f}", help="Meta padrão Backbe",
                       delta="META")
            st.divider()
            markup_check = st.number_input("Verificar preço de venda", min_value=0.0, step=5.0,
                                            value=preco_ideal)
            if markup_check > 0:
                mk = markup_check / cmv
                margem = (markup_check - cmv) / markup_check * 100
                taxas = markup_check * 0.056
                lucro = markup_check - cmv - taxas
                status = "✅ Margem Boa" if mk >= 2.6 else "⚠️ Margem Baixa"
                if mk < 1.5:
                    status = "🚨 ABAIXO DO MÍNIMO"
                st.metric("Markup", f"{mk:.1f}x", delta=f"Margem {margem:.0f}%")
                st.metric("Lucro líquido/peça", f"R${lucro:.2f}", delta=f"Taxas -R${taxas:.2f}")
                st.write(f"**Status:** {status}")

# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — FINANCEIRO (DRE Mensal)
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "▣ Financeiro":
    conn = get_conn()
    MESES_NOME = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    MESES_ABREV = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

    # ── helpers ──────────────────────────────────────────────────────────────
    def _f(v):  return f"R$ {float(v or 0):,.2f}"
    def _pct(v): return f"{float(v or 0):.1f}%"

    # ── selecionar ano ────────────────────────────────────────────────────────
    hcol1, hcol2 = st.columns([3, 1])
    hcol1.title("💳 Controle Financeiro")
    _anos_disp = list(range(2024, 2029))
    _ano_atual = datetime.now().year
    _idx_ano   = _anos_disp.index(_ano_atual) if _ano_atual in _anos_disp else 2
    ano_fin = hcol2.selectbox("Ano", _anos_disp, index=_idx_ano, key="fin_ano")

    # ── garante 12 registros ─────────────────────────────────────────────────
    for m in range(1, 13):
        conn.execute("INSERT OR IGNORE INTO dre_custos (ano, mes) VALUES (?,?)", (ano_fin, m))
    conn.commit()

    def _load_custos():
        return {r["mes"]: r for r in rows_to_list(
            conn.execute("SELECT * FROM dre_custos WHERE ano=? ORDER BY mes", (ano_fin,)).fetchall()
        )}

    custos = _load_custos()

    # ── receita Nuvemshop ─────────────────────────────────────────────────────
    try:
        all_orders = fetch_all_orders()
        rev_mes_ns, vnd_mes_ns = {}, {}
        for o in all_orders:
            d = o["created_at"][:7]
            yr, mn = int(d[:4]), int(d[5:7])
            if yr == ano_fin:
                rev_mes_ns[mn] = rev_mes_ns.get(mn, 0) + float(o.get("total") or 0)
                vnd_mes_ns[mn] = vnd_mes_ns.get(mn, 0) + 1
    except Exception:
        rev_mes_ns, vnd_mes_ns = {}, {}

    # ── função de cálculo do mês ──────────────────────────────────────────────
    def _calc_mes(c, fat, vendas, pct_m, pct_b):
        alug1  = float(c.get("aluguel_sala1") or 0)
        alug2  = float(c.get("aluguel_sala2") or 0)
        en1    = float(c.get("energia_sala1") or 0)
        en2    = float(c.get("energia_sala2") or 0)
        in1    = float(c.get("internet_sala1") or 0)
        in2    = float(c.get("internet_sala2") or 0)
        outros = float(c.get("outros_fixos") or 0)
        prol   = float(c.get("pro_labore") or 0)
        cmv    = float(c.get("cmv_estimado") or 0)
        imp    = float(c.get("impostos") or 0)
        com_m  = round(fat * pct_m / 100, 2)
        com_b  = round(fat * pct_b / 100, 2)
        fixos  = alug1 + alug2 + en1 + en2 + in1 + in2 + outros + prol + imp
        total  = fixos + com_m + com_b + cmv
        lucro  = fat - total
        margem = (lucro / fat * 100) if fat else 0.0
        ticket = (fat / vendas) if vendas else 0.0
        return dict(alug1=alug1, alug2=alug2, en1=en1, en2=en2, in1=in1, in2=in2,
                    outros=outros, prol=prol, cmv=cmv, imp=imp,
                    com_m=com_m, com_b=com_b, fixos=fixos, total=total,
                    lucro=lucro, margem=margem, ticket=ticket)

    # ── KPIs do ano (sempre visíveis no topo) ─────────────────────────────────
    pct_mae_top   = float(custos[1].get("comissao_mae_pct")   or 2.0)
    pct_bella_top = float(custos[1].get("comissao_bella_pct") or 10.0)
    fat_ano_tot   = sum(
        (float(custos[m].get("faturamento_manual") or rev_mes_ns.get(m, 0)))
        for m in range(1, 13)
    )
    lucro_meses = []
    for m in range(1, 13):
        c = custos[m]
        fat_m = float(c.get("faturamento_manual") or rev_mes_ns.get(m, 0))
        r = _calc_mes(c, fat_m, vnd_mes_ns.get(m, 0), pct_mae_top, pct_bella_top)
        lucro_meses.append(r["lucro"])
    lucro_ano_tot = sum(lucro_meses)
    mg_ano_tot    = (lucro_ano_tot / fat_ano_tot * 100) if fat_ano_tot else 0

    kp1, kp2, kp3, kp4 = st.columns(4)
    kp1.metric("💰 Faturamento {0}".format(ano_fin), _f(fat_ano_tot))
    kp2.metric("✅ Lucro acumulado",   _f(lucro_ano_tot),
               delta=f"{mg_ano_tot:.1f}% margem",
               delta_color="normal" if lucro_ano_tot >= 0 else "inverse")
    meses_com_fat = [m for m in range(1,13) if float(custos[m].get("faturamento_manual") or rev_mes_ns.get(m,0)) > 0]
    if meses_com_fat:
        best_m = max(meses_com_fat, key=lambda m: float(custos[m].get("faturamento_manual") or rev_mes_ns.get(m,0)))
        kp3.metric("🏆 Melhor mês", MESES_ABREV[best_m-1],
                   delta=_f(float(custos[best_m].get("faturamento_manual") or rev_mes_ns.get(best_m,0))))
    else:
        kp3.metric("🏆 Melhor mês", "—")
    meses_preench = len([m for m in range(1,13) if float(custos[m].get("faturamento_manual") or rev_mes_ns.get(m,0)) > 0])
    kp4.metric("📅 Meses lançados", f"{meses_preench} / 12")

    st.divider()

    # ── tabs principais ───────────────────────────────────────────────────────
    tab_mes, tab_resumo, tab_extrato = st.tabs([
        "✏️ Lançamento Mensal",
        "📊 Resumo Anual",
        "🏦 Extrato Bancário",
    ])

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 1 — LANÇAMENTO POR MÊS                                         ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    with tab_mes:
        # Seletor de mês como botões horizontais
        st.markdown("**Selecionar mês:**")
        btn_cols = st.columns(12)
        if "fin_mes_sel" not in st.session_state:
            st.session_state["fin_mes_sel"] = datetime.now().month

        for i, ab in enumerate(MESES_ABREV):
            if btn_cols[i].button(ab, key=f"fin_btn_mes_{i+1}",
                                  type="primary" if st.session_state["fin_mes_sel"] == i+1 else "secondary",
                                  use_container_width=True):
                st.session_state["fin_mes_sel"] = i + 1
                st.rerun()

        mes_sel = st.session_state["fin_mes_sel"]
        c_mes   = custos[mes_sel]

        fat_ns_mes  = rev_mes_ns.get(mes_sel, 0.0)
        fat_man_mes = c_mes.get("faturamento_manual")
        fat_init    = float(fat_man_mes) if fat_man_mes is not None else fat_ns_mes
        vnd_ns_mes  = vnd_mes_ns.get(mes_sel, 0)
        vnd_man_mes = c_mes.get("vendas_manual")
        vnd_init    = int(vnd_man_mes) if vnd_man_mes is not None else vnd_ns_mes

        pct_m_init = float(c_mes.get("comissao_mae_pct")   or 2.0)
        pct_b_init = float(c_mes.get("comissao_bella_pct") or 10.0)

        st.markdown(f"### {MESES_NOME[mes_sel-1]} {ano_fin}")
        st.markdown("---")

        # ── RECEITA ──────────────────────────────────────────────────────────
        st.markdown("##### 💵 Receita")
        r1c1, r1c2, r1c3 = st.columns(3)
        fat_v   = r1c1.number_input("Faturamento (R$)", min_value=0.0, step=100.0,
                                    value=fat_init, key=f"fin_fat_{mes_sel}",
                                    help="Pré-preenchido com dados da Nuvemshop. Edite se necessário.")
        vnd_v   = r1c2.number_input("Nº de Vendas", min_value=0, step=1,
                                    value=vnd_init, key=f"fin_vnd_{mes_sel}")
        ticket_v = fat_v / vnd_v if vnd_v else 0.0
        r1c3.metric("Ticket Médio", _f(ticket_v))
        if fat_ns_mes > 0 and fat_man_mes is not None:
            st.caption(f"ℹ️ Nuvemshop registrou {_f(fat_ns_mes)} — você está usando valor manual.")

        st.markdown("---")

        # ── PESSOAL ───────────────────────────────────────────────────────────
        st.markdown("##### 👤 Pessoal")
        p1, p2, p3, p4, p5 = st.columns([2, 1, 1, 1, 1])
        prol_v  = p1.number_input("Pró-labore (R$)", min_value=0.0, step=50.0,
                                  value=float(c_mes.get("pro_labore") or 0), key=f"fin_prol_{mes_sel}")
        pct_m_v = p2.number_input("% Comis. Mãe", min_value=0.0, max_value=100.0, step=0.5,
                                  value=pct_m_init, key=f"fin_pctm_{mes_sel}")
        com_m_v = round(fat_v * pct_m_v / 100, 2)
        p3.metric("Com. Mãe", _f(com_m_v))
        pct_b_v = p4.number_input("% Comis. Bella", min_value=0.0, max_value=100.0, step=0.5,
                                  value=pct_b_init, key=f"fin_pctb_{mes_sel}")
        com_b_v = round(fat_v * pct_b_v / 100, 2)
        p5.metric("Com. Bella", _f(com_b_v))

        st.markdown("---")

        # ── ESTRUTURA ─────────────────────────────────────────────────────────
        st.markdown("##### 🏢 Estrutura")
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        alug1_v = e1.number_input("Aluguel Sala 1", min_value=0.0, step=50.0,
                                  value=float(c_mes.get("aluguel_sala1") or 0), key=f"fin_alug1_{mes_sel}")
        en1_v   = e2.number_input("Energia Sala 1", min_value=0.0, step=20.0,
                                  value=float(c_mes.get("energia_sala1") or 0), key=f"fin_en1_{mes_sel}")
        in1_v   = e3.number_input("Internet Sala 1", min_value=0.0, step=10.0,
                                  value=float(c_mes.get("internet_sala1") or 0), key=f"fin_in1_{mes_sel}")
        alug2_v = e4.number_input("Aluguel Sala 2", min_value=0.0, step=50.0,
                                  value=float(c_mes.get("aluguel_sala2") or 0), key=f"fin_alug2_{mes_sel}")
        en2_v   = e5.number_input("Energia Sala 2", min_value=0.0, step=20.0,
                                  value=float(c_mes.get("energia_sala2") or 0), key=f"fin_en2_{mes_sel}")
        in2_v   = e6.number_input("Internet Sala 2", min_value=0.0, step=10.0,
                                  value=float(c_mes.get("internet_sala2") or 0), key=f"fin_in2_{mes_sel}")

        st.markdown("---")

        # ── VARIÁVEIS / OUTROS ────────────────────────────────────────────────
        st.markdown("##### 📦 Variáveis e Outros")
        v1, v2, v3 = st.columns(3)
        cmv_v   = v1.number_input("CMV Estimado (R$)", min_value=0.0, step=100.0,
                                  value=float(c_mes.get("cmv_estimado") or 0), key=f"fin_cmv_{mes_sel}")
        imp_v   = v2.number_input("Impostos (R$)", min_value=0.0, step=20.0,
                                  value=float(c_mes.get("impostos") or 0), key=f"fin_imp_{mes_sel}")
        outros_v = v3.number_input("Outros (R$)", min_value=0.0, step=20.0,
                                   value=float(c_mes.get("outros_fixos") or 0), key=f"fin_outros_{mes_sel}")

        st.markdown("---")

        # ── RESULTADO CALCULADO ───────────────────────────────────────────────
        total_fixos_v  = alug1_v + alug2_v + en1_v + en2_v + in1_v + in2_v + prol_v + imp_v + outros_v
        total_custos_v = total_fixos_v + com_m_v + com_b_v + cmv_v
        lucro_v        = fat_v - total_custos_v
        margem_v       = (lucro_v / fat_v * 100) if fat_v else 0.0

        res_style = "normal" if lucro_v >= 0 else "inverse"
        st.markdown("##### 📈 Resultado")
        rr1, rr2, rr3, rr4 = st.columns(4)
        rr1.metric("Total Custos",   _f(total_custos_v))
        rr2.metric("Lucro Líquido",  _f(lucro_v),
                   delta=f"{margem_v:.1f}% margem", delta_color=res_style)
        rr3.metric("Custos Fixos",   _f(total_fixos_v))
        rr4.metric("Comissões",      _f(com_m_v + com_b_v))

        st.markdown(" ")
        sv1, sv2 = st.columns([1, 5])
        if sv1.button("💾 Salvar mês", type="primary", key="fin_sv_mes"):
            fat_man_save = fat_v if abs(fat_v - fat_ns_mes) > 0.01 else None
            vnd_man_save = vnd_v if vnd_v != vnd_ns_mes else None
            conn.execute("""
                UPDATE dre_custos SET
                    faturamento_manual=?, vendas_manual=?,
                    aluguel_sala1=?, aluguel_sala2=?,
                    energia_sala1=?, energia_sala2=?,
                    internet_sala1=?, internet_sala2=?,
                    pro_labore=?, cmv_estimado=?, impostos=?,
                    outros_fixos=?,
                    comissao_mae_pct=?, comissao_bella_pct=?
                WHERE ano=? AND mes=?
            """, (fat_man_save, vnd_man_save,
                  alug1_v, alug2_v, en1_v, en2_v, in1_v, in2_v,
                  prol_v, cmv_v, imp_v, outros_v,
                  pct_m_v, pct_b_v, ano_fin, mes_sel))
            conn.commit()
            st.success(f"✅ {MESES_NOME[mes_sel-1]} salvo!")
            st.rerun()

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 2 — RESUMO ANUAL (tabela compacta, leitura)                    ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    with tab_resumo:
        st.markdown("#### Resumo {0} — todos os meses".format(ano_fin))
        st.caption("Visão consolidada. Para editar, use a aba ✏️ Lançamento Mensal.")

        resumo_rows = []
        for m in range(1, 13):
            c  = custos[m]
            fat_m  = float(c.get("faturamento_manual") or rev_mes_ns.get(m, 0))
            vnd_m  = int(c.get("vendas_manual") or vnd_mes_ns.get(m, 0))
            pct_m  = float(c.get("comissao_mae_pct")   or 2.0)
            pct_b  = float(c.get("comissao_bella_pct") or 10.0)
            r      = _calc_mes(c, fat_m, vnd_m, pct_m, pct_b)
            resumo_rows.append({
                "Mês":          MESES_NOME[m-1],
                "Faturamento":  fat_m,
                "Vendas":       vnd_m,
                "Ticket Médio": round(r["ticket"], 2),
                "Total Custos": round(r["total"], 2),
                "Lucro":        round(r["lucro"], 2),
                "Margem %":     round(r["margem"], 1),
                "Status":       "🟢" if r["lucro"] >= 0 and fat_m > 0 else ("🔴" if fat_m > 0 else "⬜"),
            })

        df_resumo = pd.DataFrame(resumo_rows)
        st.dataframe(
            df_resumo,
            use_container_width=True,
            hide_index=True,
            height=40 + 36 * 13,
            column_config={
                "Faturamento":  st.column_config.NumberColumn(format="R$%.2f"),
                "Ticket Médio": st.column_config.NumberColumn(format="R$%.2f"),
                "Total Custos": st.column_config.NumberColumn(format="R$%.2f"),
                "Lucro":        st.column_config.NumberColumn(format="R$%.2f"),
                "Margem %":     st.column_config.NumberColumn(format="%.1f%%"),
                "Status":       st.column_config.TextColumn(width="small"),
            }
        )

        # totais
        fat_t = sum(r["Faturamento"] for r in resumo_rows)
        cus_t = sum(r["Total Custos"] for r in resumo_rows)
        luc_t = sum(r["Lucro"] for r in resumo_rows)
        mg_t  = (luc_t / fat_t * 100) if fat_t else 0
        st.divider()
        tc1,tc2,tc3,tc4 = st.columns(4)
        tc1.metric("Total Faturamento", _f(fat_t))
        tc2.metric("Total Custos",      _f(cus_t))
        tc3.metric("Total Lucro",       _f(luc_t))
        tc4.metric("Margem Média",      _pct(mg_t))

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 3 — EXTRATO BANCÁRIO                                           ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    with tab_extrato:
        ecol1, ecol2 = st.columns([2, 4])
        mes_ext = ecol1.selectbox("Mês", range(1, 13),
                                  format_func=lambda m: MESES_NOME[m-1], key="fin_mes_ext")
        ecol2.info(f"Envie o extrato Nubank ou InfinitePay de **{MESES_NOME[mes_ext-1]} {ano_fin}** em PDF.")

        up_ext = st.file_uploader("Selecionar PDF(s)", type=["pdf"],
                                  accept_multiple_files=True, key=f"fin_up_{ano_fin}_{mes_ext}")

        if up_ext:
            if st.button(f"⚙️ Processar {len(up_ext)} arquivo(s)", type="primary", key="fin_proc"):
                novos = 0
                with st.spinner("Lendo PDFs..."):
                    for f in up_ext:
                        resultado = parse_nubank_pdf(f.read(), f.name)
                        for t in resultado["transacoes"]:
                            if t.get("data"):
                                try:
                                    parts   = t["data"].split("/")
                                    tx_mes  = int(parts[1])
                                    tx_ano  = int(parts[2])
                                    if tx_ano != ano_fin or tx_mes != mes_ext:
                                        continue
                                except Exception:
                                    pass
                            conn.execute("""
                                INSERT INTO dre_transacoes
                                (ano, mes, data, descricao, valor, tipo, arquivo)
                                VALUES (?,?,?,?,?,?,?)
                            """, (ano_fin, mes_ext, t["data"], t["descricao"],
                                  t["valor"], t["tipo"], f.name))
                            novos += 1
                conn.commit()
                if novos:
                    st.success(f"✅ {novos} transações importadas!")
                else:
                    st.warning("Nenhuma transação encontrada para este mês/ano.")
                st.rerun()

        st.divider()

        txs_ext = rows_to_list(conn.execute(
            "SELECT * FROM dre_transacoes WHERE ano=? AND mes=? ORDER BY data, tipo",
            (ano_fin, mes_ext)
        ).fetchall())

        if not txs_ext:
            st.info("Nenhuma transação para este mês. Faça upload do extrato acima.")
        else:
            entradas_e = [t for t in txs_ext if t["tipo"] == "entrada"]
            saidas_e   = [t for t in txs_ext if t["tipo"] == "saida"]
            tot_ent = sum(t["valor"] for t in entradas_e if t.get("contar"))
            tot_sai = sum(t["valor"] for t in saidas_e   if t.get("contar"))

            ek1, ek2, ek3 = st.columns(3)
            ek1.metric("📥 Entradas", _f(tot_ent), f"{len(entradas_e)} transações")
            ek2.metric("📤 Saídas",   _f(tot_sai), f"{len(saidas_e)} transações")
            ek3.metric("💰 Saldo",    _f(tot_ent - tot_sai))

            te, ts = st.tabs(["📥 Entradas", "📤 Saídas"])
            for _tab, _lista, _key in [(te, entradas_e, "ent"), (ts, saidas_e, "sai")]:
                with _tab:
                    if _lista:
                        st.dataframe(
                            pd.DataFrame([{"Data": t["data"], "Descrição": t["descricao"],
                                           "Valor": t["valor"]} for t in _lista]),
                            use_container_width=True, hide_index=True,
                            height=min(40 + 36*len(_lista), 3000),
                            column_config={"Valor": st.column_config.NumberColumn(format="R$%.2f")}
                        )
                    else:
                        st.info("Nenhuma transação nesta categoria.")

            st.markdown(" ")
            if st.button("🗑️ Limpar transações deste mês", key="fin_clear_ext"):
                conn.execute("DELETE FROM dre_transacoes WHERE ano=? AND mes=?", (ano_fin, mes_ext))
                conn.commit()
                st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 6 — CRESCIMENTO
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "↗ Crescimento":
    st.title("📈 Probabilidade de Crescimento")

    if not ns_monthly:
        st.warning("Sem dados da Nuvemshop para análise.")
    else:
        months = sorted(ns_monthly.keys())
        revenues = [ns_monthly[m]["revenue"] for m in months]
        orders_ct = [ns_monthly[m]["orders"] for m in months]

        # Trend calculation (linear regression over last 6 months)
        recent = revenues[-6:] if len(revenues) >= 6 else revenues
        n = len(recent)
        if n >= 3:
            x = list(range(n))
            xm = sum(x) / n
            ym = sum(recent) / n
            slope = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, recent)) / \
                    sum((xi - xm) ** 2 for xi in x)
            intercept = ym - slope * xm
            trend_next = intercept + slope * n
            trend_pct = slope / ym * 100 if ym else 0

            # Growth probability (simple scoring)
            score = 0
            if slope > 0:
                score += 40
            if len(revenues) >= 3 and revenues[-1] > revenues[-3]:
                score += 20
            if revenues[-1] > sum(revenues) / len(revenues):
                score += 20
            if len(orders_ct) >= 2 and orders_ct[-1] > orders_ct[-2]:
                score += 20
            prob = min(score, 95)

            st.subheader("Tendência dos últimos 6 meses")
            col1, col2, col3 = st.columns(3)
            col1.metric("Tendência mensal", f"R${slope:+,.0f}/mês",
                         delta="crescimento" if slope > 0 else "queda",
                         delta_color="normal" if slope > 0 else "inverse")
            col2.metric("Projeção próximo mês", f"R${max(0, trend_next):,.0f}")
            col3.metric("Probabilidade de crescimento", f"{prob}%",
                         delta="positivo" if prob >= 60 else "atenção")

        # Chart
        st.subheader("Histórico completo + Projeção")
        df_trend = pd.DataFrame({"Mês": months, "Receita": revenues})
        fig_t = px.line(df_trend, x="Mês", y="Receita", markers=True,
                        color_discrete_sequence=[PINK], title="Receita Mensal")
        if n >= 3:
            proj_months = [months[-1]]
            proj_rev = [revenues[-1]]
            for i in range(1, 4):
                from datetime import date
                last = date.fromisoformat(months[-1] + "-01")
                next_m = (last.replace(day=1) + timedelta(days=32)).replace(day=1)
                proj_months.append(next_m.strftime("%Y-%m"))
                proj_rev.append(max(0, intercept + slope * (n - 1 + i)))
            fig_t.add_scatter(x=proj_months, y=proj_rev, mode="lines+markers",
                              line=dict(color=GOLD, width=2, dash="dash"),
                              marker=dict(size=8, symbol="diamond"),
                              name="Projeção 3 meses")
        fig_t.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                             yaxis_title="R$", xaxis_title="")
        st.plotly_chart(fig_t, width="stretch")

        # Sazonality
        st.subheader("Sazonalidade por mês do ano")
        by_month_num = {}
        for m, rev in zip(months, revenues):
            mn = int(m.split("-")[1])
            by_month_num.setdefault(mn, []).append(rev)
        season = {m: sum(vs)/len(vs) for m, vs in by_month_num.items()}
        month_names = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        df_season = pd.DataFrame([
            {"Mês": month_names[m-1], "Receita média": v}
            for m, v in sorted(season.items())
        ])
        fig_s = px.bar(df_season, x="Mês", y="Receita média",
                        color_discrete_sequence=[NAVY], text_auto=".2s")
        fig_s.update_layout(plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_s, width="stretch")

        # Recommendations
        st.subheader("📋 Recomendações")
        best_month = month_names[max(season, key=season.get) - 1]
        worst_month = month_names[min(season, key=season.get) - 1]
        avg_rev = sum(revenues) / len(revenues) if revenues else 0
        st.info(f"""
        **Mês mais forte:** {best_month} (média R${season[max(season, key=season.get)]:,.0f})
        **Mês mais fraco:** {worst_month} (média R${season[min(season, key=season.get)]:,.0f})
        **Receita média mensal:** R${avg_rev:,.0f}

        💡 Lançar coleção nova **4–6 semanas antes** de {best_month} para capturar o pico.
        💡 Usar meses fracos para desenvolvimento de produto e controle de estoque.
        """)

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 7 — DECLARAÇÃO MEI
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⊛ Declaracao MEI":
    st.title("📄 Declaração Anual MEI — DASN-SIMEI")
    st.caption("Envie o extrato Nubank em PDF para calcular a receita bruta de cada MEI")

    MEIs = {
        "isabela": "Isabela Dagostim",
        "juliana": "Juliana Dagostim",
    }

    conn = get_conn()

    # Garante que as declarações existem no banco para o ano selecionado
    ano_sel = st.selectbox("Ano de referência", [2025, 2024, 2026], index=0)

    for mei_key, mei_nome in MEIs.items():
        conn.execute(
            "INSERT OR IGNORE INTO mei_declaracoes (mei_nome, mei_razao, ano) VALUES (?,?,?)",
            (mei_key, mei_nome, ano_sel)
        )
    conn.commit()

    tab_isa, tab_jul, tab_resumo = st.tabs([
        "👩 Isabela Dagostim",
        "👩 Juliana Dagostim",
        "📊 Resumo DASN-SIMEI",
    ])

    def render_mei_tab(mei_key: str, mei_nome: str, tab):
        with tab:
            st.subheader(f"{mei_nome} — {ano_sel}")

            dec = row_to_dict(conn.execute(
                "SELECT * FROM mei_declaracoes WHERE mei_nome=? AND ano=?",
                (mei_key, ano_sel)
            ).fetchone())
            dec_id = dec["id"]

            # ── Mostra resultado de processamento anterior (persistido via session_state) ──
            res_key = f"proc_result_{mei_key}_{ano_sel}"
            if res_key in st.session_state:
                res = st.session_state.pop(res_key)
                if res["novos"] > 0:
                    st.success(f"✅ {res['novos']} transações importadas de {res['arquivos']} arquivo(s)!")
                elif res["filtrados"] > 0:
                    st.warning(
                        f"⚠️ Encontrei {res['filtrados']} transações nos PDFs, mas **todas são de um ano diferente de {ano_sel}**. "
                        f"Mude o ano acima para o correto e processe novamente."
                    )
                elif res["total_pdf"] > 0:
                    st.warning(
                        f"⚠️ {res['total_pdf']} transações encontradas nos PDFs mas nenhuma foi importada. "
                        f"Verifique se o ano selecionado ({ano_sel}) está correto."
                    )
                else:
                    st.error("❌ Nenhuma transação encontrada nos PDFs. Confirme que são extratos Nubank válidos.")
                for e in res.get("erros", []):
                    st.warning(e)
                if res.get("debug_msgs"):
                    with st.expander("🔍 Debug — clique para ver detalhes do parser"):
                        for dm in res["debug_msgs"]:
                            st.markdown(dm)

            # ── Upload de PDFs ──
            st.markdown("#### 📎 Enviar Extratos Nubank (PDF)")
            st.info(
                "Envie um ou mais PDFs do extrato da conta Nubank deste MEI. "
                "Podem ser extratos mensais ou o extrato anual completo."
            )

            uploaded = st.file_uploader(
                "Selecionar PDF(s)",
                type=["pdf"],
                accept_multiple_files=True,
                key=f"upload_{mei_key}",
            )

            if uploaded:
                if st.button(f"⚙️ Processar {len(uploaded)} arquivo(s)", key=f"proc_{mei_key}", type="primary"):
                    novos = 0
                    filtrados = 0
                    total_pdf = 0
                    erros_total = []
                    debug_msgs = []
                    with st.spinner("Lendo PDFs..."):
                        for f in uploaded:
                            pdf_bytes = f.read()
                            resultado = parse_nubank_pdf(pdf_bytes, f.name)

                            # Coleta debug info
                            dbg = resultado.get("debug", {})
                            debug_msgs.append(
                                f"**{f.name}** — parser v{dbg.get('version','?')}, "
                                f"{dbg.get('linhas_total',0)} linhas, "
                                f"formato={dbg.get('formato','?')}, "
                                f"{len(resultado['transacoes'])} transações\n"
                                + "\n".join(f"  `{l}`" for l in dbg.get("primeiras_linhas", [])[:8])
                            )

                            if resultado["erros"]:
                                erros_total.extend([f"**{f.name}**: {e}" for e in resultado["erros"]])

                            total_pdf += len(resultado["transacoes"])
                            for t in resultado["transacoes"]:
                                # Filtra pelo ano selecionado
                                if t["data"]:
                                    try:
                                        ano_tx = int(t["data"].split("/")[2])
                                        if ano_tx != ano_sel:
                                            filtrados += 1
                                            continue
                                    except Exception:
                                        pass
                                try:
                                    conn.execute("""
                                        INSERT INTO mei_transacoes
                                        (declaracao_id, data, descricao, valor, tipo, contar_receita, arquivo)
                                        VALUES (?,?,?,?,?,?,?)
                                    """, (
                                        dec_id, t["data"], t["descricao"], t["valor"],
                                        t["tipo"], 1 if t["tipo"] == "entrada" else 0, f.name
                                    ))
                                    novos += 1
                                except Exception as e_db:
                                    erros_total.append(f"Erro ao salvar transação: {e_db}")

                    # Recalcula receita bruta
                    rb = conn.execute(
                        "SELECT COALESCE(SUM(ABS(valor)),0) FROM mei_transacoes "
                        "WHERE declaracao_id=? AND tipo='entrada' AND contar_receita=1",
                        (dec_id,)
                    ).fetchone()[0]
                    conn.execute(
                        "UPDATE mei_declaracoes SET receita_bruta=? WHERE id=?",
                        (rb, dec_id)
                    )
                    conn.commit()

                    # Salva resultado em session_state para mostrar após rerun
                    st.session_state[res_key] = {
                        "novos": novos,
                        "filtrados": filtrados,
                        "total_pdf": total_pdf,
                        "arquivos": len(uploaded),
                        "erros": erros_total,
                        "debug_msgs": debug_msgs,
                    }
                    st.rerun()

            st.divider()

            # ── Transações salvas ──
            txs = rows_to_list(conn.execute(
                "SELECT * FROM mei_transacoes WHERE declaracao_id=? ORDER BY data",
                (dec_id,)
            ).fetchall())

            if not txs:
                st.info("Nenhuma transação importada ainda. Envie o PDF acima.")
            else:
                entradas = [t for t in txs if t["tipo"] == "entrada"]
                saidas = [t for t in txs if t["tipo"] == "saida"]
                receita = sum(abs(t["valor"]) for t in entradas if t["contar_receita"])

                k1, k2, k3 = st.columns(3)
                k1.metric("💰 Receita Bruta (DASN-SIMEI)", f"R${receita:,.2f}")
                k2.metric("📥 Total Entradas", f"R${sum(abs(t['valor']) for t in entradas):,.2f}", f"{len(entradas)} transações")
                k3.metric("📤 Total Saídas", f"R${sum(abs(t['valor']) for t in saidas):,.2f}", f"{len(saidas)} transações")

                st.divider()

                # Resumo por mês
                st.markdown("#### 📅 Receita por mês")
                por_mes = {}
                for t in entradas:
                    if not t["data"] or not t["contar_receita"]:
                        continue
                    try:
                        mes = t["data"][3:5] + "/" + t["data"][6:]
                        por_mes[mes] = por_mes.get(mes, 0) + abs(t["valor"])
                    except Exception:
                        pass

                if por_mes:
                    df_mes = pd.DataFrame(
                        sorted(por_mes.items()),
                        columns=["Mês", "Receita"]
                    )
                    df_mes["Receita fmt"] = df_mes["Receita"].apply(lambda x: f"R${x:,.2f}")
                    fig_mei = px.bar(
                        df_mes, x="Mês", y="Receita",
                        color_discrete_sequence=[GOLD],
                        text="Receita fmt",
                    )
                    fig_mei.update_traces(textposition="outside")
                    fig_mei.update_layout(
                        plot_bgcolor="white", paper_bgcolor="white",
                        yaxis_title="R$", xaxis_title="",
                        showlegend=False, margin=dict(t=30, b=0)
                    )
                    st.plotly_chart(fig_mei, use_container_width=True)

                # Tabela de transações com toggle para incluir/excluir
                st.markdown("#### 📋 Transações — Entradas")
                st.caption("Desmarque transações que NÃO são receita de negócio (ex: transferências pessoais, empréstimos)")

                df_tx = pd.DataFrame([{
                    "Incluir": bool(t["contar_receita"]),
                    "Data": t["data"] or "",
                    "Descrição": t["descricao"] or "",
                    "Valor (R$)": abs(t["valor"]),
                    "_id": t["id"],
                } for t in entradas])

                if not df_tx.empty:
                    edited_tx = st.data_editor(
                        df_tx.drop(columns=["_id"]),
                        use_container_width=True,
                        hide_index=True,
                        height=min(40 + 36 * len(df_tx), 5000),
                        column_config={
                            "Incluir": st.column_config.CheckboxColumn("Incluir na receita"),
                            "Valor (R$)": st.column_config.NumberColumn(format="R$%.2f"),
                        },
                        disabled=["Data", "Descrição", "Valor (R$)"],
                        key=f"tx_edit_{mei_key}",
                    )

                    if st.button("💾 Salvar seleção de receitas", key=f"save_tx_{mei_key}"):
                        for i, row in edited_tx.iterrows():
                            conn.execute(
                                "UPDATE mei_transacoes SET contar_receita=? WHERE id=?",
                                (1 if row["Incluir"] else 0, df_tx.iloc[i]["_id"])
                            )
                        # Recalcula receita bruta
                        rb = conn.execute(
                            "SELECT COALESCE(SUM(ABS(valor)),0) FROM mei_transacoes "
                            "WHERE declaracao_id=? AND tipo='entrada' AND contar_receita=1",
                            (dec_id,)
                        ).fetchone()[0]
                        conn.execute(
                            "UPDATE mei_declaracoes SET receita_bruta=? WHERE id=?",
                            (rb, dec_id)
                        )
                        conn.commit()
                        st.success("✅ Receita bruta recalculada!")

                if st.button("🗑️ Limpar todas as transações deste MEI/ano", key=f"clear_{mei_key}"):
                    conn.execute("DELETE FROM mei_transacoes WHERE declaracao_id=?", (dec_id,))
                    conn.execute("UPDATE mei_declaracoes SET receita_bruta=0 WHERE id=?", (dec_id,))
                    conn.commit()
                    st.success("✅ Transações removidas.")

    render_mei_tab("isabela", "Isabela Dagostim", tab_isa)
    render_mei_tab("juliana", "Juliana Dagostim", tab_jul)

    # ── Aba resumo DASN-SIMEI ──
    with tab_resumo:
        st.subheader(f"📊 Resumo para DASN-SIMEI — {ano_sel}")
        st.info(
            "A DASN-SIMEI pede a **Receita Bruta Total** do ano. "
            "Para um MEI de comércio (moda/vestuário), toda a receita entra como "
            "**comércio e/ou indústria**."
        )

        decs = rows_to_list(conn.execute(
            "SELECT * FROM mei_declaracoes WHERE ano=?", (ano_sel,)
        ).fetchall())

        total_geral = 0
        for d in decs:
            rb = d["receita_bruta"] or 0
            total_geral += rb
            st.markdown(f"""
<div style="background:#f4f1ee;border-left:4px solid {NAVY};padding:16px;border-radius:8px;margin-bottom:12px">
<b style="color:{NAVY};font-size:16px">{d['mei_razao']}</b><br>
<span style="font-size:28px;color:{PINK};font-weight:700">R${rb:,.2f}</span>
<span style="color:#666;margin-left:12px">Receita Bruta {ano_sel}</span>
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown(f"""
<div style="background:{NAVY};padding:20px;border-radius:8px;text-align:center">
<div style="color:#fff;font-size:14px;margin-bottom:4px">RECEITA BRUTA TOTAL (ambos os MEIs)</div>
<div style="color:{GOLD};font-size:36px;font-weight:700">R${total_geral:,.2f}</div>
<div style="color:#aaa;font-size:12px;margin-top:8px">Ano-calendário {ano_sel}</div>
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown("#### 📝 Como preencher a DASN-SIMEI")
        st.markdown(f"""
1. Acesse **gov.br/empresas** → **DASN-SIMEI**
2. Informe o CNPJ do MEI
3. No campo **"Receita Bruta Total"**:
   - Isabela Dagostim: **R${next((d['receita_bruta'] for d in decs if d['mei_nome']=='isabela'), 0):,.2f}**
   - Juliana Dagostim: **R${next((d['receita_bruta'] for d in decs if d['mei_nome']=='juliana'), 0):,.2f}**
4. Atividade: **Comércio** (venda de roupas/moda)
5. Empregado: verificar se contratou com carteira no ano

⚠️ Prazo: **31 de maio** de cada ano (ano seguinte ao de referência)

**CNPJs:**
- Isabela Dagostim: 60.499.292/0001-80
- Juliana Dagostim: 60.174.416/0001-58
        """)

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — ESTOQUE
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⊟ Estoque":
    st.title("Estoque")

    conn = get_conn()

    with st.spinner("Carregando estoque da Nuvemshop..."):
        try:
            _ns_prods = fetch_all_products()
            _inv_rows = parse_inventory(_ns_prods)
            _ns_ok = True
        except Exception as _e_inv:
            _inv_rows = []
            _ns_ok = False
            st.error(f"Erro ao conectar com Nuvemshop: {_e_inv}")

    # ── Dados de produção local ─────────────────────────────────────────────
    _em_prod_row = conn.execute(
        "SELECT SUM(custo_total) as total FROM ordens_producao WHERE status != 'pronto'"
    ).fetchone()
    _valor_producao = float(_em_prod_row["total"] or 0)

    _ordens_abertas = rows_to_list(conn.execute(
        "SELECT produto, quantidade, status, custo_total FROM ordens_producao "
        "WHERE status != 'pronto' ORDER BY status"
    ).fetchall())

    # ── KPIs principais ────────────────────────────────────────────────────
    _total_pecas  = sum(r["estoque"] for r in _inv_rows)
    _valor_inv    = sum(r["valor_total"] for r in _inv_rows)
    _skus_com_est = sum(1 for r in _inv_rows if r["estoque"] > 0)
    _lucro_est    = _valor_inv * 0.38

    def _fmt_brl(v):
        """Formata valor em reais sem vírgula que quebra linha (usa ponto)."""
        if v >= 1_000_000:
            return f"R$ {v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"R$ {v/1_000:.1f}k"
        return f"R$ {v:.0f}"

    # Grid 3 + 2 igual ao dashboard principal — sem 5 colunas estreitas
    _kcard = (
        "background:white;border-radius:14px;padding:16px 18px;"
        "border:1.5px solid #F0F0F0;box-shadow:0 2px 10px rgba(0,0,0,.05);"
        "min-width:0;overflow:hidden"
    )

    _ka, _kb, _kc = st.columns(3, gap="medium")
    _kd, _ke     = st.columns(2, gap="medium")

    for _col, _lbl, _val, _clr in [
        (_ka, "SKUs",         str(_skus_com_est),         "#1a2f4a"),
        (_kb, "Peças",        str(_total_pecas),           "#1a2f4a"),
        (_kc, "Inventário",   _fmt_brl(_valor_inv),        "#c96ba0"),
        (_kd, "Lucro est.",   _fmt_brl(_lucro_est),        "#059669"),
        (_ke, "Em produção",  _fmt_brl(_valor_producao),   "#b8860b"),
    ]:
        _col.markdown(f"""
        <div style="{_kcard}">
          <div style="font-size:11px;font-weight:600;color:#9CA3AF;
                      text-transform:uppercase;letter-spacing:.05em;
                      margin-bottom:6px;white-space:nowrap;overflow:hidden;
                      text-overflow:ellipsis">{_lbl}</div>
          <div style="font-size:clamp(18px,2.2vw,26px);font-weight:800;
                      color:{_clr};white-space:nowrap;line-height:1.1">
            {_val}
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    if _inv_rows:
        _df_inv = pd.DataFrame(_inv_rows)

        # ── Busca por nome ──────────────────────────────────────────────────
        _busca_nome = st.text_input(
            "Pesquisar produto",
            placeholder="Digite o nome do produto...",
            key="est_busca_nome",
        )

        # ── Filtros ─────────────────────────────────────────────────────────
        with st.expander("Filtros", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])

            _all_colors = sorted({r["cor"] for r in _inv_rows if r["cor"]})
            _all_sizes  = sorted(
                {r["tamanho"] for r in _inv_rows if r["tamanho"]},
                key=lambda s: ["PP","P","M","G","GG","XG","XGG"].index(s)
                if s in ["PP","P","M","G","GG","XG","XGG"] else 99
            )

            _filt_cor   = fc1.multiselect("Cor", _all_colors, default=[])
            _filt_tam   = fc2.multiselect("Tamanho", _all_sizes, default=[])
            _ord_opts   = {
                "Maior estoque": ("estoque", False),
                "Menor estoque": ("estoque", True),
                "Maior valor":   ("valor_total", False),
                "A-Z produto":   ("produto", True),
            }
            _ord_sel    = fc3.selectbox("Ordenar por", list(_ord_opts.keys()))
            _so_estoque = fc4.checkbox("Só com estoque", value=True)

        # Aplica filtros
        _df_f = _df_inv.copy()
        if _busca_nome:
            _df_f = _df_f[_df_f["produto"].str.contains(_busca_nome, case=False, na=False)]
        if _filt_cor:
            _df_f = _df_f[_df_f["cor"].isin(_filt_cor)]
        if _filt_tam:
            _df_f = _df_f[_df_f["tamanho"].isin(_filt_tam)]
        if _so_estoque:
            _df_f = _df_f[_df_f["estoque"] > 0]

        _col_sort, _asc = _ord_opts[_ord_sel]
        _df_f = _df_f.sort_values(_col_sort, ascending=_asc)

        # Renomeia colunas para exibição
        _df_show = _df_f.rename(columns={
            "produto": "Produto",
            "cor": "Cor",
            "tamanho": "Tamanho",
            "estoque": "Qtde",
            "preco": "Preço R$",
            "valor_total": "Valor Total R$",
        })[["Produto", "Cor", "Tamanho", "Qtde", "Preço R$", "Valor Total R$"]]

        st.markdown(
            f"<div style='font-size:13px;color:#6B7280;margin-bottom:8px'>"
            f"{len(_df_show)} variante(s) exibida(s)</div>",
            unsafe_allow_html=True
        )

        # Highlight de baixo estoque
        def _highlight_estoque(row):
            if row["Qtde"] == 0:
                return ["background:#FEF2F2"] * len(row)
            if row["Qtde"] <= 3:
                return ["background:#FFFBEB"] * len(row)
            return [""] * len(row)

        st.dataframe(
            _df_show.style.apply(_highlight_estoque, axis=1).format({
                "Preço R$":      "R${:.2f}",
                "Valor Total R$": "R${:.2f}",
            }),
            use_container_width=True,
            hide_index=True,
            height=min(50 + 35 * len(_df_show), 600),
        )
        st.caption("🔴 Sem estoque · 🟡 Estoque ≤ 3 · Verde = OK")

        # ── Resumo por produto ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Resumo por produto")
        _df_by_prod = (
            _df_inv[_df_inv["estoque"] > 0]
            .groupby("produto")
            .agg(total_pecas=("estoque", "sum"), valor_total=("valor_total", "sum"))
            .reset_index()
            .sort_values("total_pecas", ascending=False)
        )
        _df_by_prod.columns = ["Produto", "Total Peças", "Valor Total R$"]
        st.dataframe(
            _df_by_prod.style.format({"Valor Total R$": "R${:.2f}"}),
            use_container_width=True, hide_index=True,
            height=min(50 + 35 * len(_df_by_prod), 400)
        )

    # ── Em Produção ─────────────────────────────────────────────────────────
    if _ordens_abertas:
        st.markdown("---")
        st.markdown("#### Em produção (ordens abertas)")
        _STATUS_LABELS = {
            "modelagem": "Modelagem", "corte": "Corte",
            "costura": "Costura", "acabamento": "Acabamento",
        }
        for _op in _ordens_abertas:
            _op_st = _STATUS_LABELS.get(_op["status"], _op["status"])
            _op_custo = float(_op["custo_total"] or 0)
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:8px 14px;background:white;border-radius:8px;"
                f"margin-bottom:6px;border:1.5px solid #F0F0F0'>"
                f"<span style='font-weight:600;color:#1a2f4a'>{_op['produto']}</span>"
                f"<span style='color:#6B7280'>{_op['quantidade']} peças · {_op_st}</span>"
                f"<span style='font-weight:700;color:#b8860b'>R${_op_custo:.2f}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Mais acessados da semana ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Mais vendidos esta semana")
    try:
        _all_orders_est = fetch_all_orders()
        _7d_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        _recent_ord = [o for o in _all_orders_est if o["created_at"][:10] >= _7d_ago]
        if _recent_ord:
            _top_week, _ = compute_sales(_recent_ord)
            _top_week = [p for p in _top_week if p["units"] > 0][:10]
            if _top_week:
                for _i, _p in enumerate(_top_week, 1):
                    _medal = "🥇" if _i == 1 else ("🥈" if _i == 2 else ("🥉" if _i == 3 else f"{_i}."))
                    _rev = f"R${_p['revenue']:,.0f}"
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:12px;"
                        f"padding:8px 14px;background:white;border-radius:8px;"
                        f"margin-bottom:6px;border:1.5px solid #F0F0F0'>"
                        f"<span style='font-size:18px;min-width:28px'>{_medal}</span>"
                        f"<span style='font-weight:600;color:#1a2f4a;flex:1'>{_p['produto']}</span>"
                        f"<span style='color:#6B7280'>{_p['units']} unidades</span>"
                        f"<span style='font-weight:700;color:#c96ba0;min-width:70px;text-align:right'>{_rev}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("Nenhuma venda nos últimos 7 dias.")
        else:
            st.info("Nenhuma venda nos últimos 7 dias.")
    except Exception as _e_week:
        st.warning(f"Não foi possível carregar vendas da semana: {_e_week}")

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — PRODUTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "▦ Produtos":
    import io as _io
    import requests as _req
    import urllib3 as _u3
    _u3.disable_warnings()

    GS_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1oqzBlwEkLiy9P6DrWU4YC7jvJ4QecPzHgTS8hOP_tvw"
        "/gviz/tq?tqx=out:csv&sheet=lista%20de%20produtos"
    )

    st.title("🧶 Produtos Backbe")
    conn = get_conn()

    tab_lista, tab_import, tab_novo = st.tabs([
        "📋 Todos os Produtos", "📥 Importar Planilha", "➕ Novo Produto"
    ])

    with tab_lista:
        produtos = rows_to_list(conn.execute(
            "SELECT * FROM produtos_backbe WHERE ativo=1 ORDER BY colecao, nome"
        ).fetchall())

        if not produtos:
            st.info("Nenhum produto cadastrado. Use **📥 Importar Planilha** para importar da Google Sheets, ou **➕ Novo Produto** para adicionar manualmente.")
        else:
            colecoes = sorted(set(p["colecao"] for p in produtos if p["colecao"]))
            cf1, cf2 = st.columns(2)
            filtro_col = cf1.multiselect("Filtrar por coleção", colecoes)
            prods_show = [p for p in produtos if not filtro_col or p["colecao"] in filtro_col]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total de produtos", len(prods_show))
            avg_cmv = sum(float(p["custo_total"] or 0) for p in prods_show) / len(prods_show) if prods_show else 0
            prods_com_venda = [p for p in prods_show if p.get("preco_venda")]
            avg_venda = sum(float(p["preco_venda"] or 0) for p in prods_com_venda) / len(prods_com_venda) if prods_com_venda else 0
            markups = [float(p["preco_venda"]) / float(p["custo_total"]) for p in prods_com_venda if p.get("custo_total")]
            avg_mk = sum(markups) / len(markups) if markups else 0
            k2.metric("CMV médio", f"R${avg_cmv:.2f}")
            k3.metric("Preço médio de venda", f"R${avg_venda:.2f}")
            k4.metric("Markup médio", f"{avg_mk:.1f}x")

            st.caption("✏️ Edite os valores diretamente na tabela e clique em Salvar.")

            df_prod = pd.DataFrame([{
                "ID": p["id"],
                "Produto": p["nome"],
                "Coleção": p["colecao"] or "",
                "Tecido R$": float(p["custo_tecido"] or 0),
                "Corte R$": float(p["custo_corte"] or 0),
                "Costura R$": float(p["custo_costura"] or 0),
                "Etiquetas R$": float(p["custo_etiquetas"] or 0),
                "Embalagem R$": float(p["custo_embalagem"] or 0),
                "Modelagem/peça R$": float(p["custo_modelagem"] or 0),
                "Adicional R$": float(p["custo_adicional"] or 0),
                "CMV R$": float(p["custo_total"] or 0),
                "Preço Venda R$": float(p["preco_venda"] or 0),
                "Markup": f"{p['preco_venda']/p['custo_total']:.1f}x" if (p["custo_total"] and p["preco_venda"]) else "-",
                "Obs": p.get("observacoes") or "",
            } for p in prods_show])

            # ── Cores pastel por coleção ──────────────────────────────────
            _COLL_PALETTES = [
                "#FFF0F6", "#EFF6FF", "#FFFBEB", "#F5F3FF", "#ECFDF5",
                "#FFF7ED", "#F0F9FF", "#FDF4FF", "#F7FEE7", "#FEF2F2",
                "#F0FDFA", "#FFFDE7", "#EDE9FE", "#E0F2FE", "#FCE7F3",
            ]
            _coll_list = sorted(df_prod["Coleção"].unique().tolist())
            _coll_map = {c: _COLL_PALETTES[i % len(_COLL_PALETTES)]
                         for i, c in enumerate(_coll_list)}

            def _row_bg(row):
                bg = _coll_map.get(row["Coleção"], "#FFFFFF")
                return [f"background-color:{bg}" for _ in row]

            styled_prod = df_prod.style.apply(_row_bg, axis=1)

            edited_p = st.data_editor(
                styled_prod,
                use_container_width=True,
                hide_index=True,
                height=min(40 + 36 * len(df_prod), 5000),  # dinâmico — a página rola, não a tabela
                disabled=["ID", "CMV R$", "Markup"],
                column_config={
                    "Tecido R$":        st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Corte R$":         st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Costura R$":       st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Etiquetas R$":     st.column_config.NumberColumn(format="R$%.2f", step=0.1),
                    "Embalagem R$":     st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Modelagem/peça R$":st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Adicional R$":     st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "CMV R$":           st.column_config.NumberColumn(format="R$%.2f"),
                    "Preço Venda R$":   st.column_config.NumberColumn(format="R$%.2f", step=5.0),
                },
                key="edit_prods_main"
            )

            if st.button("💾 Salvar produtos", type="primary"):
                for _, row in edited_p.iterrows():
                    cmv = (float(row["Tecido R$"]) + float(row["Corte R$"]) +
                           float(row["Costura R$"]) + float(row["Etiquetas R$"]) +
                           float(row["Embalagem R$"]) + float(row["Modelagem/peça R$"]) +
                           float(row["Adicional R$"]))
                    conn.execute("""
                        UPDATE produtos_backbe SET
                            nome=?, colecao=?,
                            custo_tecido=?, custo_corte=?, custo_costura=?,
                            custo_etiquetas=?, custo_embalagem=?, custo_modelagem=?,
                            custo_adicional=?, custo_total=?, preco_venda=?,
                            observacoes=?, atualizado_em=datetime('now','localtime')
                        WHERE id=?
                    """, (
                        row["Produto"], row["Coleção"],
                        float(row["Tecido R$"]), float(row["Corte R$"]), float(row["Costura R$"]),
                        float(row["Etiquetas R$"]), float(row["Embalagem R$"]), float(row["Modelagem/peça R$"]),
                        float(row["Adicional R$"]), cmv, float(row["Preço Venda R$"]),
                        row["Obs"], int(row["ID"])
                    ))
                conn.commit()
                st.success(f"✅ {len(edited_p)} produtos salvos!")
                st.rerun()

    with tab_import:
        st.subheader("📥 Importar da Planilha Google Sheets")
        st.info(
            "Importa os produtos da aba **'lista de produtos'** da sua planilha. "
            "Produtos com o mesmo nome não são duplicados."
        )
        col_i1, col_i2 = st.columns(2)
        modelagem_total = col_i1.number_input(
            "Custo de modelagem padrão (R$)", min_value=0.0, value=0.0, step=50.0,
            help="Custo total de modelagem por produto, dividido pelo lote mínimo"
        )
        lote_imp = col_i2.number_input("Lote mínimo padrão (peças)", min_value=1, value=10, step=1)
        custo_mod_imp = round(modelagem_total / lote_imp, 2) if lote_imp else 0
        if modelagem_total > 0:
            st.caption(f"Modelagem por peça: R${custo_mod_imp:.2f}")

        if st.button("📥 Importar agora", type="primary"):
            try:
                with st.spinner("Buscando planilha..."):
                    r = _req.get(GS_URL, verify=False, timeout=30)
                    r.raise_for_status()
                    df_gs = pd.read_csv(_io.StringIO(r.text))

                existentes = {
                    p["nome"] for p in rows_to_list(
                        conn.execute("SELECT nome FROM produtos_backbe").fetchall()
                    )
                }

                importados = 0
                pulados = 0
                for _, row in df_gs.iterrows():
                    nome_p = str(row.iloc[0]).strip()
                    if not nome_p or nome_p.lower() in ["produto", "nan", ""]:
                        continue
                    if nome_p in existentes:
                        pulados += 1
                        continue
                    colecao_p = str(row.iloc[1]).strip() if len(row) > 1 else ""
                    if colecao_p.lower() == "nan":
                        colecao_p = ""
                    custo_tec  = _brl(row.iloc[4]) if len(row) > 4 else 0
                    custo_cor  = _brl(row.iloc[5]) if len(row) > 5 else 0
                    custo_cos  = _brl(row.iloc[6]) if len(row) > 6 else 0
                    custo_eti  = _brl(row.iloc[7]) if len(row) > 7 else 0
                    custo_adic = _brl(row.iloc[8]) if len(row) > 8 else 0
                    custo_emb  = _brl(row.iloc[9]) if len(row) > 9 else 0
                    preco_vnd  = _brl(row.iloc[13]) if len(row) > 13 else 0
                    cmv_p = custo_tec + custo_cor + custo_cos + custo_eti + custo_adic + custo_emb + custo_mod_imp
                    conn.execute("""
                        INSERT INTO produtos_backbe
                        (nome, colecao, custo_tecido, custo_corte, custo_costura,
                         custo_etiquetas, custo_adicional, custo_embalagem, custo_modelagem,
                         lote_minimo, custo_total, preco_venda)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (nome_p, colecao_p, custo_tec, custo_cor, custo_cos,
                          custo_eti, custo_adic, custo_emb, custo_mod_imp,
                          lote_imp, cmv_p, preco_vnd))
                    importados += 1
                conn.commit()
                msg = f"✅ **{importados} produtos importados**"
                if pulados:
                    msg += f" ({pulados} já existiam e foram pulados)"
                st.success(msg)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar: {e}")

    with tab_novo:
        st.subheader("➕ Novo Produto")

        # ── Nome e coleção ──────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        nome_np     = c1.text_input("Nome do produto*", key="np_nome")
        colecao_np  = c2.text_input("Coleção", key="np_colecao")

        # ── Tecido ─────────────────────────────────────────────────────────
        st.markdown("**🧵 Tecido**")
        tecidos_ativos_np = rows_to_list(conn.execute(
            "SELECT id, nome, unidade, preco_metro, preco_kg, peso_gsm, largura_m "
            "FROM tecidos WHERE ativo=1 ORDER BY nome"
        ).fetchall())

        MANUAL = "— Digitar custo manualmente —"
        opcoes_np = [MANUAL] + [t["nome"] for t in tecidos_ativos_np]

        ct1, ct2 = st.columns([3, 2])
        tec_np_nome = ct1.selectbox("Selecionar tecido", opcoes_np, key="np_tec_sel")

        custo_tec_np   = 0.0
        metragem_cm_np = 0

        if tec_np_nome == MANUAL:
            custo_tec_np = ct2.number_input(
                "Custo tecido R$/peça", min_value=0.0, step=0.5, key="np_custo_tec_manual"
            )
            if not tecidos_ativos_np:
                st.caption("ℹ️ Nenhum tecido cadastrado. Vá em **🧵 Tecidos** no menu lateral para adicionar.")
            else:
                st.caption("Tecido não listado? Vá em **🧵 Tecidos** no menu lateral para cadastrar.")
        else:
            tec_np = next(t for t in tecidos_ativos_np if t["nome"] == tec_np_nome)
            metragem_cm_np = ct2.number_input(
                "Metragem usada (cm)", min_value=0, step=5, value=100, key="np_metragem_cm"
            )
            # Calcula custo do tecido por peça
            unid = tec_np.get("unidade", "metro")
            preco_metro = float(tec_np.get("preco_metro") or 0)
            preco_kg    = float(tec_np.get("preco_kg") or 0)
            largura_m   = float(tec_np.get("largura_m") or 1.5)
            gsm         = float(tec_np.get("peso_gsm") or 200)
            metros_np   = metragem_cm_np / 100

            if unid == "metro" and preco_metro > 0:
                custo_tec_np = round(metros_np * preco_metro, 2)
                st.caption(
                    f"📐 {metragem_cm_np} cm × R${preco_metro:.2f}/m = **R${custo_tec_np:.2f}/peça**"
                )
            elif unid == "kg" and preco_kg > 0:
                peso_peca = metros_np * largura_m * gsm / 1000
                custo_tec_np = round(peso_peca * preco_kg, 2)
                st.caption(
                    f"📐 {metragem_cm_np} cm × {largura_m}m larg. × {gsm}gsm → "
                    f"{peso_peca:.3f} kg × R${preco_kg:.2f}/kg = **R${custo_tec_np:.2f}/peça**"
                )
            else:
                st.caption("⚠️ Tecido sem preço cadastrado. Vá em **🧵 Tecidos** para adicionar o preço.")

        # ── Outros custos ──────────────────────────────────────────────────
        c3, c4 = st.columns(2)
        custo_cor_np  = c3.number_input("Corte R$/peça",     min_value=0.0, step=0.5, value=8.0,  key="np_corte")
        custo_cos_np  = c4.number_input("Costura R$/peça",   min_value=0.0, step=0.5,              key="np_costura")

        c5, c6 = st.columns(2)
        custo_eti_np  = c5.number_input("Etiquetas R$/peça", min_value=0.0, step=0.1, value=0.2,  key="np_etiq")
        custo_emb_np  = c6.number_input("Embalagem R$/peça", min_value=0.0, step=0.5, value=10.0, key="np_emb")

        # ── Acabamentos / Aviamentos ────────────────────────────────────────
        st.markdown("**🔩 Aviamentos**")

        acabamentos_db_np = rows_to_list(conn.execute(
            "SELECT id, nome, preco, unidade, categoria FROM acabamentos WHERE ativo=1 ORDER BY categoria, nome"
        ).fetchall())

        if "np_aviamentos" not in st.session_state:
            st.session_state["np_aviamentos"] = []

        if acabamentos_db_np:
            av1, av2, av3 = st.columns([5, 2, 2])
            av_opcoes = [f"{a['nome']}  —  R${float(a['preco']):.2f}/{a['unidade']}" for a in acabamentos_db_np]
            av_sel_i  = av1.selectbox("Selecionar aviamento", range(len(av_opcoes)),
                                       format_func=lambda i: av_opcoes[i], key="np_av_sel",
                                       label_visibility="collapsed")
            av_qtde   = av2.number_input("Qtde", min_value=1, value=1, step=1, key="np_av_qtde",
                                          label_visibility="collapsed")
            if av3.button("➕ Adicionar", key="np_av_add"):
                av_obj = acabamentos_db_np[av_sel_i]
                existing = next((x for x in st.session_state["np_aviamentos"] if x["id"] == av_obj["id"]), None)
                if existing:
                    existing["qtde"] += av_qtde
                    existing["subtotal"] = round(existing["qtde"] * existing["preco"], 2)
                else:
                    st.session_state["np_aviamentos"].append({
                        "id":       av_obj["id"],
                        "nome":     av_obj["nome"],
                        "preco":    float(av_obj["preco"]),
                        "unidade":  av_obj["unidade"],
                        "qtde":     av_qtde,
                        "subtotal": round(av_qtde * float(av_obj["preco"]), 2),
                    })
                st.rerun()

            # Lista dos itens selecionados
            if st.session_state["np_aviamentos"]:
                for i, av in enumerate(list(st.session_state["np_aviamentos"])):
                    col_av, col_del = st.columns([10, 1])
                    col_av.markdown(
                        f"**{av['qtde']}×** {av['nome']} — "
                        f"R${av['preco']:.2f}/{av['unidade']} = **R${av['subtotal']:.2f}**"
                    )
                    if col_del.button("🗑️", key=f"np_av_del_{i}", help="Remover"):
                        st.session_state["np_aviamentos"].pop(i)
                        st.rerun()
                total_av = sum(av["subtotal"] for av in st.session_state["np_aviamentos"])
                st.caption(f"💰 Total aviamentos selecionados: **R${total_av:.2f}**")
            else:
                st.caption("Nenhum aviamento adicionado ainda.")
                total_av = 0.0
        else:
            st.caption("Nenhum aviamento cadastrado. Vá em **🔩 Aviamentos** no menu lateral para adicionar.")
            total_av = 0.0

        # Campo extra para custos adicionais não listados
        custo_adic_extra = st.number_input(
            "Custo extra não listado R$/peça", min_value=0.0, step=0.5, key="np_adic",
            help="Custos de acabamento que não estão no cadastro de aviamentos"
        )
        custo_adic_np = round(total_av + custo_adic_extra, 2)

        # ── Modelagem e lote ────────────────────────────────────────────────
        c8, c9 = st.columns(2)
        mod_total_np  = c8.number_input(
            "Modelagem total R$", min_value=0.0, step=50.0, key="np_mod",
            help="Valor total pago pela modelagem — será dividido pelo lote mínimo"
        )
        lote_np      = c9.number_input("Lote mínimo (peças)", min_value=1, value=10, step=1, key="np_lote")
        custo_mod_np = round(mod_total_np / lote_np, 2) if lote_np else 0

        # ── CMV preview ────────────────────────────────────────────────────
        cmv_np = (custo_tec_np + custo_cor_np + custo_cos_np + custo_eti_np +
                  custo_adic_np + custo_emb_np + custo_mod_np)
        st.info(
            f"CMV estimado: **R${cmv_np:.2f}** | "
            f"Mínimo (2x): R${cmv_np*2:.2f} | "
            f"Ideal (3,5x): R${cmv_np*3.5:.2f}"
        )

        preco_vnd_np = st.number_input("Preço de Venda R$", min_value=0.0, step=5.0, key="np_venda")
        obs_np       = st.text_area("Observações", key="np_obs")

        if st.button("✅ Cadastrar produto", type="primary", key="np_submit") and nome_np:
            conn.execute("""
                INSERT INTO produtos_backbe
                (nome, colecao, metragem_cm, custo_tecido, custo_corte, custo_costura,
                 custo_etiquetas, custo_adicional, custo_embalagem, custo_modelagem,
                 lote_minimo, custo_total, preco_venda, observacoes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (nome_np, colecao_np, metragem_cm_np,
                  custo_tec_np, custo_cor_np, custo_cos_np,
                  custo_eti_np, custo_adic_np, custo_emb_np, custo_mod_np,
                  lote_np, cmv_np, preco_vnd_np, obs_np))
            conn.commit()
            st.session_state["np_aviamentos"] = []  # limpa lista de aviamentos
            st.success(f"✅ Produto **{nome_np}** cadastrado! CMV: R${cmv_np:.2f}")
            st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — ACABAMENTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⊕ Aviamentos":
    st.title("🔩 Aviamentos")
    st.caption("Cadastre botões, zíperes, elásticos e outros aviamentos. Eles ficam salvos para usar na Calculadora CMV.")

    CATS_ACB = ["botão", "zíper", "elástico", "etiqueta", "forro", "ribana", "viés", "ilhós", "regulagem", "outro"]
    conn = get_conn()

    tab_cat, tab_novo_a = st.tabs(["📋 Catálogo", "➕ Novo Item"])

    with tab_cat:
        import base64 as _b64
        acabamentos = rows_to_list(conn.execute(
            "SELECT * FROM acabamentos ORDER BY categoria, nome"
        ).fetchall())

        if not acabamentos:
            st.info("Nenhum aviamento cadastrado ainda. Adicione na aba **➕ Novo Item**.")
        else:
            by_cat = {}
            for a in acabamentos:
                by_cat.setdefault(a["categoria"] or "outro", []).append(a)

            # CSS para os cards de aviamento
            st.markdown("""
            <style>
            .avia-card {
                background: white;
                border: 1.5px solid #F0F0F0;
                border-radius: 14px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,.06);
                transition: box-shadow .2s;
                height: 100%;
            }
            .avia-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.12); }
            .avia-img {
                width:100%; aspect-ratio:1/1; object-fit:cover;
                background:#F8F8F8; display:flex; align-items:center;
                justify-content:center;
            }
            .avia-body { padding: 10px 12px 12px 12px; }
            .avia-nome { font-size:13px; font-weight:700; color:#1a2f4a;
                         line-height:1.3; margin-bottom:3px; }
            .avia-un   { font-size:11px; color:#9CA3AF; margin-bottom:4px; }
            .avia-preco{ font-size:16px; font-weight:800; color:#c96ba0; }
            </style>""", unsafe_allow_html=True)

            for cat, items in sorted(by_cat.items()):
                # Cabeçalho de categoria
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;
                            margin:24px 0 12px 0;padding-bottom:8px;
                            border-bottom:2px solid #F0F4FF">
                  <span style="font-size:14px;font-weight:700;
                               color:#1a2f4a;text-transform:uppercase;
                               letter-spacing:.04em">{cat.title()}</span>
                  <span style="font-size:11px;background:#EFF6FF;color:#1D4ED8;
                               border-radius:20px;padding:1px 8px">
                    {len(items)} item(s)
                  </span>
                </div>""", unsafe_allow_html=True)

                # Grade: 3 colunas por linha
                COLS = 3
                rows_items = [items[i:i+COLS] for i in range(0, len(items), COLS)]
                for row_items in rows_items:
                    cols = st.columns(COLS, gap="medium")
                    for j, a in enumerate(row_items):
                        with cols[j]:
                            # — Card container
                            preco = float(a["preco"] or 0)
                            un    = a["unidade"] or "un"

                            # Imagem
                            if a.get("imagem_b64"):
                                try:
                                    img_bytes = _b64.b64decode(a["imagem_b64"])
                                    st.image(img_bytes, use_container_width=True,
                                             caption=None)
                                except Exception:
                                    st.markdown(
                                        "<div class='avia-img' style='height:120px;"
                                        "background:#F3F4F6;border-radius:10px;"
                                        "display:flex;align-items:center;"
                                        "justify-content:center;font-size:32px'>📦</div>",
                                        unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    "<div style='height:120px;background:#F8F9FA;"
                                    "border-radius:10px;display:flex;align-items:center;"
                                    "justify-content:center;font-size:36px;"
                                    "border:1.5px dashed #E5E7EB'>📦</div>",
                                    unsafe_allow_html=True)

                            # Info do produto
                            st.markdown(f"""
                            <div style="margin-top:8px">
                              <div style="font-size:13px;font-weight:700;
                                          color:#1a2f4a;line-height:1.3">
                                {a['nome']}
                              </div>
                              <div style="font-size:11px;color:#9CA3AF;margin:2px 0">
                                por {un}
                              </div>
                              <div style="font-size:17px;font-weight:800;color:#c96ba0">
                                R${preco:.2f}
                              </div>
                            </div>""", unsafe_allow_html=True)

                            # Upload de imagem (compacto)
                            up_img = st.file_uploader(
                                "Trocar foto", type=["jpg","jpeg","png","webp"],
                                key=f"img_up_{a['id']}", label_visibility="collapsed"
                            )
                            if up_img:
                                b64_str = _b64.b64encode(up_img.read()).decode()
                                conn.execute(
                                    "UPDATE acabamentos SET imagem_b64=? WHERE id=?",
                                    (b64_str, a["id"])
                                )
                                conn.commit()
                                st.rerun()

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                # ── Edição de preços (expander, sem bagunçar a grade) ──────
                with st.expander(f"Editar preços — {cat.title()}", expanded=False):
                    df_cat = pd.DataFrame([{
                        "ID": a["id"],
                        "Nome": a["nome"],
                        "Unidade": a["unidade"] or "unidade",
                        "Preço R$": float(a["preco"] or 0),
                        "Obs": a.get("observacoes") or "",
                        "Ativo": bool(a["ativo"]),
                    } for a in items])

                    edited_a = st.data_editor(
                        df_cat,
                        use_container_width=True,
                        hide_index=True,
                        height=min(40 + 36 * len(df_cat), 2000),
                        disabled=["ID"],
                        column_config={
                            "Preço R$": st.column_config.NumberColumn(
                                format="R$%.2f", step=0.1),
                            "Ativo": st.column_config.CheckboxColumn(),
                        },
                        key=f"edit_acab_{cat}"
                    )
                    if st.button(f"Salvar {cat}", key=f"sv_acab_{cat}", type="primary"):
                        for _, row in edited_a.iterrows():
                            conn.execute(
                                "UPDATE acabamentos SET nome=?, unidade=?, preco=?,"
                                "observacoes=?, ativo=? WHERE id=?",
                                (row["Nome"], row["Unidade"], float(row["Preço R$"]),
                                 row["Obs"], 1 if row["Ativo"] else 0, int(row["ID"]))
                            )
                        conn.commit()
                        st.success(f"✅ {cat.title()} salvo!")
                        st.rerun()

    with tab_novo_a:
        st.subheader("➕ Novo Acabamento")
        with st.form("form_novo_acabamento"):
            c1, c2 = st.columns(2)
            nome_a  = c1.text_input("Nome*", placeholder="Ex: Botão pérola 15mm")
            cat_a   = c2.selectbox("Categoria", CATS_ACB)
            c3, c4  = st.columns(2)
            un_a    = c3.selectbox("Unidade", ["unidade", "metro", "par", "kit", "pacote"])
            preco_a = c4.number_input("Preço R$*", min_value=0.0, step=0.1)
            obs_a   = st.text_area("Observações")
            if st.form_submit_button("✅ Cadastrar", type="primary"):
                if nome_a:
                    conn.execute(
                        "INSERT INTO acabamentos (nome, categoria, unidade, preco, observacoes) VALUES (?,?,?,?,?)",
                        (nome_a, cat_a, un_a, preco_a, obs_a)
                    )
                    conn.commit()
                    st.success(f"✅ **{nome_a}** cadastrado!")
                    st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — CORTE VÓ MARCIA
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "✂ Corte Vo Marcia":
    st.title("Corte — Vó Marcia")
    st.caption("Controle mensal dos cortes. Marque quais foram feitos pela Vó para calcular o pagamento.")

    conn = get_conn()

    # Garante que as tabelas existem (migração defensiva)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relatorio_corte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes INTEGER NOT NULL, ano INTEGER NOT NULL,
            cortadora TEXT DEFAULT 'Vo Marcia',
            total_pecas INTEGER DEFAULT 0,
            total_corte REAL DEFAULT 0,
            pago INTEGER DEFAULT 0, observacoes TEXT,
            UNIQUE(mes, ano)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relatorio_corte_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relatorio_id INTEGER NOT NULL REFERENCES relatorio_corte(id),
            produto TEXT NOT NULL,
            quantidade INTEGER DEFAULT 0,
            valor_corte_total REAL DEFAULT 0,
            valor_corte_unit REAL DEFAULT 0,
            feito_pela_vo INTEGER DEFAULT 1
        )""")
    conn.commit()

    MESES_C = ["Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

    col_mc, col_ac = st.columns(2)
    mes_c = col_mc.selectbox("Mês", range(1,13), index=datetime.now().month-1,
                              format_func=lambda x: MESES_C[x-1])
    ano_c = int(col_ac.number_input("Ano", min_value=2020, max_value=2030,
                                     value=datetime.now().year, step=1))

    conn.execute(
        "INSERT OR IGNORE INTO relatorio_corte (mes, ano) VALUES (?,?)",
        (mes_c, ano_c)
    )
    conn.commit()
    rel_c = row_to_dict(conn.execute(
        "SELECT * FROM relatorio_corte WHERE mes=? AND ano=?", (mes_c, ano_c)
    ).fetchone())
    rel_c_id = rel_c["id"]

    def _recalc_corte(conn, rid):
        rows = conn.execute(
            "SELECT quantidade, valor_corte_total, feito_pela_vo "
            "FROM relatorio_corte_itens WHERE relatorio_id=?", (rid,)
        ).fetchall()
        total_pecas = sum(r["quantidade"] for r in rows if r["feito_pela_vo"])
        total_corte = sum(r["valor_corte_total"] for r in rows if r["feito_pela_vo"])
        conn.execute(
            "UPDATE relatorio_corte SET total_pecas=?, total_corte=? WHERE id=?",
            (total_pecas, total_corte, rid)
        )

    tab_itens_c, tab_resumo_c, tab_hist_c = st.tabs([
        "Itens de Corte", "Resumo do Mês", "Histórico"
    ])

    with tab_itens_c:
        itens_c = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_corte_itens WHERE relatorio_id=? ORDER BY id",
            (rel_c_id,)
        ).fetchall())

        if itens_c:
            # Totalizadores
            _tot_pecas_c = sum(i["quantidade"] for i in itens_c if i["feito_pela_vo"])
            _tot_val_c   = sum(i["valor_corte_total"] for i in itens_c if i["feito_pela_vo"])
            _tot_todos    = sum(i["valor_corte_total"] for i in itens_c)

            kc1, kc2, kc3 = st.columns(3)
            _kcs = "background:white;border-radius:12px;padding:12px 16px;border:1.5px solid #F0F0F0"
            kc1.markdown(f"<div style='{_kcs}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>Peças (Vó)</div><div style='font-size:22px;font-weight:800;color:#1a2f4a;white-space:nowrap'>{_tot_pecas_c}</div></div>", unsafe_allow_html=True)
            kc2.markdown(f"<div style='{_kcs}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>A pagar Vó</div><div style='font-size:22px;font-weight:800;color:#c96ba0;white-space:nowrap'>R${_tot_val_c:.2f}</div></div>", unsafe_allow_html=True)
            kc3.markdown(f"<div style='{_kcs}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>Corte total mês</div><div style='font-size:22px;font-weight:800;color:#6B7280;white-space:nowrap'>R${_tot_todos:.2f}</div></div>", unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            # Cabeçalho da tabela
            _hc0, _hc1, _hc2, _hc3, _hc4, _hc5, _hc6 = st.columns([3, 0.8, 1.2, 1.2, 1, 0.7, 0.7])
            for _col, _lbl in [(_hc0,"Produto"),(_hc1,"Qtde"),(_hc2,"Total corte"),
                                (_hc3,"R$/peça"),(_hc4,"Vó fez?"),(_hc5,""),(_hc6,"")]:
                _col.markdown(
                    f"<div style='font-size:10px;font-weight:700;color:#9CA3AF;"
                    f"text-transform:uppercase;padding:3px 0'>{_lbl}</div>",
                    unsafe_allow_html=True)

            for _ic in itens_c:
                _icid = _ic["id"]
                _edit_key_c = f"edit_corte_{_icid}"

                if st.session_state.get(_edit_key_c):
                    _ec0,_ec1,_ec2,_ec3,_ec4,_ec5,_ec6 = st.columns([3,0.8,1.2,1.2,1,0.7,0.7])
                    _nn = _ec0.text_input("", value=_ic["produto"],  key=f"cn_{_icid}", label_visibility="collapsed")
                    _nq = _ec1.number_input("", value=int(_ic["quantidade"]), min_value=1, step=1, key=f"cq_{_icid}", label_visibility="collapsed")
                    _nt = _ec2.number_input("", value=float(_ic["valor_corte_total"]), min_value=0.0, step=0.5, key=f"ct_{_icid}", label_visibility="collapsed")
                    _ec3.markdown(f"<div style='padding:6px 0;font-size:13px;color:#6B7280'>R${(_nt/_nq):.2f}</div>", unsafe_allow_html=True)
                    _nv = _ec4.checkbox("Vó", value=bool(_ic["feito_pela_vo"]), key=f"cv_{_icid}")
                    if _ec5.button("Salvar", key=f"csv_{_icid}", type="primary", use_container_width=True):
                        conn.execute(
                            "UPDATE relatorio_corte_itens SET produto=?, quantidade=?, "
                            "valor_corte_total=?, valor_corte_unit=?, feito_pela_vo=? WHERE id=?",
                            (_nn, _nq, _nt, round(_nt/_nq,2), 1 if _nv else 0, _icid)
                        )
                        _recalc_corte(conn, rel_c_id)
                        conn.commit()
                        del st.session_state[_edit_key_c]
                        st.rerun()
                    if _ec6.button("✕", key=f"ccan_{_icid}", use_container_width=True):
                        del st.session_state[_edit_key_c]
                        st.rerun()
                else:
                    _rc0,_rc1,_rc2,_rc3,_rc4,_rc5,_rc6 = st.columns([3,0.8,1.2,1.2,1,0.7,0.7])
                    _vo_badge = (
                        "<span style='background:#EFF6FF;color:#1D4ED8;border-radius:6px;"
                        "padding:2px 7px;font-size:11px;font-weight:700'>Vó</span>"
                        if _ic["feito_pela_vo"] else
                        "<span style='background:#F3F4F6;color:#9CA3AF;border-radius:6px;"
                        "padding:2px 7px;font-size:11px'>Outro</span>"
                    )
                    _rc0.markdown(f"<div style='padding:5px 0;font-weight:600;color:#1a2f4a;font-size:13px'>{_ic['produto']}</div>", unsafe_allow_html=True)
                    _rc1.markdown(f"<div style='padding:5px 0;color:#374151;font-size:13px'>{_ic['quantidade']}</div>", unsafe_allow_html=True)
                    _rc2.markdown(f"<div style='padding:5px 0;font-weight:700;color:#059669;font-size:13px'>R${float(_ic['valor_corte_total']):.2f}</div>", unsafe_allow_html=True)
                    _rc3.markdown(f"<div style='padding:5px 0;color:#6B7280;font-size:12px'>R${float(_ic['valor_corte_unit']):.2f}</div>", unsafe_allow_html=True)
                    _rc4.markdown(f"<div style='padding:5px 0'>{_vo_badge}</div>", unsafe_allow_html=True)
                    if _rc5.button("Editar", key=f"cedt_{_icid}", use_container_width=True):
                        st.session_state[_edit_key_c] = True
                        st.rerun()
                    if _rc6.button("Excluir", key=f"cdel_{_icid}", use_container_width=True):
                        conn.execute("DELETE FROM relatorio_corte_itens WHERE id=?", (_icid,))
                        _recalc_corte(conn, rel_c_id)
                        conn.commit()
                        st.rerun()

                st.markdown("<div style='height:1px;background:#F3F4F6;margin:1px 0'></div>", unsafe_allow_html=True)

            # Total
            st.markdown(
                f"<div style='text-align:right;font-weight:800;font-size:15px;"
                f"color:#c96ba0;padding:8px 0'>Total Vó: R${_tot_val_c:.2f}</div>",
                unsafe_allow_html=True)

        else:
            st.info("Nenhum item de corte cadastrado para este mês.")

        st.divider()
        st.subheader("Adicionar corte")

        # Catálogo para autocomplete
        _cat_corte = rows_to_list(conn.execute(
            "SELECT nome FROM produtos_backbe WHERE ativo=1 ORDER BY nome"
        ).fetchall())
        _cat_corte_opts = ["(digitar nome)"] + [p["nome"] for p in _cat_corte]

        _prod_sel_c = st.selectbox("Produto", _cat_corte_opts, key="corte_prod_sel")
        _prod_nome_c = (_prod_sel_c if _prod_sel_c != "(digitar nome)"
                        else st.text_input("Nome do produto*", key="corte_prod_custom"))

        _cc1, _cc2, _cc3 = st.columns([1, 1.5, 1])
        _qtde_c   = _cc1.number_input("Quantidade", min_value=1, value=1, step=1, key="corte_qtde")
        _total_c  = _cc2.number_input("Valor total do corte R$", min_value=0.0, step=0.5, key="corte_total")
        _pela_vo_c = _cc3.checkbox("Feito pela Vó Marcia", value=True, key="corte_pela_vo")

        if st.button("Adicionar", type="primary", key="corte_add_btn"):
            if _prod_nome_c and _prod_nome_c != "(digitar nome)":
                _unit_c = round(_total_c / _qtde_c, 2) if _qtde_c else 0
                conn.execute(
                    "INSERT INTO relatorio_corte_itens "
                    "(relatorio_id, produto, quantidade, valor_corte_total, valor_corte_unit, feito_pela_vo) "
                    "VALUES (?,?,?,?,?,?)",
                    (rel_c_id, _prod_nome_c, _qtde_c, _total_c, _unit_c, 1 if _pela_vo_c else 0)
                )
                _recalc_corte(conn, rel_c_id)
                conn.commit()
                st.success(f"Adicionado: {_qtde_c}× {_prod_nome_c} — R${_total_c:.2f}")
                st.rerun()

    with tab_resumo_c:
        rel_c2 = row_to_dict(conn.execute(
            "SELECT * FROM relatorio_corte WHERE id=?", (rel_c_id,)
        ).fetchone())
        itens_c2 = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_corte_itens WHERE relatorio_id=? ORDER BY id", (rel_c_id,)
        ).fetchall())

        st.subheader(f"{MESES_C[mes_c-1]}/{ano_c} — Vó Marcia")

        if itens_c2:
            _vo_items  = [i for i in itens_c2 if i["feito_pela_vo"]]
            _out_items = [i for i in itens_c2 if not i["feito_pela_vo"]]
            _total_vo  = sum(i["valor_corte_total"] for i in _vo_items)
            _total_out = sum(i["valor_corte_total"] for i in _out_items)

            r1, r2, r3 = st.columns(3)
            _kcs2 = "background:white;border-radius:12px;padding:14px 16px;border:1.5px solid #F0F0F0"
            r1.markdown(f"<div style='{_kcs2}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>Peças cortadas (Vó)</div><div style='font-size:24px;font-weight:800;color:#1a2f4a;white-space:nowrap'>{sum(i['quantidade'] for i in _vo_items)}</div></div>", unsafe_allow_html=True)
            r2.markdown(f"<div style='{_kcs2}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>A pagar</div><div style='font-size:24px;font-weight:800;color:#c96ba0;white-space:nowrap'>R${_total_vo:.2f}</div></div>", unsafe_allow_html=True)
            r3.markdown(f"<div style='{_kcs2}'><div style='font-size:10px;color:#9CA3AF;text-transform:uppercase;font-weight:700'>Corte externo</div><div style='font-size:24px;font-weight:800;color:#6B7280;white-space:nowrap'>R${_total_out:.2f}</div></div>", unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if _vo_items:
                st.markdown("**Itens cortados pela Vó**")
                _df_vo = pd.DataFrame([{
                    "Produto": i["produto"],
                    "Qtde": i["quantidade"],
                    "Total R$": float(i["valor_corte_total"]),
                    "R$/peça": float(i["valor_corte_unit"]),
                } for i in _vo_items])
                st.dataframe(
                    _df_vo.style.format({"Total R$": "R${:.2f}", "R$/peça": "R${:.2f}"}),
                    use_container_width=True, hide_index=True,
                    height=min(40 + 35*len(_df_vo), 400)
                )

            if _out_items:
                with st.expander(f"Cortes externos ({len(_out_items)} itens — R${_total_out:.2f})", expanded=False):
                    for i in _out_items:
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"padding:6px 10px;background:#F9FAFB;border-radius:6px;margin-bottom:4px'>"
                            f"<span style='color:#6B7280'>{i['produto']}</span>"
                            f"<span style='color:#9CA3AF'>{i['quantidade']} peças · R${float(i['valor_corte_total']):.2f}</span>"
                            f"</div>",
                            unsafe_allow_html=True)

            # Botão pago / pendente
            st.divider()
            c_pago1, c_pago2 = st.columns([2,1])
            _pago_c = c_pago1.checkbox("Marcar como pago", value=bool(rel_c2["pago"]), key="corte_pago_chk")
            if _pago_c != bool(rel_c2["pago"]):
                conn.execute("UPDATE relatorio_corte SET pago=? WHERE id=?",
                             (1 if _pago_c else 0, rel_c_id))
                conn.commit()
                st.rerun()
            if _pago_c:
                c_pago2.success("PAGO")
            else:
                c_pago2.warning("PENDENTE")

            _obs_c = st.text_area("Observações", value=rel_c2.get("observacoes") or "", key="corte_obs")
            if st.button("Salvar obs", key="sv_corte_obs"):
                conn.execute("UPDATE relatorio_corte SET observacoes=? WHERE id=?",
                             (_obs_c, rel_c_id))
                conn.commit()
                st.success("Salvo!")
        else:
            st.info("Nenhum item cadastrado para este mês.")

    with tab_hist_c:
        _hist_c = rows_to_list(conn.execute(
            "SELECT mes, ano, total_pecas, total_corte, pago "
            "FROM relatorio_corte ORDER BY ano DESC, mes DESC"
        ).fetchall())
        if _hist_c:
            _df_hc = pd.DataFrame([{
                "Mês": MESES_C[r["mes"]-1],
                "Ano": r["ano"],
                "Peças (Vó)": r["total_pecas"],
                "Total R$": float(r["total_corte"]),
                "Status": "PAGO" if r["pago"] else "Pendente",
            } for r in _hist_c])
            st.dataframe(
                _df_hc.style.format({"Total R$": "R${:.2f}"}),
                use_container_width=True, hide_index=True
            )
            st.metric("Total acumulado",
                      f"R${sum(r['total_corte'] for r in _hist_c):.2f}")
        else:
            st.info("Nenhum histórico ainda.")

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — RELATÓRIO MÃE
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "◉ Relatorio Mae":
    st.title("👩 Relatório Mensal — Mãe Costureira")

    conn = get_conn()
    mae = row_to_dict(conn.execute("SELECT * FROM costureiras WHERE tipo='mae' LIMIT 1").fetchone())

    if not mae:
        st.error("Nenhuma costureira do tipo 'mãe' cadastrada. Cadastre em **🏭 Ordens de Produção → Gerenciar Costureiras**.")
        conn.close()
        st.stop()

    st.caption(f"Costureira: **{mae['nome']}** — pagamento por peça + 3% de comissão sobre o lucro mensal")

    MESES_R = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    col_m, col_a = st.columns(2)
    mes_r = col_m.selectbox("Mês", range(1, 13), index=datetime.now().month - 1,
                             format_func=lambda x: MESES_R[x - 1])
    ano_r = int(col_a.number_input("Ano", min_value=2020, max_value=2030,
                                   value=datetime.now().year, step=1))

    conn.execute(
        "INSERT OR IGNORE INTO relatorio_mae (mes, ano, costureira_id, comissao_pct) VALUES (?,?,?,3.0)",
        (mes_r, ano_r, mae["id"])
    )
    conn.commit()

    rel = row_to_dict(conn.execute(
        "SELECT * FROM relatorio_mae WHERE mes=? AND ano=? AND costureira_id=?",
        (mes_r, ano_r, mae["id"])
    ).fetchone())
    rel_id = rel["id"]

    tab_pecas_r, tab_corte_r, tab_resumo_r, tab_hist_r = st.tabs([
        "🧵 Peças Costuradas", "✂ Corte (Vó Marcia)", "📊 Resumo do Mês", "📅 Histórico"
    ])

    with tab_pecas_r:
        st.subheader(f"Peças costuradas — {MESES_R[mes_r-1]}/{ano_r}")
        costura_precos_r = rows_to_list(conn.execute("SELECT * FROM costura_precos ORDER BY categoria").fetchall())
        cat_opts_r = {cp["categoria"]: cp for cp in costura_precos_r}

        itens_r = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_mae_itens WHERE relatorio_id=? ORDER BY id",
            (rel_id,)
        ).fetchall())

        if itens_r:
            # Cabeçalho da tabela
            _h0, _h1, _h2, _h3, _h4, _h5 = st.columns([3, 1, 1.4, 1.4, 0.8, 0.8])
            for _col, _lbl in [
                (_h0, "Produto"), (_h1, "Qtde"), (_h2, "R$/peça"),
                (_h3, "Subtotal"), (_h4, ""), (_h5, ""),
            ]:
                _col.markdown(
                    f"<div style='font-size:11px;font-weight:700;color:#6B7280;"
                    f"text-transform:uppercase;padding:4px 0'>{_lbl}</div>",
                    unsafe_allow_html=True,
                )

            for _it in itens_r:
                _iid = _it["id"]
                _edit_key = f"edit_row_{_iid}"

                # Linha normal ou em modo edição
                if st.session_state.get(_edit_key):
                    # ── Modo edição ───────────────────────────────────────
                    _e0, _e1, _e2, _e3, _e4, _e5 = st.columns([3, 1, 1.4, 1.4, 0.8, 0.8])
                    _new_nome  = _e0.text_input("", value=_it["produto"], key=f"en_{_iid}", label_visibility="collapsed")
                    _new_qtde  = _e1.number_input("", value=int(_it["quantidade"]), min_value=1, step=1, key=f"eq_{_iid}", label_visibility="collapsed")
                    _new_preco = _e2.number_input("", value=float(_it["preco_unitario"]), min_value=0.0, step=0.5, key=f"ep_{_iid}", label_visibility="collapsed")
                    _e3.markdown(
                        f"<div style='padding:6px 0;font-size:13px;color:#6B7280'>"
                        f"R${_new_qtde * _new_preco:.2f}</div>",
                        unsafe_allow_html=True,
                    )
                    if _e4.button("Salvar", key=f"esv_{_iid}", type="primary", use_container_width=True):
                        _new_sub = _new_qtde * _new_preco
                        conn.execute(
                            "UPDATE relatorio_mae_itens "
                            "SET produto=?, quantidade=?, preco_unitario=?, subtotal=? WHERE id=?",
                            (_new_nome, _new_qtde, _new_preco, _new_sub, _iid),
                        )
                        _recalc_relatorio(conn, rel_id)
                        conn.commit()
                        del st.session_state[_edit_key]
                        st.rerun()
                    if _e5.button("✕", key=f"ecan_{_iid}", use_container_width=True):
                        del st.session_state[_edit_key]
                        st.rerun()
                else:
                    # ── Linha de visualização ─────────────────────────────
                    _r0, _r1, _r2, _r3, _r4, _r5 = st.columns([3, 1, 1.4, 1.4, 0.8, 0.8])
                    _r0.markdown(
                        f"<div style='padding:6px 0;font-weight:600;color:#1a2f4a'>{_it['produto']}</div>",
                        unsafe_allow_html=True,
                    )
                    _r1.markdown(
                        f"<div style='padding:6px 0;color:#374151'>{_it['quantidade']}</div>",
                        unsafe_allow_html=True,
                    )
                    _r2.markdown(
                        f"<div style='padding:6px 0;color:#374151'>R${float(_it['preco_unitario']):.2f}</div>",
                        unsafe_allow_html=True,
                    )
                    _r3.markdown(
                        f"<div style='padding:6px 0;font-weight:700;color:#059669'>R${float(_it['subtotal']):.2f}</div>",
                        unsafe_allow_html=True,
                    )
                    if _r4.button("Editar", key=f"edt_{_iid}", use_container_width=True):
                        st.session_state[_edit_key] = True
                        st.rerun()
                    if _r5.button("Excluir", key=f"del_{_iid}", use_container_width=True):
                        conn.execute("DELETE FROM relatorio_mae_itens WHERE id=?", (_iid,))
                        _recalc_relatorio(conn, rel_id)
                        conn.commit()
                        st.rerun()

                st.markdown(
                    "<div style='height:1px;background:#F3F4F6;margin:2px 0'></div>",
                    unsafe_allow_html=True,
                )

            # Total
            _total_it = sum(float(i["subtotal"]) for i in itens_r)
            st.markdown(
                f"<div style='text-align:right;font-weight:800;font-size:15px;"
                f"color:#1a2f4a;padding:8px 0'>Total: R${_total_it:.2f}</div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.subheader("➕ Adicionar peças")

        # ── Catálogo de produtos para autocomplete ─────────────────────────
        _catalogo_mae = rows_to_list(conn.execute(
            "SELECT nome, custo_costura FROM produtos_backbe WHERE ativo=1 ORDER BY nome"
        ).fetchall())
        _cat_mae_map = {p["nome"]: float(p["custo_costura"] or 0) for p in _catalogo_mae}
        _cat_mae_opts = ["(digitar nome)"] + list(_cat_mae_map.keys())

        # Selectbox com busca (Streamlit filtra ao digitar)
        _prod_sel_mae = st.selectbox(
            "Produto",
            _cat_mae_opts,
            key="mae_prod_sel",
            help="Digite para filtrar produtos do catálogo"
        )

        _prod_nome_mae = ""
        _preco_def_mae = 0.0

        if _prod_sel_mae == "(digitar nome)":
            _prod_nome_mae = st.text_input(
                "Nome do produto*", placeholder="Ex: Calça Itália",
                key="mae_prod_custom"
            )
            # Se digitou, tenta achar no catálogo para pré-preencher preço
            if _prod_nome_mae and _prod_nome_mae in _cat_mae_map:
                _preco_def_mae = _cat_mae_map[_prod_nome_mae]
        else:
            _prod_nome_mae = _prod_sel_mae
            _preco_def_mae = _cat_mae_map.get(_prod_sel_mae, 0.0)

        f3, f4 = st.columns(2)
        _qtde_mae = f3.number_input(
            "Quantidade de peças", min_value=1, value=10, step=1, key="mae_qtde_r"
        )
        # Chave muda com o produto para forçar reset do valor ao trocar produto
        _preco_mae = f4.number_input(
            "Preço/peça R$ (mãe)",
            min_value=0.0,
            value=_preco_def_mae,
            step=0.5,
            key=f"mae_preco_{_prod_sel_mae}",
        )

        if _preco_def_mae > 0:
            f4.caption(f"Auto-preenchido do catálogo")

        if st.button("➕ Adicionar", type="primary", key="mae_add_btn"):
            if _prod_nome_mae:
                _sub_mae = int(_qtde_mae) * float(_preco_mae)
                conn.execute("""
                    INSERT INTO relatorio_mae_itens
                    (relatorio_id, produto, categoria, quantidade, preco_unitario, subtotal)
                    VALUES (?,?,?,?,?,?)
                """, (rel_id, _prod_nome_mae, "", int(_qtde_mae), float(_preco_mae), _sub_mae))
                _recalc_relatorio(conn, rel_id)
                conn.commit()
                st.success(f"✅ {int(_qtde_mae)}× {_prod_nome_mae} — R${_sub_mae:.2f}")
                st.rerun()
            else:
                st.warning("Informe o nome do produto.")

    with tab_corte_r:
        st.subheader(f"✂ Corte — {MESES_R[mes_r-1]}/{ano_r}")

        # Garante que o relatório de corte existe para este mês
        conn.execute(
            "INSERT OR IGNORE INTO relatorio_corte (mes, ano) VALUES (?,?)",
            (mes_r, ano_r)
        )
        conn.commit()
        rel_c = row_to_dict(conn.execute(
            "SELECT * FROM relatorio_corte WHERE mes=? AND ano=?", (mes_r, ano_r)
        ).fetchone())
        rel_c_id = rel_c["id"]

        itens_c = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_corte_itens WHERE relatorio_id=? ORDER BY id",
            (rel_c_id,)
        ).fetchall())

        if not itens_c:
            st.info("Nenhum item de corte neste mês. Adicione abaixo.")
        else:
            for ic in itens_c:
                _ck = f"edit_corte_{ic['id']}"
                cols_c = st.columns([3, 1, 1, 1, 1, 1])
                if st.session_state.get(_ck):
                    new_prod_c  = cols_c[0].text_input("Produto",   value=ic["produto"],              key=f"cp_{ic['id']}")
                    new_qtd_c   = cols_c[1].number_input("Qtd",     value=int(ic["quantidade"]),      min_value=1, key=f"cq_{ic['id']}")
                    new_val_c   = cols_c[2].number_input("Total R$", value=float(ic["valor_corte_total"]), min_value=0.0, step=0.5, key=f"cv_{ic['id']}")
                    pela_vo_c   = cols_c[3].checkbox("Vó", value=bool(ic["feito_pela_vo"]),            key=f"cvo_{ic['id']}")
                    if cols_c[4].button("💾", key=f"csave_{ic['id']}"):
                        unit_c = round(new_val_c / new_qtd_c, 2) if new_qtd_c else 0
                        conn.execute(
                            "UPDATE relatorio_corte_itens SET produto=?, quantidade=?, "
                            "valor_corte_total=?, valor_corte_unit=?, feito_pela_vo=? WHERE id=?",
                            (new_prod_c, new_qtd_c, new_val_c, unit_c, 1 if pela_vo_c else 0, ic["id"])
                        )
                        # recalcula totais
                        rows_c = conn.execute(
                            "SELECT quantidade, valor_corte_total, feito_pela_vo "
                            "FROM relatorio_corte_itens WHERE relatorio_id=?", (rel_c_id,)
                        ).fetchall()
                        conn.execute(
                            "UPDATE relatorio_corte SET total_pecas=?, total_corte=? WHERE id=?",
                            (sum(r[0] for r in rows_c if r[2]), sum(r[1] for r in rows_c if r[2]), rel_c_id)
                        )
                        conn.commit()
                        st.session_state[_ck] = False
                        st.rerun()
                    if cols_c[5].button("✕", key=f"ccanc_{ic['id']}"):
                        st.session_state[_ck] = False
                        st.rerun()
                else:
                    vo_badge = "🟣 Vó" if ic["feito_pela_vo"] else "⚪ Outro"
                    cols_c[0].markdown(f"**{ic['produto']}**")
                    cols_c[1].markdown(f"{ic['quantidade']} pç")
                    cols_c[2].markdown(f"R${ic['valor_corte_total']:.2f}")
                    cols_c[3].markdown(vo_badge)
                    if cols_c[4].button("✏️", key=f"cedit_{ic['id']}"):
                        st.session_state[_ck] = True
                        st.rerun()
                    if cols_c[5].button("🗑️", key=f"cdel_{ic['id']}"):
                        conn.execute("DELETE FROM relatorio_corte_itens WHERE id=?", (ic["id"],))
                        rows_c = conn.execute(
                            "SELECT quantidade, valor_corte_total, feito_pela_vo "
                            "FROM relatorio_corte_itens WHERE relatorio_id=?", (rel_c_id,)
                        ).fetchall()
                        conn.execute(
                            "UPDATE relatorio_corte SET total_pecas=?, total_corte=? WHERE id=?",
                            (sum(r[0] for r in rows_c if r[2]), sum(r[1] for r in rows_c if r[2]), rel_c_id)
                        )
                        conn.commit()
                        st.rerun()

        # Totais
        rel_c_up = row_to_dict(conn.execute(
            "SELECT * FROM relatorio_corte WHERE id=?", (rel_c_id,)
        ).fetchone())
        st.divider()
        ct1, ct2 = st.columns(2)
        ct1.metric("Total peças cortadas (Vó)", rel_c_up["total_pecas"])
        ct2.metric("Total corte R$", f"R${rel_c_up['total_corte']:.2f}")

        # ── Adicionar item de corte ─────────────────────────────────────
        with st.expander("➕ Adicionar item de corte"):
            # autocomplete com nomes do catálogo de costura
            _cat_names_c = [cp["categoria"] for cp in rows_to_list(
                conn.execute("SELECT categoria FROM costura_precos ORDER BY categoria").fetchall()
            )]
            _prod_c = st.selectbox("Produto", ["(digitar nome)"] + _cat_names_c, key="c_prod_sel")
            _nome_c = st.text_input("Nome do produto", value="" if _prod_c == "(digitar nome)" else _prod_c, key=f"c_nome_{_prod_c}")
            _qtd_c  = st.number_input("Quantidade", min_value=1, value=1, key="c_qtd")
            _val_c  = st.number_input("Valor total de corte (R$)", min_value=0.0, step=0.5, key="c_val")
            _vo_c   = st.checkbox("Feito pela Vó Marcia", value=True, key="c_vo")
            if st.button("Adicionar corte", key="c_add_btn"):
                if _nome_c.strip():
                    _unit_c = round(_val_c / _qtd_c, 2) if _qtd_c else 0
                    conn.execute(
                        "INSERT INTO relatorio_corte_itens "
                        "(relatorio_id, produto, quantidade, valor_corte_total, valor_corte_unit, feito_pela_vo) "
                        "VALUES (?,?,?,?,?,?)",
                        (rel_c_id, _nome_c.strip(), _qtd_c, _val_c, _unit_c, 1 if _vo_c else 0)
                    )
                    rows_c2 = conn.execute(
                        "SELECT quantidade, valor_corte_total, feito_pela_vo "
                        "FROM relatorio_corte_itens WHERE relatorio_id=?", (rel_c_id,)
                    ).fetchall()
                    conn.execute(
                        "UPDATE relatorio_corte SET total_pecas=?, total_corte=? WHERE id=?",
                        (sum(r[0] for r in rows_c2 if r[2]), sum(r[1] for r in rows_c2 if r[2]), rel_c_id)
                    )
                    conn.commit()
                    st.success("Adicionado!")
                    st.rerun()
                else:
                    st.warning("Informe o nome do produto.")

    with tab_resumo_r:
        rel = row_to_dict(conn.execute(
            "SELECT * FROM relatorio_mae WHERE id=?", (rel_id,)
        ).fetchone())
        itens_r2 = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_mae_itens WHERE relatorio_id=? ORDER BY id", (rel_id,)
        ).fetchall())

        st.subheader(f"📊 {MESES_R[mes_r-1]}/{ano_r} — {mae['nome']}")

        k1, k2, k3 = st.columns(3)
        k1.metric("Total de peças", rel["total_pecas"])
        k2.metric("Costura total", f"R${rel['total_costura']:.2f}")
        k3.metric("Total a pagar", f"R${rel['total_pagar']:.2f}",
                  delta="✅ PAGO" if rel["pago"] else "⏳ Pendente")

        # ── Corte Vó Marcia do mesmo mês ──────────────────────────────────────
        _corte_result = conn.execute(
            "SELECT * FROM relatorio_corte WHERE mes=? AND ano=?", (mes_r, ano_r)
        ).fetchone()
        _corte_row = dict(_corte_result) if _corte_result else {}
        _total_corte_m = float(_corte_row.get("total_corte") or 0)
        _pecas_corte_m = int(_corte_row.get("total_pecas") or 0)
        if _total_corte_m > 0:
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("✂ Peças cortadas", _pecas_corte_m)
            kc2.metric("✂ Corte (Vó Marcia)", f"R${_total_corte_m:.2f}")
            kc3.metric("Costura + Corte", f"R${float(rel['total_costura']) + _total_corte_m:.2f}")

        st.divider()
        col_res1, col_res2 = st.columns([2, 1])
        with col_res1:
            st.markdown("**Receita do mês para calcular comissão**")
            receita_m = st.number_input(
                "Receita total Backbe no mês (R$)",
                min_value=0.0, step=100.0, value=float(rel["receita_mes"]),
                help="Veja no Dashboard — faturamento mensal"
            )
            lucro_est   = max(0, receita_m * 0.35)  # estimativa: 35% de margem líquida
            comissao_v  = round(lucro_est * float(rel["comissao_pct"]) / 100, 2)
            total_final = round(float(rel["total_costura"]) + comissao_v, 2)

            if receita_m > 0:
                st.markdown(f"""
| Item | Valor |
|---|---|
| Costura (peças) | **R${rel['total_costura']:.2f}** |
| Receita do mês | R${receita_m:,.2f} |
| Lucro estimado (35%) | R${lucro_est:,.2f} |
| Comissão {rel['comissao_pct']:.0f}% | **R${comissao_v:.2f}** |
| **TOTAL A PAGAR** | **R${total_final:.2f}** |
""")

            if st.button("💾 Salvar receita e comissão"):
                conn.execute("""
                    UPDATE relatorio_mae
                    SET receita_mes=?, comissao_valor=?, total_pagar=?
                    WHERE id=?
                """, (receita_m, comissao_v, total_final, rel_id))
                conn.commit()
                st.success("Salvo!")
                st.rerun()

        with col_res2:
            pago_r = st.checkbox("Marcado como pago", value=bool(rel["pago"]))
            if pago_r != bool(rel["pago"]):
                conn.execute("UPDATE relatorio_mae SET pago=? WHERE id=?", (1 if pago_r else 0, rel_id))
                conn.commit()
                st.rerun()
            if pago_r:
                st.success("✅ PAGO")
            else:
                st.warning("⏳ PENDENTE")

            obs_r2 = st.text_area("Observações", value=rel.get("observacoes") or "", key="obs_rel_r")
            if st.button("Salvar obs", key="sv_obs_rel"):
                conn.execute("UPDATE relatorio_mae SET observacoes=? WHERE id=?", (obs_r2, rel_id))
                conn.commit()
                st.success("Salvo!")

        if itens_r2 and rel["total_pagar"] > 0:
            st.divider()
            st.subheader("🖨️ Relatório")
            linhas_html = "".join(
                f"<tr><td style='padding:6px 8px'>{i['produto']}</td>"
                f"<td style='text-align:center;padding:6px 8px'>{i['quantidade']}</td>"
                f"<td style='text-align:right;padding:6px 8px'>R${i['preco_unitario']:.2f}</td>"
                f"<td style='text-align:right;padding:6px 8px'>R${i['subtotal']:.2f}</td></tr>"
                for i in itens_r2
            )
            st.markdown(f"""
<div style="font-family:Arial;max-width:580px;border:2px solid {NAVY};border-radius:8px;padding:20px">
<h3 style="color:{NAVY};text-align:center;margin:0 0 4px">BACKBE — Relatório de Costura</h3>
<p style="text-align:center;color:#666;margin:0 0 16px">{MESES_R[mes_r-1]}/{ano_r} — {mae['nome']}</p>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<tr style="background:{NAVY};color:white">
<th style="padding:6px 8px;text-align:left">Produto</th>
<th style="padding:6px 8px;text-align:center">Qtde</th>
<th style="padding:6px 8px;text-align:right">R$/peça</th>
<th style="padding:6px 8px;text-align:right">Subtotal</th>
</tr>
{linhas_html}
<tr style="border-top:2px solid {NAVY};background:#f4f1ee">
<td colspan="2" style="padding:8px;font-weight:bold">TOTAL</td>
<td></td>
<td style="text-align:right;font-weight:bold;padding:8px">R${rel['total_costura']:.2f}</td>
</tr>
<tr><td colspan="2" style="padding:4px 8px">Comissão {rel['comissao_pct']:.0f}%</td>
<td></td><td style="text-align:right;padding:4px 8px">R${rel['comissao_valor']:.2f}</td></tr>
<tr style="background:{PINK}33"><td colspan="2" style="padding:8px;font-weight:bold;font-size:15px">TOTAL A PAGAR</td>
<td></td><td style="text-align:right;font-weight:bold;font-size:15px;padding:8px">R${rel['total_pagar']:.2f}</td></tr>
</table>
<p style="color:#999;font-size:11px;margin-top:12px">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

    with tab_hist_r:
        st.subheader("📅 Histórico de pagamentos")
        hist = rows_to_list(conn.execute(
            "SELECT * FROM relatorio_mae WHERE costureira_id=? ORDER BY ano DESC, mes DESC",
            (mae["id"],)
        ).fetchall())
        if not hist:
            st.info("Sem histórico ainda.")
        else:
            # Junta dados de corte para exibir junto
            _cortes_map = {(r["mes"], r["ano"]): float(r["total_corte"] or 0)
                           for r in rows_to_list(conn.execute(
                               "SELECT mes, ano, total_corte FROM relatorio_corte"
                           ).fetchall())}
            df_h = pd.DataFrame([{
                "Mês/Ano": f"{MESES_R[h['mes']-1]}/{h['ano']}",
                "Peças": h["total_pecas"],
                "Costura R$": h["total_costura"],
                "Corte (Vó) R$": _cortes_map.get((h["mes"], h["ano"]), 0),
                "Comissão R$": h["comissao_valor"],
                "Total Costura R$": h["total_pagar"],
                "Status": "✅ Pago" if h["pago"] else "⏳ Pendente",
            } for h in hist])
            st.dataframe(df_h, use_container_width=True, hide_index=True)
            c_p, c_pen, c_corte = st.columns(3)
            c_p.metric("Total costura pago", f"R${sum(h['total_pagar'] for h in hist if h['pago']):.2f}")
            c_pen.metric("Total pendente", f"R${sum(h['total_pagar'] for h in hist if not h['pago']):.2f}")
            c_corte.metric("Total corte (Vó)", f"R${sum(_cortes_map.values()):.2f}")

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — CALENDÁRIO (datas comerciais/moda + ordens de produção)
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "▷ Calendario":

    # ── Datas especiais (comercial, moda, fiscal, feriado) ────────────────────
    DATAS_ESPECIAIS = [
        # Mai/2026
        {"data": "2026-05-31", "nome": "DASN-SIMEI (prazo MEI)", "tipo": "fiscal"},
        # Jun/2026
        {"data": "2026-06-04", "nome": "Corpus Christi", "tipo": "feriado"},
        {"data": "2026-06-12", "nome": "Dia dos Namorados 💑", "tipo": "comercial"},
        # Jul/2026
        {"data": "2026-07-01", "nome": "Liquidação de Inverno", "tipo": "moda"},
        {"data": "2026-07-09", "nome": "Revolução Constitucionalista", "tipo": "feriado"},
        # Ago/2026
        {"data": "2026-08-09", "nome": "Dia dos Pais", "tipo": "comercial"},
        # Set/2026
        {"data": "2026-09-07", "nome": "Independência do Brasil", "tipo": "feriado"},
        {"data": "2026-09-14", "nome": "Início SPFW", "tipo": "moda"},
        # Out/2026
        {"data": "2026-10-12", "nome": "Dia das Crianças", "tipo": "comercial"},
        {"data": "2026-10-28", "nome": "Servidor Público", "tipo": "feriado"},
        {"data": "2026-10-31", "nome": "Halloween Fashion 🎃", "tipo": "moda"},
        # Nov/2026
        {"data": "2026-11-02", "nome": "Finados", "tipo": "feriado"},
        {"data": "2026-11-15", "nome": "Proclamação da República", "tipo": "feriado"},
        {"data": "2026-11-27", "nome": "Black Friday 🖤", "tipo": "comercial"},
        {"data": "2026-11-30", "nome": "Cyber Monday", "tipo": "comercial"},
        # Dez/2026
        {"data": "2026-12-08", "nome": "Imaculada Conceição", "tipo": "feriado"},
        {"data": "2026-12-15", "nome": "Prazo col. Verão 2027", "tipo": "moda"},
        {"data": "2026-12-25", "nome": "Natal 🎄", "tipo": "comercial"},
        {"data": "2026-12-31", "nome": "Réveillon", "tipo": "feriado"},
        # Jan/2027
        {"data": "2027-01-01", "nome": "Ano Novo", "tipo": "feriado"},
        {"data": "2027-01-15", "nome": "Liquidação de Verão", "tipo": "moda"},
        # Fev/2027
        {"data": "2027-02-15", "nome": "Carnaval", "tipo": "feriado"},
        {"data": "2027-02-16", "nome": "Carnaval", "tipo": "feriado"},
        # Mar/2027
        {"data": "2027-03-08", "nome": "Dia Internacional da Mulher", "tipo": "moda"},
        # Abr/2027
        {"data": "2027-04-02", "nome": "Páscoa 🐣", "tipo": "comercial"},
        # Mai/2027
        {"data": "2027-05-09", "nome": "Dia das Mães 🌸", "tipo": "comercial"},
        {"data": "2027-05-31", "nome": "DASN-SIMEI (prazo MEI)", "tipo": "fiscal"},
        # Jun/2027
        {"data": "2027-06-12", "nome": "Dia dos Namorados 💑", "tipo": "comercial"},
    ]

    TIPO_COLORS = {
        "feriado":   {"dot": "#9CA3AF", "bg": "#F3F4F6", "text": "#6B7280"},
        "comercial": {"dot": PINK,       "bg": "#FDF0F8", "text": PINK},
        "moda":      {"dot": GOLD,       "bg": "#FFFBEB", "text": "#92400E"},
        "fiscal":    {"dot": "#DC2626",  "bg": "#FEE2E2", "text": "#991B1B"},
    }

    # ── Navegação de mês ──────────────────────────────────────────────────────
    if "cal_y" not in st.session_state:
        st.session_state.cal_y = datetime.now().year
        st.session_state.cal_m = datetime.now().month

    MESES_C = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

    nav_l, nav_c, nav_r = st.columns([1, 4, 1])
    with nav_l:
        if st.button("← Anterior", use_container_width=True):
            if st.session_state.cal_m == 1:
                st.session_state.cal_m = 12
                st.session_state.cal_y -= 1
            else:
                st.session_state.cal_m -= 1
            st.rerun()
    with nav_r:
        if st.button("Próximo →", use_container_width=True):
            if st.session_state.cal_m == 12:
                st.session_state.cal_m = 1
                st.session_state.cal_y += 1
            else:
                st.session_state.cal_m += 1
            st.rerun()
    with nav_c:
        st.markdown(f"""
<div style="text-align:center;padding:6px 0">
  <div style="font-size:22px;font-weight:700;color:{NAVY}">{MESES_C[st.session_state.cal_m-1]} {st.session_state.cal_y}</div>
</div>
""", unsafe_allow_html=True)

    cy, cm = st.session_state.cal_y, st.session_state.cal_m

    # ── Carregar ordens de produção ───────────────────────────────────────────
    conn_cal = get_conn()
    ordens_cal = rows_to_list(conn_cal.execute(
        "SELECT * FROM ordens_producao WHERE status != 'pronto' ORDER BY data_entrada"
    ).fetchall())
    conn_cal.close()

    def _est_days(o):
        qty = max(1, o.get("quantidade") or 1)
        return max(5, (qty // 7) + 5)

    # ── Mapear eventos e ordens por dia do mês ────────────────────────────────
    days_in_month = cal_lib.monthrange(cy, cm)[1]
    month_str = f"{cy}-{cm:02d}"

    month_events = {}
    for d in DATAS_ESPECIAIS:
        if d["data"].startswith(month_str):
            day_num = int(d["data"].split("-")[2])
            month_events.setdefault(day_num, []).append(d)

    order_days = {}
    for o in ordens_cal:
        try:
            start = datetime.strptime(o["data_entrada"][:10], "%Y-%m-%d").date()
        except Exception:
            start = dt_date.today()
        if o.get("data_prevista"):
            try:
                end_d = datetime.strptime(o["data_prevista"][:10], "%Y-%m-%d").date()
            except Exception:
                end_d = start + timedelta(days=_est_days(o))
        else:
            end_d = start + timedelta(days=_est_days(o))
        month_start = dt_date(cy, cm, 1)
        month_end   = dt_date(cy, cm, days_in_month)
        if start <= month_end and end_d >= month_start:
            for day in range(1, days_in_month + 1):
                d_obj = dt_date(cy, cm, day)
                if start <= d_obj <= end_d:
                    order_days.setdefault(day, []).append(o)

    # ── Gerar grid HTML do calendário ─────────────────────────────────────────
    cal_weeks = cal_lib.monthcalendar(cy, cm)
    today_d   = dt_date.today()
    days_header = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]

    STATUS_BG = {
        "modelagem":  GOLD,
        "corte":      "#F97316",
        "costura":    PINK,
        "acabamento": "#7C3AED",
    }

    cal_html = f"""
<div style="background:white;border-radius:18px;padding:20px 22px 22px;
            box-shadow:0 2px 16px rgba(0,0,0,0.05);border:1px solid #F0ECE7">
  <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin-bottom:6px">
"""
    for i, dh in enumerate(days_header):
        c = "#DC2626" if i == 6 else ("#9CA3AF" if i == 5 else NAVY)
        cal_html += f'<div style="text-align:center;font-size:10px;font-weight:700;color:{c};padding:4px 0;letter-spacing:0.05em;text-transform:uppercase">{dh}</div>'
    cal_html += '</div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px">'

    for week in cal_weeks:
        for col_idx, day in enumerate(week):
            is_sun = col_idx == 6
            is_sat = col_idx == 5
            if day == 0:
                cal_html += '<div></div>'
                continue

            is_today  = (day == today_d.day and cy == today_d.year and cm == today_d.month)
            events    = month_events.get(day, [])
            orders    = order_days.get(day, [])

            if is_today:
                cell_bg, num_color, border = NAVY, "white", f"border:2px solid {NAVY}"
            elif events:
                tc = TIPO_COLORS[events[0]["tipo"]]
                cell_bg, num_color, border = tc["bg"], "#374151", "border:1px solid #E5E7EB"
            elif orders:
                cell_bg, num_color, border = "#EFF6FF", NAVY, f"border:1px solid #BFDBFE"
            elif is_sun:
                cell_bg, num_color, border = "#FFF5F5", "#DC2626", "border:1px solid #FECACA"
            elif is_sat:
                cell_bg, num_color, border = "#FAFAFA", "#9CA3AF", "border:1px solid #F0ECE7"
            else:
                cell_bg, num_color, border = "white", NAVY, "border:1px solid #F0ECE7"

            cal_html += f'<div style="background:{cell_bg};border-radius:10px;{border};padding:7px 6px 6px;min-height:72px">'
            cal_html += f'<div style="font-size:13px;font-weight:{"700" if is_today else "600"};color:{num_color};margin-bottom:3px">{day}</div>'

            for ev in events[:1]:
                ev_color = "white" if is_today else TIPO_COLORS[ev["tipo"]]["text"]
                short    = ev["nome"][:13] + ("…" if len(ev["nome"]) > 13 else "")
                cal_html += f'<div style="font-size:8.5px;font-weight:600;color:{ev_color};line-height:1.3;margin-bottom:2px">{short}</div>'

            for o in orders[:2]:
                s_col = STATUS_BG.get(o.get("status","modelagem"), NAVY)
                prod_short = (o["produto"][:11] + "…") if len(o["produto"]) > 11 else o["produto"]
                cal_html += (
                    f'<div style="background:{s_col};color:white;border-radius:4px;'
                    f'font-size:8px;font-weight:600;padding:1px 4px;margin-top:2px;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                    f'{prod_short}</div>'
                )
            if len(orders) > 2:
                cal_html += f'<div style="font-size:8px;color:#9CA3AF;margin-top:1px">+{len(orders)-2} mais</div>'

            cal_html += '</div>'

    cal_html += '</div></div>'

    # ── Layout: calendário (esquerda) + próximas datas (direita) ─────────────
    cal_col, ev_col = st.columns([6.5, 3.5], gap="large")

    with cal_col:
        st.markdown(cal_html, unsafe_allow_html=True)
        st.markdown(f"""
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;padding:4px 0">
  <span style="font-size:11px;color:#9CA3AF;font-weight:600;align-self:center">Legenda:</span>
  {''.join([f'<span style="background:{tc["bg"]};color:{tc["dot"]};padding:3px 10px;border-radius:99px;font-size:11px;font-weight:600">{k}</span>' for k, tc in TIPO_COLORS.items()])}
  <span style="background:#EFF6FF;color:{NAVY};padding:3px 10px;border-radius:99px;font-size:11px;font-weight:600">🏭 produção</span>
  <span style="background:{NAVY};color:white;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:600">hoje</span>
</div>
""", unsafe_allow_html=True)

    with ev_col:
        # ── Notion: busca conteúdo da semana ─────────────────────────────────
        @st.cache_data(ttl=1800, show_spinner=False)
        def _load_notion_week():
            return get_week_content()

        notion_posts = []
        notion_error = None
        if notion_ok():
            try:
                notion_posts = _load_notion_week()
                if notion_posts and notion_posts[0].get("_error"):
                    notion_error = notion_posts[0]["_error"]
                    notion_posts = []
            except Exception as e:
                notion_error = str(e)

        tab_datas, tab_conteudo = st.tabs(["📅 Próximas Datas", "📝 Conteúdo da Semana"])

        with tab_datas:
            upcoming = []
            for d in DATAS_ESPECIAIS:
                try:
                    d_obj = datetime.strptime(d["data"], "%Y-%m-%d").date()
                    if d_obj >= today_d:
                        upcoming.append({**d, "days_until": (d_obj - today_d).days, "d_obj": d_obj})
                except Exception:
                    pass
            upcoming = sorted(upcoming, key=lambda x: x["days_until"])[:12]

            st.markdown(f"""
<div class="wcard" style="max-height:440px;overflow-y:auto;padding:16px 18px">
  <div style="font-size:14px;font-weight:700;color:{NAVY};margin-bottom:12px">Datas importantes</div>
""", unsafe_allow_html=True)
            for ev in upcoming:
                tc = TIPO_COLORS[ev["tipo"]]
                du = ev["days_until"]
                dias_label = "hoje!" if du == 0 else (f"⚠ {du}d" if du <= 7 else f"{du}d")
                bold = "font-weight:700" if du <= 14 else ""
                gcal = gcal_link(ev["nome"], ev["data"])
                gcal_btn = (
                    f'<a href="{gcal}" target="_blank" '
                    f'style="font-size:9px;color:#9CA3AF;text-decoration:none;'
                    f'border:1px solid #E5E7EB;border-radius:4px;padding:1px 5px">+GCal</a>'
                ) if gcal else ""
                st.markdown(f"""
  <div style="display:flex;justify-content:space-between;align-items:center;
              padding:7px 0;border-bottom:1px solid #F0F2F5">
    <div style="flex:1">
      <div style="font-size:11.5px;font-weight:600;color:{NAVY};{bold}">{ev['nome']}</div>
      <div style="font-size:10px;color:#9CA3AF;margin-top:1px;display:flex;align-items:center;gap:6px">
        {ev['d_obj'].strftime('%d/%m/%Y')} {gcal_btn}
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:5px;flex-shrink:0">
      <span style="background:{tc['bg']};color:{tc['dot']};padding:1px 6px;border-radius:99px;font-size:9px;font-weight:700">{ev['tipo']}</span>
      <span style="font-size:11px;font-weight:700;color:{NAVY};min-width:36px;text-align:right">{dias_label}</span>
    </div>
  </div>
""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            with st.expander("➕ Adicionar data personalizada", expanded=False):
                with st.form("form_data_custom", clear_on_submit=True):
                    d_nome = st.text_input("Nome do evento")
                    d_data = st.date_input("Data", value=dt_date.today())
                    d_tipo = st.selectbox("Tipo", ["comercial", "moda", "feriado", "fiscal"])
                    if st.form_submit_button("Salvar", type="primary"):
                        st.success("Salvo! (datas permanentes em breve)")

        with tab_conteudo:
            if not notion_ok():
                st.markdown(f"""
<div class="wcard" style="padding:20px;text-align:center">
  <div style="font-size:28px;margin-bottom:8px">📓</div>
  <div style="font-size:14px;font-weight:700;color:{NAVY}">Conectar Notion</div>
  <div style="font-size:12px;color:#9CA3AF;margin-top:6px;line-height:1.5">
    Adicione <code>NOTION_TOKEN</code> nos secrets do Streamlit.<br>
    Veja o .env.example para instruções.
  </div>
</div>""", unsafe_allow_html=True)
            elif notion_error:
                st.warning(f"Erro ao buscar Notion: {notion_error}")
            elif not notion_posts:
                st.markdown(f"""
<div class="wcard" style="padding:20px;text-align:center">
  <div style="font-size:28px;margin-bottom:6px">📭</div>
  <div style="font-size:13px;color:#9CA3AF">Nenhum post encontrado para esta semana no Notion.</div>
</div>""", unsafe_allow_html=True)
            else:
                STATUS_COLORS = {
                    "Publicado":  ("#DCFCE7","#15803D"),
                    "Publicar":   ("#DBEAFE","#1D4ED8"),
                    "Gravar":     ("#FEF9C3","#92400E"),
                    "Em edição":  ("#EDE9FE","#5B21B6"),
                    "Ideia":      ("#F3F4F6","#6B7280"),
                }
                st.markdown(f"""
<div class="wcard" style="max-height:440px;overflow-y:auto;padding:16px 18px">
  <div style="font-size:14px;font-weight:700;color:{NAVY};margin-bottom:12px">
    Semana atual — {len(notion_posts)} posts
  </div>
""", unsafe_allow_html=True)
                for post in notion_posts:
                    sb, sc = STATUS_COLORS.get(post["status"], ("#F3F4F6","#6B7280"))
                    data_fmt = post["data_post"].strftime("%d/%m") if post.get("data_post") else post.get("dia","?")
                    gcal = gcal_link(
                        f"{post['plataforma']} — {post['titulo']}",
                        post["data_post"].strftime("%Y-%m-%d") if post.get("data_post") else "",
                        post.get("detalhes","")[:200]
                    ) if post.get("data_post") else ""
                    gcal_btn = (
                        f'<a href="{gcal}" target="_blank" '
                        f'style="font-size:9px;color:#9CA3AF;text-decoration:none;'
                        f'border:1px solid #E5E7EB;border-radius:4px;padding:1px 5px">+GCal</a>'
                    ) if gcal else ""
                    notion_link = (
                        f'<a href="{post["url"]}" target="_blank" '
                        f'style="font-size:9px;color:{PINK};text-decoration:none;'
                        f'border:1px solid #F9D2E9;border-radius:4px;padding:1px 5px">Notion</a>'
                    ) if post.get("url") else ""
                    st.markdown(f"""
  <div style="padding:9px 0;border-bottom:1px solid #F0F2F5">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
      <span style="font-size:14px">{post['icon']}</span>
      <span style="font-size:11.5px;font-weight:700;color:{NAVY};flex:1">{post['titulo'][:45]}</span>
    </div>
    <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap">
      <span style="background:#F0F2F5;color:#374151;padding:1px 7px;border-radius:99px;font-size:10px;font-weight:600">{post['plataforma']}</span>
      <span style="background:{sb};color:{sc};padding:1px 7px;border-radius:99px;font-size:10px;font-weight:600">{post['status']}</span>
      <span style="font-size:10px;color:#9CA3AF">{data_fmt} ({post['dia']})</span>
      {gcal_btn}
      {notion_link}
    </div>
  </div>
""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            if notion_ok() and notion_posts:
                if st.button("↺ Atualizar conteúdo Notion", use_container_width=True,
                             key="btn_refresh_notion"):
                    st.cache_data.clear()
                    st.rerun()

    # ── Exportar para Google Calendar (ICS) ──────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("📅 Exportar calendário para Google Calendar / iPhone", expanded=False):
        st.markdown(f"""
<div style="font-size:13px;color:#374151;line-height:1.7;margin-bottom:12px">
  Baixe o arquivo <strong>.ics</strong> e importe no Google Calendar — os eventos aparecem
  automaticamente no celular com notificações.<br>
  <span style="color:#9CA3AF;font-size:12px">
  Google Calendar → Configurações → Importar → selecione o arquivo
  </span>
</div>
""", unsafe_allow_html=True)
        _inc_prod  = st.checkbox("Incluir ordens de produção", value=True, key="ics_prod")
        _inc_cont  = st.checkbox("Incluir posts do Notion", value=True, key="ics_cont")
        if st.button("⬇ Gerar arquivo .ics", type="primary", key="btn_ics"):
            _posts_ics = notion_posts if (_inc_cont and notion_ok()) else []
            _ics_str   = build_ics(
                datas_especiais=DATAS_ESPECIAIS,
                ordens=ordens_cal if _inc_prod else [],
                notion_posts=_posts_ics,
                include_producao=_inc_prod,
                include_conteudo=_inc_cont,
            )
            st.download_button(
                label="📥 Baixar backbe_calendario.ics",
                data=_ics_str.encode("utf-8"),
                file_name="backbe_calendario.ics",
                mime="text/calendar",
                key="download_ics",
            )

    # ── Gantt de ordens de produção ───────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if ordens_cal:
        st.markdown(f"""
<div style="background:white;border-radius:18px;padding:22px 24px 16px;
            box-shadow:0 2px 16px rgba(0,0,0,0.05);border:1px solid #F0ECE7">
  <div style="font-size:15px;font-weight:700;color:{NAVY}">🏭 Linha do tempo das ordens ativas</div>
  <div style="font-size:12px;color:#9CA3AF;margin-top:2px;margin-bottom:12px">
    Duração estimada por quantidade. Defina "Data prevista" nas ordens para maior precisão.
  </div>
""", unsafe_allow_html=True)

        STATUS_GANTT = {
            "modelagem":  GOLD,
            "corte":      "#F97316",
            "costura":    PINK,
            "acabamento": "#7C3AED",
        }

        gantt_rows = []
        for o in ordens_cal:
            try:
                g_start = datetime.strptime(o["data_entrada"][:10], "%Y-%m-%d")
            except Exception:
                g_start = datetime.now()
            if o.get("data_prevista"):
                try:
                    g_end = datetime.strptime(o["data_prevista"][:10], "%Y-%m-%d")
                except Exception:
                    g_end = g_start + timedelta(days=_est_days(o))
            else:
                g_end = g_start + timedelta(days=_est_days(o))
            if g_end <= g_start:
                g_end = g_start + timedelta(days=1)

            label = f"{o['produto'][:30]} ×{o['quantidade']}"
            gantt_rows.append({
                "Ordem":      label,
                "Início":     g_start,
                "Fim":        g_end,
                "Status":     o.get("status", "modelagem"),
                "Prioridade": o.get("prioridade", "normal"),
            })

        if gantt_rows:
            df_g = pd.DataFrame(gantt_rows).sort_values("Início")
            fig_g = px.timeline(
                df_g,
                x_start="Início",
                x_end="Fim",
                y="Ordem",
                color="Status",
                color_discrete_map=STATUS_GANTT,
                hover_data={"Prioridade": True, "Início": "|%d/%m/%Y", "Fim": "|%d/%m/%Y"},
            )
            fig_g.update_yaxes(autorange="reversed")
            fig_g.add_vline(
                x=datetime.now(),
                line_color=PINK, line_dash="dash", line_width=1.5,
                annotation_text="hoje",
                annotation_font_size=10,
                annotation_font_color=PINK,
                annotation_position="top right",
            )
            fig_g.update_layout(
                height=max(160, len(df_g) * 44 + 70),
                margin=dict(t=10, b=20, l=8, r=8),
                plot_bgcolor="white",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    tickformat="%d/%m",
                    tickfont=dict(size=11, color="#9CA3AF"),
                    showgrid=True, gridcolor="#F7F5F3",
                    title=None,
                ),
                yaxis=dict(tickfont=dict(size=11, color=NAVY), showgrid=False, title=None),
                legend=dict(orientation="h", x=0, y=-0.15, font=dict(size=11), title=None),
            )
            st.plotly_chart(fig_g, width="stretch")

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style="background:white;border-radius:18px;padding:32px 24px;text-align:center;
            box-shadow:0 2px 16px rgba(0,0,0,0.05);border:1px solid #F0ECE7">
  <div style="font-size:32px;margin-bottom:8px">🏭</div>
  <div style="font-size:15px;font-weight:600;color:{NAVY}">Nenhuma ordem de produção ativa</div>
  <div style="font-size:13px;color:#9CA3AF;margin-top:4px">Crie ordens na página 🏭 para vê-las aqui na linha do tempo.</div>
</div>
""", unsafe_allow_html=True)

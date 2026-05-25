import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date as dt_date
import calendar as cal_lib
import sqlite3, math, json
from pathlib import Path

from db import init_db, get_conn, rows_to_list, row_to_dict
from api_ns import fetch_all_orders, fetch_all_customers, compute_sales, compute_customers
from nubank_parser import parse_nubank_pdf


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
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded",
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Base ───────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp, button, input, select, textarea {{
    font-family: 'Inter', -apple-system, sans-serif !important;
}}
.stApp {{ background: {BG} !important; }}
.main .block-container {{
    padding: 1.6rem 2rem 3rem !important;
    background: {BG} !important;
    max-width: 1440px;
}}

/* ── Sidebar — branca estilo SaaS ───────────────────────────── */
section[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"],
div[data-testid="stSidebarContent"] {{
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}}
/* Hide label */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
div[data-testid="stSidebarContent"] [data-testid="stWidgetLabel"] {{
    display: none !important;
}}
/* Hide radio circle indicator */
section[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child,
div[data-testid="stSidebarContent"] [data-baseweb="radio"] > div:first-child {{
    display: none !important;
}}
/* Radio group column */
section[data-testid="stSidebar"] [data-baseweb="radio-group"],
div[data-testid="stSidebarContent"] [data-baseweb="radio-group"] {{
    gap: 1px !important; display: flex !important; flex-direction: column !important;
}}
/* Nav item — default */
section[data-testid="stSidebar"] [data-baseweb="radio"] label,
div[data-testid="stSidebarContent"] [data-baseweb="radio"] label {{
    width: 100% !important;
    padding: 9px 14px 9px 14px !important;
    border-radius: 8px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    cursor: pointer !important;
    transition: all 0.12s ease !important;
    display: flex !important;
    align-items: center !important;
    margin: 0 !important;
    user-select: none !important;
    letter-spacing: -0.01em !important;
}}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover,
div[data-testid="stSidebarContent"] [data-baseweb="radio"] label:hover {{
    background: #F3F4F6 !important;
    color: #111827 !important;
}}
/* Active nav item */
section[data-testid="stSidebar"] [data-baseweb="radio"] label:has(input:checked),
div[data-testid="stSidebarContent"] [data-baseweb="radio"] label:has(input:checked) {{
    background: {PURPLE}14 !important;
    color: {PURPLE} !important;
    font-weight: 600 !important;
}}
/* Hide radio input */
section[data-testid="stSidebar"] [data-baseweb="radio"] input,
div[data-testid="stSidebarContent"] [data-baseweb="radio"] input {{
    position: absolute !important; opacity: 0 !important;
    width: 0 !important; height: 0 !important;
}}
/* Sidebar button */
section[data-testid="stSidebar"] .stButton > button,
div[data-testid="stSidebarContent"] .stButton > button {{
    background: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
    color: #6B7280 !important;
    border-radius: 8px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    transition: all 0.12s !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover,
div[data-testid="stSidebarContent"] .stButton > button:hover {{
    background: #F3F4F6 !important;
    color: {PURPLE} !important;
    border-color: {PURPLE}40 !important;
}}

/* ── Typography ─────────────────────────────────────────────── */
h1 {{ color:{NAVY};font-size:20px !important;font-weight:700 !important;margin-bottom:0 !important; }}
h2 {{ color:{NAVY};font-size:15px !important;font-weight:600 !important; }}
h3 {{ color:{NAVY};font-size:13px !important;font-weight:600 !important; }}

/* ── Chip tags (weihu style) ─────────────────────────────────── */
.chip        {{ display:inline-flex;align-items:center;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:600;letter-spacing:0.01em; }}
.chip-purple {{ background:#EDE9FE;color:#6D28D9; }}
.chip-pink   {{ background:#FCE7F3;color:#9D174D; }}
.chip-orange {{ background:#FFEDD5;color:#9A3412; }}
.chip-green  {{ background:#DCFCE7;color:#166534; }}
.chip-blue   {{ background:#DBEAFE;color:#1E40AF; }}
.chip-yellow {{ background:#FEF9C3;color:#854D0E; }}
.chip-gray   {{ background:#F3F4F6;color:#6B7280; }}

/* ── KPI cards — brancos com chip de cor no topo ─────────────── */
.kpi-card {{
    background: white;
    border-radius: 16px;
    padding: 20px 22px 18px;
    border: 1px solid #F3F4F6;
    box-shadow: 0 1px 8px rgba(0,0,0,0.05);
    transition: box-shadow 0.2s;
}}
.kpi-card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.09); }}
.kpi-accent {{ width:36px;height:5px;border-radius:99px;margin-bottom:16px; }}
.kpi-label  {{ font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px; }}
.kpi-value  {{ font-size:32px;font-weight:800;color:{NAVY};letter-spacing:-0.03em;line-height:1; }}
.kpi-sub    {{ font-size:12px;margin-top:6px;color:#9CA3AF;font-weight:400; }}

/* ── White content cards ─────────────────────────────────────── */
.wcard {{
    background: white;
    border-radius: 16px;
    padding: 22px 24px;
    border: 1px solid #F3F4F6;
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
}}
.wcard-title {{
    font-size: 14px; font-weight: 700; color: {NAVY}; margin-bottom: 4px;
}}
.wcard-sub {{
    font-size: 12px; color: #9CA3AF; font-weight: 400;
}}

/* ── Task/item cards (weihu style) ───────────────────────────── */
.task-card {{
    background: white;
    border-radius: 14px;
    padding: 16px 18px;
    border: 1px solid #F3F4F6;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    margin-bottom: 10px;
}}
.task-title {{ font-size:13.5px;font-weight:600;color:{NAVY};line-height:1.4; }}
.task-note  {{ font-size:12px;color:#9CA3AF;margin-top:4px; }}

/* ── Badges ─────────────────────────────────────────────────── */
.bb-badge   {{ display:inline-flex;align-items:center;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:600; }}
.badge-green  {{ background:#DCFCE7;color:#15803D; }}
.badge-red    {{ background:#FEE2E2;color:#B91C1C; }}
.badge-yellow {{ background:#FEF9C3;color:#92400E; }}
.badge-pink   {{ background:#FCE7F3;color:#9D174D; }}
.badge-blue   {{ background:#DBEAFE;color:#1E40AF; }}
.badge-gray   {{ background:#F3F4F6;color:#6B7280; }}
.badge-purple {{ background:#EDE9FE;color:#6D28D9; }}

/* ── Metrics ─────────────────────────────────────────────────── */
.stMetric {{ background:white;border-radius:14px;padding:16px 18px !important;box-shadow:0 1px 6px rgba(0,0,0,0.05);border:1px solid #F3F4F6; }}
.stMetric label {{ color:#9CA3AF !important;font-size:11px !important;font-weight:600 !important;text-transform:uppercase;letter-spacing:0.08em; }}
[data-testid="stMetricValue"] {{ color:{NAVY} !important;font-size:24px !important;font-weight:800 !important; }}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{ background:#F9FAFB;border-radius:10px;padding:3px;border:1px solid #E5E7EB;gap:1px; }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px !important;font-weight:500 !important;font-size:13px !important;padding:6px 14px !important;color:#6B7280 !important; }}
.stTabs [aria-selected="true"] {{ background:{PURPLE} !important;color:white !important; }}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button {{ border-radius:8px !important;font-weight:600 !important;font-size:13px !important; }}
.stButton > button[kind="primary"] {{ background:{PURPLE} !important;color:white !important;border:none !important; }}
.stButton > button[kind="secondary"] {{ border:1px solid #E5E7EB !important;color:{NAVY} !important;background:#F9FAFB !important; }}

/* ── Misc ────────────────────────────────────────────────────── */
.stDataFrame {{ border-radius:12px !important;overflow:hidden !important; }}
.stAlert {{ border-radius:10px !important; }}
.streamlit-expanderHeader {{ border-radius:8px !important;font-weight:500 !important; }}
hr {{ border-color:#F3F4F6 !important; }}

/* ── CRM pills ───────────────────────────────────────────────── */
.pill-vip  {{ background:#FEF9C3;color:#713F12;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-ativo{{ background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-reat {{ background:#FFEDD5;color:#9A3412;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}
.pill-perd {{ background:#F3F4F6;color:#6B7280;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600; }}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {{
  .main .block-container {{ padding: 0.8rem 0.6rem 2rem !important; }}
  .kpi-card {{ padding: 16px 16px 14px; }}
  .kpi-value {{ font-size: 26px; }}
  .wcard {{ padding: 16px 16px; }}
}}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div style="padding:6px 0 18px 0">
  <div style="display:flex;align-items:center;gap:10px">
    <div style="width:38px;height:38px;background:{PURPLE};
                border-radius:10px;display:flex;align-items:center;justify-content:center;
                font-size:20px;flex-shrink:0">⭐</div>
    <div>
      <div style="font-size:17px;font-weight:800;color:#111827;letter-spacing:-0.5px;line-height:1.1">Backbe</div>
      <div style="font-size:9px;color:#9CA3AF;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.15em;margin-top:1px">Central</div>
    </div>
  </div>
</div>
<div style="margin-bottom:4px">
  <div style="font-size:10px;font-weight:700;color:#D1D5DB;text-transform:uppercase;
              letter-spacing:0.12em;padding:0 6px;margin-bottom:4px">Visão Geral</div>
</div>
""", unsafe_allow_html=True)
    pagina = st.radio("Navegação", [
        "📊 Dashboard",
        "📅 Calendário",
        "🧶 Produtos",
        "👥 CRM — Clientes",
        "🧵 Tecidos",
        "🔩 Acabamentos",
        "🏭 Ordens de Produção",
        "💰 Calculadora CMV",
        "📈 Crescimento",
        "👩 Relatório Mãe",
        "📄 Declaração MEI",
    ], label_visibility="collapsed")
    st.markdown("""
<div style="height:1px;background:#F3F4F6;margin:12px 0 8px 0"></div>
<div style="font-size:10px;font-weight:700;color:#D1D5DB;text-transform:uppercase;
            letter-spacing:0.12em;padding:0 6px;margin-bottom:4px">Configurações</div>
""", unsafe_allow_html=True)
    if st.button("🔄 Atualizar Nuvemshop", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""<div style="font-size:11px;color:#D1D5DB;text-align:center;margin-top:5px">dados atualizados a cada 1h</div>""", unsafe_allow_html=True)

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
#  PÁGINA 1 — DASHBOARD  (visão geral da empresa)
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":

    # ── Métricas base ────────────────────────────────────────────────────────
    total_rev    = sum(d["revenue"] for d in ns_monthly.values())
    total_orders = len(ns_orders)
    ticket_medio = total_rev / total_orders if total_orders else 0
    months_sorted = sorted(ns_monthly.keys())
    rev_atual = ns_monthly.get(months_sorted[-1], {}).get("revenue", 0) if months_sorted else 0
    rev_ant   = ns_monthly.get(months_sorted[-2], {}).get("revenue", 0) if len(months_sorted) > 1 else 0
    delta_pct = ((rev_atual - rev_ant) / rev_ant * 100) if rev_ant else 0
    delta_icon  = "↑" if delta_pct >= 0 else "↓"
    delta_color = "#16A34A" if delta_pct >= 0 else "#DC2626"
    delta_bg    = "#DCFCE7" if delta_pct >= 0 else "#FEE2E2"

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
    conn_d.close()
    total_em_prod = sum(o["cnt"] for o in ordens_raw)

    # ── Header ───────────────────────────────────────────────────────────────
    MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho",
                "julho","agosto","setembro","outubro","novembro","dezembro"]
    hoje = datetime.now()
    hora = hoje.hour
    saudacao = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            margin-bottom:24px;flex-wrap:wrap;gap:12px">
  <div>
    <div style="font-size:13px;color:#9CA3AF;font-weight:500;margin-bottom:2px">
      {saudacao}, <strong style="color:{NAVY}">Isabela</strong> 👋
    </div>
    <div style="font-size:22px;font-weight:800;color:{NAVY};letter-spacing:-0.5px;line-height:1.2">
      Visão Geral do Negócio
    </div>
    <div style="font-size:12px;color:#9CA3AF;margin-top:3px">
      {hoje.strftime('%A, %d')} de {MESES_PT[hoje.month-1]} de {hoje.year}
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:8px">
    <div style="background:white;border:1px solid #E5E7EB;border-radius:10px;
                padding:7px 16px;display:flex;align-items:center;gap:7px">
      <div style="width:7px;height:7px;background:#10B981;border-radius:50%"></div>
      <span style="font-size:12px;color:#374151;font-weight:500">Nuvemshop conectada</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── LINHA 1: 4 KPIs estilo weihu ─────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    total_k = total_rev / 1000

    with k1:
        st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-accent" style="background:#F59E0B"></div>
  <div class="kpi-label">💰 Faturamento total</div>
  <div class="kpi-value">R${total_k:.1f}k</div>
  <div class="kpi-sub">histórico Nuvemshop</div>
</div>
""", unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-accent" style="background:#10B981"></div>
  <div class="kpi-label">📦 Pedidos</div>
  <div class="kpi-value">{total_orders}</div>
  <div class="kpi-sub">ticket médio R${ticket_medio:.0f}</div>
</div>
""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-accent" style="background:{PINK}"></div>
  <div class="kpi-label">👥 Clientes</div>
  <div class="kpi-value">{len(ns_customers)}</div>
  <div class="kpi-sub">⭐ {segs['VIP']} VIP · {segs['Reativar']} reativar</div>
</div>
""", unsafe_allow_html=True)

    with k4:
        delta_bg2   = "#DCFCE7" if delta_pct >= 0 else "#FEE2E2"
        delta_col2  = "#15803D" if delta_pct >= 0 else "#B91C1C"
        st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-accent" style="background:{PURPLE}"></div>
  <div class="kpi-label">📈 Este mês</div>
  <div class="kpi-value">R${rev_atual/1000:.1f}k</div>
  <div style="margin-top:6px;display:flex;align-items:center;gap:6px">
    <span style="background:{delta_bg2};color:{delta_col2};padding:2px 8px;
                 border-radius:6px;font-size:11px;font-weight:700">{delta_icon}{abs(delta_pct):.1f}%</span>
    <span class="kpi-sub" style="margin-top:0">vs anterior</span>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ── LINHA 2: Gráfico principal (65%) + Alertas rápidos (35%) ─────────────
    chart_col, alert_col = st.columns([6.5, 3.5], gap="large")

    with chart_col:
        st.markdown(f"""
<div class="wcard" style="padding-bottom:6px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
    <div>
      <div class="wcard-title">Faturamento mensal</div>
      <div class="wcard-sub">Receita bruta por mês</div>
    </div>
    <span style="background:#F3F4F6;color:#6B7280;padding:4px 12px;border-radius:8px;
                 font-size:11px;font-weight:600;border:1px solid #E5E7EB">Todos os meses</span>
  </div>
""", unsafe_allow_html=True)
        if ns_monthly:
            df_monthly = pd.DataFrame([
                {"Mês": m[5:] + "/" + m[2:4], "Receita": d["revenue"]}
                for m, d in sorted(ns_monthly.items())
            ])
            fig_area = go.Figure()
            fig_area.add_trace(go.Scatter(
                x=df_monthly["Mês"], y=df_monthly["Receita"],
                fill="tozeroy",
                fillcolor="rgba(201,107,160,0.08)",
                line=dict(color=PINK, width=2.5),
                mode="lines",
                hovertemplate="R$%{y:,.0f}<extra></extra>",
            ))
            fig_area.add_trace(go.Scatter(
                x=df_monthly["Mês"], y=df_monthly["Receita"],
                mode="markers",
                marker=dict(color=PINK, size=6, line=dict(color="white", width=2)),
                showlegend=False, hoverinfo="skip",
            ))
            fig_area.update_layout(
                height=250,
                margin=dict(t=16, b=16, l=4, r=4),
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(showgrid=False, tickfont=dict(size=11, color="#98A2B3"), tickangle=-30),
                yaxis=dict(showgrid=True, gridcolor="#F5F0E8", tickprefix="R$",
                           tickfont=dict(size=10, color="#98A2B3"), gridwidth=1),
                showlegend=False,
            )
            st.plotly_chart(fig_area, width="stretch")
        else:
            st.markdown('<div style="padding:40px 0;text-align:center;color:#98A2B3;font-size:13px">Sem dados mensais ainda.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with alert_col:
        st.markdown(f"""
<div class="wcard" style="display:flex;flex-direction:column;gap:0;height:100%">

  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <div class="wcard-title">Atenção</div>
    <span style="background:#EDE9FE;color:{PURPLE};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600">3 itens</span>
  </div>

  <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #F3F4F6">
    <div style="width:38px;height:38px;background:#FCE7F3;border-radius:10px;flex-shrink:0;
                display:flex;align-items:center;justify-content:center;font-size:18px">📩</div>
    <div style="flex:1">
      <div style="font-size:11px;color:#9CA3AF;font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Para Reativar</div>
      <div style="font-size:22px;font-weight:800;color:{NAVY};line-height:1.2;margin-top:1px">{segs['Reativar']}</div>
      <div style="font-size:11px;color:#9CA3AF">clientes 60–180 dias</div>
    </div>
    <span class="chip chip-pink">reativar</span>
  </div>

  <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #F3F4F6">
    <div style="width:38px;height:38px;background:#FEF9C3;border-radius:10px;flex-shrink:0;
                display:flex;align-items:center;justify-content:center;font-size:18px">🏭</div>
    <div style="flex:1">
      <div style="font-size:11px;color:#9CA3AF;font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Em Produção</div>
      <div style="font-size:22px;font-weight:800;color:{NAVY};line-height:1.2;margin-top:1px">{total_em_prod}</div>
      <div style="font-size:11px;color:#9CA3AF">{n_urgentes} urgente(s) na fila</div>
    </div>
    <span class="chip chip-yellow">ordens</span>
  </div>

  <div style="display:flex;align-items:center;gap:12px;padding:12px 0 0">
    <div style="width:38px;height:38px;background:#DCFCE7;border-radius:10px;flex-shrink:0;
                display:flex;align-items:center;justify-content:center;font-size:18px">⭐</div>
    <div style="flex:1">
      <div style="font-size:11px;color:#9CA3AF;font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Clientes VIP</div>
      <div style="font-size:22px;font-weight:800;color:{NAVY};line-height:1.2;margin-top:1px">{segs['VIP']}</div>
      <div style="font-size:11px;color:#9CA3AF">3+ pedidos ou R$500+</div>
    </div>
    <span class="chip chip-green">VIP</span>
  </div>

</div>
""", unsafe_allow_html=True)

    # ── LINHA 3: Top Produtos | Segmentos clientes | Tamanhos ─────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns([4.6, 2.7, 2.7], gap="large")

    with b1:
        st.markdown(f"""
<div class="wcard">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <div class="wcard-title">🏆 Top Produtos</div>
    <span class="chip chip-gray">{len(ns_products)} produtos</span>
  </div>
""", unsafe_allow_html=True)
        for i, p in enumerate(ns_products[:8]):
            pct = p["revenue"] / total_rev * 100 if total_rev else 0
            bar_w = max(6, int(pct * 3.2))
            rank_bg   = PINK if i < 3 else "#E5E7EB"
            rank_color = "white" if i < 3 else "#6B7280"
            st.markdown(f"""
  <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F7F5F3">
    <span style="min-width:22px;height:22px;background:{rank_bg};color:{rank_color};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">{i+1}</span>
    <div style="flex:1;min-width:0">
      <div style="font-size:12px;font-weight:600;color:{NAVY};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{p['produto'][:36]}</div>
      <div style="background:#F3F4F6;border-radius:99px;height:4px;margin-top:5px">
        <div style="width:{bar_w}%;background:{PINK};border-radius:99px;height:4px"></div>
      </div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:12px;font-weight:700;color:{NAVY}">R${p['revenue']:,.0f}</div>
      <div style="font-size:10px;color:#9CA3AF">{p['units']} un · {pct:.0f}%</div>
    </div>
  </div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with b2:
        st.markdown(f"""<div class="bb-card">
  <div style="font-size:15px;font-weight:700;color:{NAVY};margin-bottom:8px">👥 Saúde da base</div>
""", unsafe_allow_html=True)
        if ns_customers:
            fig_seg = go.Figure(go.Pie(
                labels=list(segs.keys()),
                values=list(segs.values()),
                hole=0.58,
                marker_colors=["#EAB308","#22C55E","#F97316","#D1D5DB"],
                textinfo="none",
            ))
            fig_seg.update_layout(
                margin=dict(t=4, b=4, l=4, r=4),
                height=155,
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                annotations=[dict(
                    text=f"<b>{len(ns_customers)}</b><br><span style='font-size:10px'>clientes</span>",
                    x=0.5, y=0.5, font_size=14, font_color=NAVY,
                    showarrow=False
                )]
            )
            st.plotly_chart(fig_seg, width="stretch")
        st.markdown(f"""
  <div style="display:flex;flex-direction:column;gap:6px;margin-top:4px">
    <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 10px;background:#FEF9C3;border-radius:8px">
      <span style="font-size:12px;font-weight:600;color:#713F12">⭐ VIP</span>
      <span style="font-size:13px;font-weight:700;color:{NAVY}">{segs['VIP']}</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 10px;background:#DCFCE7;border-radius:8px">
      <span style="font-size:12px;font-weight:600;color:#15803D">✅ Ativos</span>
      <span style="font-size:13px;font-weight:700;color:{NAVY}">{segs['Ativo']}</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 10px;background:#FED7AA;border-radius:8px">
      <span style="font-size:12px;font-weight:600;color:#92400E">🔔 Reativar</span>
      <span style="font-size:13px;font-weight:700;color:{NAVY}">{segs['Reativar']}</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 10px;background:#F3F4F6;border-radius:8px">
      <span style="font-size:12px;font-weight:600;color:#6B7280">❌ Perdidos</span>
      <span style="font-size:13px;font-weight:700;color:{NAVY}">{segs['Perdido']}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    with b3:
        sizes_all = {}
        for p in ns_products:
            for s, q in (p.get("sizes") or {}).items():
                sizes_all[s] = sizes_all.get(s, 0) + q
        colors_all = {}
        for p in ns_products:
            for cor, q in (p.get("colors") or {}).items():
                colors_all[cor] = colors_all.get(cor, 0) + q

        st.markdown(f"""<div class="bb-card">
  <div style="font-size:15px;font-weight:700;color:{NAVY};margin-bottom:8px">📐 Tamanhos & Cores</div>
""", unsafe_allow_html=True)
        if sizes_all:
            df_sz = pd.DataFrame(
                sorted(sizes_all.items(), key=lambda x: -x[1])[:6],
                columns=["Tamanho", "Unidades"]
            )
            fig_sz = go.Figure(go.Bar(
                x=df_sz["Tamanho"],
                y=df_sz["Unidades"],
                marker_color=NAVY,
                marker_opacity=0.8,
                text=df_sz["Unidades"],
                textposition="outside",
                textfont_size=10,
            ))
            fig_sz.update_layout(
                height=155,
                margin=dict(t=8, b=8, l=0, r=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(visible=False),
                showlegend=False,
            )
            st.plotly_chart(fig_sz, width="stretch")

        if colors_all:
            st.markdown(f'<div style="font-size:12px;font-weight:600;color:{NAVY};margin:6px 0 6px">Cores mais vendidas</div>', unsafe_allow_html=True)
            for cor, qtd in sorted(colors_all.items(), key=lambda x: -x[1])[:4]:
                st.markdown(f"""
  <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #F7F5F3;font-size:12px">
    <span style="color:{NAVY};font-weight:500">{cor}</span>
    <span class="bb-badge badge-gray">{qtd} un</span>
  </div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA 2 — CRM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "👥 CRM — Clientes":
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
elif pagina == "🧵 Tecidos":
    st.title("🧵 Gestão de Tecidos")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Estoque", "➕ Cadastrar Tecido", "✏️ Editar Tecidos", "⚖️ Tabela kg → metro"])

    conn = get_conn()

    with tab1:
        st.subheader("Estoque de Tecidos")
        tecidos = rows_to_list(conn.execute("SELECT * FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())

        if not tecidos:
            st.info("Nenhum tecido cadastrado ainda.")
        else:
            for t in tecidos:
                preco_m = _calc_preco_metro(t)
                with st.expander(f"**{t['nome']}** — {t['tipo']} | R${preco_m:.2f}/metro | Estoque: {t['estoque']} {t['estoque_unidade']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Preço/metro", f"R${preco_m:.2f}")
                    c2.metric("Estoque", f"{t['estoque']} {t['estoque_unidade']}")
                    if t['unidade'] == 'kg':
                        c3.metric("Preço/kg", f"R${t['preco_kg']:.2f}")
                        c4.metric("Peso GSM", f"{t['peso_gsm']:.0f} g/m²")

                    col_est, col_btn = st.columns([2, 1])
                    novo_est = col_est.number_input(
                        "Atualizar estoque", value=float(t["estoque"]),
                        step=0.5, key=f"est_{t['id']}"
                    )
                    if col_btn.button("💾 Salvar", key=f"save_est_{t['id']}"):
                        conn.execute("UPDATE tecidos SET estoque=? WHERE id=?", (novo_est, t["id"]))
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

    with tab4:
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
elif pagina == "🏭 Ordens de Produção":
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

        tecidos_list = rows_to_list(conn.execute("SELECT * FROM tecidos WHERE ativo=1 ORDER BY nome").fetchall())
        costureiras_list = rows_to_list(conn.execute("SELECT * FROM costureiras WHERE ativa=1").fetchall())
        costura_precos = rows_to_list(conn.execute("SELECT * FROM costura_precos ORDER BY categoria").fetchall())

        with st.form("form_ordem"):
            c1, c2 = st.columns(2)
            produto = c1.text_input("Nome do produto*")
            ref     = c2.text_input("Referência (ex: BL-001)")

            c3, c4, c5 = st.columns(3)
            quantidade  = c3.number_input("Quantidade (peças)", min_value=1, value=10, step=1)
            prioridade  = c4.selectbox("Prioridade", ["normal", "urgente", "baixa"])
            data_prev   = c5.date_input("Data prevista de entrega",
                                         value=datetime.today() + timedelta(days=14))

            st.subheader("Tecido")
            c6, c7 = st.columns(2)
            tec_opts = {t["nome"]: t for t in tecidos_list}
            tec_nome = c6.selectbox("Tecido", ["(sem tecido)"] + list(tec_opts.keys()))
            metros = c7.number_input("Metros necessários (total)", min_value=0.0, step=0.1, value=0.0)

            custo_tec = 0.0
            if tec_nome != "(sem tecido)" and tec_nome in tec_opts:
                t = tec_opts[tec_nome]
                pm = _calc_preco_metro(t)
                custo_tec = round(pm * metros, 2)
                st.caption(f"Custo tecido: R${pm:.2f}/m × {metros:.1f}m = **R${custo_tec:.2f}** total | R${custo_tec/quantidade:.2f}/peça")

            st.subheader("Costura")
            c8, c9 = st.columns(2)
            cos_opts = {c["nome"]: c for c in costureiras_list}
            cos_nome = c8.selectbox("Costureira", ["(a definir)"] + list(cos_opts.keys()))
            cat_opts = {cp["categoria"]: cp for cp in costura_precos}
            cat_cos  = c9.selectbox("Categoria da peça", list(cat_opts.keys()))

            custo_cos_unit = 0.0
            if cat_cos in cat_opts:
                cp = cat_opts[cat_cos]
                if cos_nome != "(a definir)" and cos_nome in cos_opts:
                    tipo = cos_opts[cos_nome]["tipo"]
                    custo_cos_unit = cp["preco_mae"] if tipo == "mae" else cp["preco_terc"]
                    st.caption(f"Costura ({cos_nome}, {tipo}): **R${custo_cos_unit:.2f}/peça** = R${custo_cos_unit*quantidade:.2f} total")

            st.subheader("Outros custos")
            c10, c11, c12 = st.columns(3)
            custo_corte = c10.number_input("Corte (R$/peça)", min_value=0.0, step=0.5, value=3.0)
            custo_avia  = c11.number_input("Aviamentos (R$/peça)", min_value=0.0, step=0.5, value=8.0)
            custo_emb   = c12.number_input("Embalagem (R$/peça)", min_value=0.0, step=0.5, value=10.0)

            custo_total_unit = (custo_tec / quantidade if quantidade else 0) + custo_cos_unit + custo_corte + custo_avia + custo_emb
            custo_total_total = custo_total_unit * quantidade
            st.success(f"**CMV estimado: R${custo_total_unit:.2f}/peça** (total: R${custo_total_total:.2f})")

            obs = st.text_area("Observações")
            submitted = st.form_submit_button("🚀 Lançar Produção", type="primary")

            if submitted and produto:
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
elif pagina == "💰 Calculadora CMV":
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
#  PÁGINA 6 — CRESCIMENTO
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📈 Crescimento":
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
elif pagina == "📄 Declaração MEI":
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
#  PÁGINA — PRODUTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🧶 Produtos":
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

            edited_p = st.data_editor(
                df_prod,
                use_container_width=True,
                hide_index=True,
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
        with st.form("form_novo_produto"):
            c1, c2 = st.columns(2)
            nome_np = c1.text_input("Nome do produto*")
            colecao_np = c2.text_input("Coleção")

            c3, c4 = st.columns(2)
            custo_tec_np  = c3.number_input("Custo Tecido R$/peça", min_value=0.0, step=0.5)
            custo_cor_np  = c4.number_input("Corte R$/peça", min_value=0.0, step=0.5, value=8.0)

            c5, c6 = st.columns(2)
            custo_cos_np  = c5.number_input("Costura R$/peça", min_value=0.0, step=0.5)
            custo_eti_np  = c6.number_input("Etiquetas R$/peça", min_value=0.0, step=0.1, value=0.2)

            c7, c8 = st.columns(2)
            custo_adic_np = c7.number_input("Acabamentos/Adicional R$/peça", min_value=0.0, step=0.5)
            custo_emb_np  = c8.number_input("Embalagem R$/peça", min_value=0.0, step=0.5, value=10.0)

            c9, c10 = st.columns(2)
            mod_total_np  = c9.number_input("Modelagem total R$", min_value=0.0, step=50.0,
                help="Valor total pago pela modelagem — será dividido pelo lote mínimo")
            lote_np       = c10.number_input("Lote mínimo (peças)", min_value=1, value=10, step=1)
            custo_mod_np  = round(mod_total_np / lote_np, 2) if lote_np else 0

            cmv_np = (custo_tec_np + custo_cor_np + custo_cos_np + custo_eti_np +
                      custo_adic_np + custo_emb_np + custo_mod_np)
            st.info(
                f"CMV estimado: **R${cmv_np:.2f}** | "
                f"Mínimo (2x): R${cmv_np*2:.2f} | "
                f"Ideal (3,5x): R${cmv_np*3.5:.2f}"
            )
            preco_vnd_np = st.number_input("Preço de Venda R$", min_value=0.0, step=5.0)
            obs_np = st.text_area("Observações")

            if st.form_submit_button("✅ Cadastrar", type="primary") and nome_np:
                conn.execute("""
                    INSERT INTO produtos_backbe
                    (nome, colecao, custo_tecido, custo_corte, custo_costura,
                     custo_etiquetas, custo_adicional, custo_embalagem, custo_modelagem,
                     lote_minimo, custo_total, preco_venda, observacoes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (nome_np, colecao_np, custo_tec_np, custo_cor_np, custo_cos_np,
                      custo_eti_np, custo_adic_np, custo_emb_np, custo_mod_np,
                      lote_np, cmv_np, preco_vnd_np, obs_np))
                conn.commit()
                st.success(f"✅ Produto **{nome_np}** cadastrado!")
                st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — ACABAMENTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🔩 Acabamentos":
    st.title("🔩 Peças e Acabamentos")
    st.caption("Cadastre botões, zíperes, elásticos e outros aviamentos. Eles ficam salvos para usar na Calculadora CMV.")

    CATS_ACB = ["botão", "zíper", "elástico", "etiqueta", "forro", "ribana", "viés", "ilhós", "regulagem", "outro"]
    conn = get_conn()

    tab_cat, tab_novo_a = st.tabs(["📋 Catálogo", "➕ Novo Item"])

    with tab_cat:
        acabamentos = rows_to_list(conn.execute(
            "SELECT * FROM acabamentos ORDER BY categoria, nome"
        ).fetchall())

        if not acabamentos:
            st.info("Nenhum acabamento cadastrado ainda. Adicione na aba **➕ Novo Item**.")
        else:
            by_cat = {}
            for a in acabamentos:
                by_cat.setdefault(a["categoria"] or "outro", []).append(a)

            for cat, items in sorted(by_cat.items()):
                with st.expander(f"🔸 **{cat.title()}** — {len(items)} item(s)", expanded=True):
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
                        disabled=["ID"],
                        column_config={
                            "Preço R$": st.column_config.NumberColumn(format="R$%.2f", step=0.1),
                            "Ativo": st.column_config.CheckboxColumn(),
                        },
                        key=f"edit_acab_{cat}"
                    )
                    if st.button(f"💾 Salvar {cat}", key=f"sv_acab_{cat}"):
                        for _, row in edited_a.iterrows():
                            conn.execute(
                                "UPDATE acabamentos SET nome=?, unidade=?, preco=?, observacoes=?, ativo=? WHERE id=?",
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
#  PÁGINA — RELATÓRIO MÃE
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "👩 Relatório Mãe":
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

    tab_pecas_r, tab_resumo_r, tab_hist_r = st.tabs([
        "🧵 Peças Costuradas", "📊 Resumo do Mês", "📅 Histórico"
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
            df_it = pd.DataFrame([{
                "ID": i["id"],
                "Produto": i["produto"],
                "Categoria": i["categoria"] or "",
                "Qtde": int(i["quantidade"]),
                "Preço/peça R$": float(i["preco_unitario"]),
                "Subtotal R$": float(i["subtotal"]),
            } for i in itens_r])

            edited_it = st.data_editor(
                df_it,
                use_container_width=True,
                hide_index=True,
                disabled=["ID", "Subtotal R$"],
                column_config={
                    "Preço/peça R$": st.column_config.NumberColumn(format="R$%.2f", step=0.5),
                    "Subtotal R$":   st.column_config.NumberColumn(format="R$%.2f"),
                    "Qtde":          st.column_config.NumberColumn(step=1, min_value=1),
                },
                key="edit_itens_mae_r"
            )
            c_sv, c_del = st.columns(2)
            if c_sv.button("💾 Salvar alterações", key="sv_itens_mae"):
                for _, row in edited_it.iterrows():
                    sub = int(row["Qtde"]) * float(row["Preço/peça R$"])
                    conn.execute(
                        "UPDATE relatorio_mae_itens SET produto=?, categoria=?, quantidade=?, preco_unitario=?, subtotal=? WHERE id=?",
                        (row["Produto"], row["Categoria"], int(row["Qtde"]),
                         float(row["Preço/peça R$"]), sub, int(row["ID"]))
                    )
                _recalc_relatorio(conn, rel_id)
                conn.commit()
                st.success("✅ Peças salvas!")
                st.rerun()

        st.divider()
        st.subheader("➕ Adicionar peças")
        with st.form("form_add_peca_mae"):
            f1, f2 = st.columns(2)
            prod_r    = f1.text_input("Produto", placeholder="Ex: Calça Itália")
            cat_r     = f2.selectbox("Categoria de costura", list(cat_opts_r.keys()))
            f3, f4    = st.columns(2)
            qtde_r    = f3.number_input("Quantidade de peças", min_value=1, value=10, step=1)
            preco_def = cat_opts_r[cat_r]["preco_mae"] if cat_r in cat_opts_r else 0.0
            preco_r   = f4.number_input("Preço/peça R$ (mãe)", min_value=0.0,
                                        value=float(preco_def), step=0.5)
            if st.form_submit_button("➕ Adicionar", type="primary"):
                if prod_r:
                    sub_r = int(qtde_r) * float(preco_r)
                    conn.execute("""
                        INSERT INTO relatorio_mae_itens
                        (relatorio_id, produto, categoria, quantidade, preco_unitario, subtotal)
                        VALUES (?,?,?,?,?,?)
                    """, (rel_id, prod_r, cat_r, int(qtde_r), float(preco_r), sub_r))
                    _recalc_relatorio(conn, rel_id)
                    conn.commit()
                    st.success(f"✅ {int(qtde_r)}× {prod_r} — R${sub_r:.2f}")
                    st.rerun()

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
            df_h = pd.DataFrame([{
                "Mês/Ano": f"{MESES_R[h['mes']-1]}/{h['ano']}",
                "Peças": h["total_pecas"],
                "Costura R$": h["total_costura"],
                "Comissão R$": h["comissao_valor"],
                "Total R$": h["total_pagar"],
                "Status": "✅ Pago" if h["pago"] else "⏳ Pendente",
            } for h in hist])
            st.dataframe(df_h, use_container_width=True, hide_index=True)
            c_p, c_pen = st.columns(2)
            c_p.metric("Total pago", f"R${sum(h['total_pagar'] for h in hist if h['pago']):.2f}")
            c_pen.metric("Total pendente", f"R${sum(h['total_pagar'] for h in hist if not h['pago']):.2f}")

    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
#  PÁGINA — CALENDÁRIO (datas comerciais/moda + ordens de produção)
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📅 Calendário":

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
<div class="bb-card" style="max-height:520px;overflow-y:auto">
  <div style="font-size:15px;font-weight:700;color:{NAVY};margin-bottom:14px">📅 Próximas datas</div>
""", unsafe_allow_html=True)
        for ev in upcoming:
            tc = TIPO_COLORS[ev["tipo"]]
            du = ev["days_until"]
            dias_label = "🔴 hoje!" if du == 0 else (f"⚠️ {du}d" if du <= 7 else f"{du}d")
            bold = "font-weight:700" if du <= 14 else ""
            st.markdown(f"""
  <div style="display:flex;justify-content:space-between;align-items:center;
              padding:8px 0;border-bottom:1px solid #F7F5F3">
    <div>
      <div style="font-size:12px;font-weight:600;color:{NAVY};{bold}">{ev['nome']}</div>
      <div style="font-size:10px;color:#9CA3AF;margin-top:1px">{ev['d_obj'].strftime('%d/%m/%Y')}</div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
      <span style="background:{tc['bg']};color:{tc['dot']};padding:2px 7px;border-radius:99px;font-size:9px;font-weight:700;text-transform:uppercase">{ev['tipo']}</span>
      <span style="font-size:12px;font-weight:700;color:{NAVY};min-width:38px;text-align:right">{dias_label}</span>
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
                    st.success(f"Salvo! (nota: datas personalizadas são temporárias — serão adicionadas permanentemente em breve)")

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

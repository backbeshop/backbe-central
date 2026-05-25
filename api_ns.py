import os, requests, json, re
from datetime import datetime, timedelta
from collections import defaultdict
import streamlit as st
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NS_TOKEN = os.getenv("NS_TOKEN", "6e1aec8238ada829a792ec2fd64d1a4f825f817b")
NS_STORE  = os.getenv("NS_STORE", "2427782")
BASE_URL  = f"https://api.tiendanube.com/v1/{NS_STORE}"
HEADERS   = {
    "Authentication": f"bearer {NS_TOKEN}",
    "User-Agent": "BackbeDashboard/1.0 (backbeshop@gmail.com)",
    "Content-Type": "application/json",
}

def _get(endpoint, params=None):
    r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=45, verify=False)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_orders():
    all_orders = []
    page = 1
    while True:
        batch = _get("orders", {"per_page": 200, "page": page,
                                 "fields": "id,created_at,total,subtotal,discount,products,customer,payment_details,shipping_address"})
        if not batch:
            break
        all_orders.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return all_orders

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_customers():
    customers = []
    page = 1
    while True:
        batch = _get("customers", {"per_page": 200, "page": page,
                                    "fields": "id,name,email,phone,orders_count,total_spent,created_at,last_order_at"})
        if not batch:
            break
        customers.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return customers

def _name(nm):
    if isinstance(nm, dict):
        return nm.get("pt", nm.get("es", str(nm)))
    return str(nm) if nm else ""

def _base(name):
    name = re.sub(r"\s*\([^)]*\)", "", name)
    name = re.sub(r"\s+Pronta Entrega[a-z]*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+Limitad[oa]", "", name, flags=re.IGNORECASE)
    COLOR = {"preto","branco","marrom","rosa","azul","cinza","verde","vermelho","off","glow",
             "marinho","acetinado","acetinada","courino","listra","xadrez","chumbo","mescla",
             "claro","escuro","bebe","bic","petroleo","militar","lima","ferrugem","vinho","prata"}
    parts = name.split()
    while parts and parts[-1].lower().strip(".,") in COLOR:
        parts.pop()
    return " ".join(parts).strip()

def compute_sales(orders):
    by_product = defaultdict(lambda: {"units": 0, "revenue": 0.0,
                                       "sizes": defaultdict(int), "colors": defaultdict(int),
                                       "months": defaultdict(float)})
    monthly = defaultdict(lambda: {"orders": 0, "units": 0, "revenue": 0.0})

    for o in orders:
        month = o["created_at"][:7]
        monthly[month]["orders"] += 1
        for p in o.get("products", []):
            nm = _name(p.get("name", ""))
            qty = int(p.get("quantity", 1) or 1)
            price = float(p.get("price", 0) or 0)
            if price == 0:
                continue
            variants = p.get("variant_values", []) or []
            size, color = "", ""
            for v in variants:
                if re.match(r"^(PP|P|M|G|GG|XG|34|36|38|40|42|44|Unico)$", str(v), re.IGNORECASE):
                    size = str(v)
                else:
                    color = str(v)
            base = _base(nm)
            by_product[base]["units"] += qty
            by_product[base]["revenue"] += price * qty
            if size:
                by_product[base]["sizes"][size] += qty
            if color:
                by_product[base]["colors"][color] += qty
            by_product[base]["months"][month] += qty
            monthly[month]["units"] += qty
            monthly[month]["revenue"] += price * qty

    prod_list = sorted(
        [{"produto": k, **{kk: (dict(vv) if isinstance(vv, defaultdict) else vv)
                           for kk, vv in v.items()}}
         for k, v in by_product.items()],
        key=lambda x: -x["units"]
    )
    return prod_list, dict(monthly)

def compute_customers(orders):
    cust = defaultdict(lambda: {"name": "", "email": "", "pedidos": 0,
                                 "gasto": 0.0, "primeiro": "", "ultimo": ""})
    for o in orders:
        c = o.get("customer") or {}
        cid = str(c.get("id", "")) if c else ""
        if not cid:
            continue
        total = float(o.get("total", 0) or 0)
        date = o["created_at"][:10]
        cust[cid]["name"] = c.get("name", "")
        cust[cid]["email"] = c.get("email", "")
        cust[cid]["pedidos"] += 1
        cust[cid]["gasto"] += total
        if not cust[cid]["primeiro"] or date < cust[cid]["primeiro"]:
            cust[cid]["primeiro"] = date
        if not cust[cid]["ultimo"] or date > cust[cid]["ultimo"]:
            cust[cid]["ultimo"] = date

    result = []
    today = datetime.today()
    for cid, d in cust.items():
        days_since = (today - datetime.strptime(d["ultimo"], "%Y-%m-%d")).days if d["ultimo"] else 999
        if d["pedidos"] >= 3 and d["gasto"] >= 500:
            seg = "VIP"
        elif days_since <= 60:
            seg = "Ativo"
        elif days_since <= 180:
            seg = "Reativar"
        else:
            seg = "Perdido"
        result.append({"id": cid, "days_since": days_since, "segmento": seg, **d})

    return sorted(result, key=lambda x: -x["gasto"])

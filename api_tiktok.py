"""
TikTok Shop API helper — Backbe Central

Integração com a TikTok Shop Partner API (open-api.tiktokglobalshop.com) para:
  • Listar os produtos já cadastrados no TikTok Shop
  • Subir produtos novos que ainda não existem lá (a partir do catálogo Nuvemshop)
  • Atualizar as quantidades em estoque dos produtos pronta entrega

Assinatura (sign) segue o algoritmo oficial da TikTok Shop (HMAC-SHA256):
  1. Pega todos os query params, exceto `sign` e `access_token`
  2. Ordena as chaves em ordem alfabética e concatena no formato {key}{value}
  3. Prefixa com o `path` da requisição
  4. Se houver body JSON (content-type != multipart), concatena o body
  5. Envolve tudo com o app_secret: {secret}{string}{secret}
  6. HMAC-SHA256(app_secret, string) em hexadecimal

Credenciais via variáveis de ambiente / secrets do Streamlit (ver .env.example):
  TIKTOK_APP_KEY, TIKTOK_APP_SECRET, TIKTOK_ACCESS_TOKEN, TIKTOK_SHOP_CIPHER
Opcionais:
  TIKTOK_SHOP_ID, TIKTOK_WAREHOUSE_ID, TIKTOK_CATEGORY_ID, TIKTOK_BASE_URL, TIKTOK_API_VERSION
"""
import os
import re
import time
import json
import hmac
import hashlib
from collections import defaultdict

import requests

try:  # cache opcional — funciona dentro e fora do Streamlit
    import streamlit as st
    _cache = st.cache_data
except Exception:  # pragma: no cover - fora do Streamlit
    def _cache(*a, **k):
        def _wrap(fn):
            return fn
        return _wrap

# ── Configuração ──────────────────────────────────────────────────────────────
APP_KEY      = os.getenv("TIKTOK_APP_KEY", "")
APP_SECRET   = os.getenv("TIKTOK_APP_SECRET", "")
ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
SHOP_CIPHER  = os.getenv("TIKTOK_SHOP_CIPHER", "")
SHOP_ID      = os.getenv("TIKTOK_SHOP_ID", "")
WAREHOUSE_ID = os.getenv("TIKTOK_WAREHOUSE_ID", "")
CATEGORY_ID  = os.getenv("TIKTOK_CATEGORY_ID", "")
BASE_URL     = os.getenv("TIKTOK_BASE_URL", "https://open-api.tiktokglobalshop.com")
API_VERSION  = os.getenv("TIKTOK_API_VERSION", "202309")


class TikTokError(Exception):
    """Erro retornado pela TikTok Shop API (code != 0) ou de configuração."""


def tiktok_ok() -> bool:
    """True se as credenciais mínimas para chamar a API estão presentes."""
    return all([APP_KEY, APP_SECRET, ACCESS_TOKEN, SHOP_CIPHER])


def missing_credentials() -> list[str]:
    """Lista das variáveis obrigatórias que estão faltando."""
    req = {
        "TIKTOK_APP_KEY": APP_KEY,
        "TIKTOK_APP_SECRET": APP_SECRET,
        "TIKTOK_ACCESS_TOKEN": ACCESS_TOKEN,
        "TIKTOK_SHOP_CIPHER": SHOP_CIPHER,
    }
    return [k for k, v in req.items() if not v]


# ── Assinatura e requisição ───────────────────────────────────────────────────
def _sign(path: str, query: dict, body: str = "") -> str:
    """Calcula a assinatura HMAC-SHA256 exigida pela TikTok Shop API."""
    keys = sorted(k for k in query if k not in ("sign", "access_token"))
    base = path + "".join(f"{k}{query[k]}" for k in keys)
    if body:
        base += body
    base = f"{APP_SECRET}{base}{APP_SECRET}"
    return hmac.new(
        APP_SECRET.encode("utf-8"), base.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _request(method: str, path: str, query: dict = None, body: dict = None,
             with_shop: bool = True, timeout: int = 45) -> dict:
    """
    Executa uma chamada autenticada à TikTok Shop API.
    Retorna o conteúdo de `data`; levanta TikTokError em caso de falha.
    """
    if not tiktok_ok():
        raise TikTokError(
            "Credenciais da TikTok Shop ausentes: "
            + ", ".join(missing_credentials())
        )

    query = dict(query or {})
    query["app_key"]   = APP_KEY
    query["timestamp"] = str(int(time.time()))
    if with_shop and SHOP_CIPHER:
        query["shop_cipher"] = SHOP_CIPHER

    body_str = json.dumps(body, separators=(",", ":")) if body is not None else ""
    query["sign"] = _sign(path, query, body_str)

    headers = {
        "x-tts-access-token": ACCESS_TOKEN,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{path}"
    resp = requests.request(
        method, url, params=query, headers=headers,
        data=body_str if body is not None else None, timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code", 0) != 0:
        raise TikTokError(
            f"{payload.get('code')}: {payload.get('message', 'erro desconhecido')}"
        )
    return payload.get("data", {}) or {}


# ── Leitura: shop, warehouses, produtos ───────────────────────────────────────
@_cache(ttl=3600, show_spinner=False)
def get_authorized_shops() -> list[dict]:
    """Lista as lojas autorizadas (útil para descobrir o shop_cipher/shop_id)."""
    data = _request("GET", f"/authorization/{API_VERSION}/shops", with_shop=False)
    return data.get("shops", [])


@_cache(ttl=3600, show_spinner=False)
def get_warehouses() -> list[dict]:
    """Lista os armazéns (warehouses) da loja. O primeiro costuma ser o de venda."""
    data = _request("GET", f"/logistics/{API_VERSION}/warehouses")
    return data.get("warehouses", [])


def _resolve_warehouse_id() -> str:
    """Resolve o warehouse_id: usa env var ou o primeiro armazém de vendas."""
    if WAREHOUSE_ID:
        return WAREHOUSE_ID
    for w in get_warehouses():
        # SALES_WAREHOUSE é o tipo usado para estoque vendável
        if w.get("type", "").upper().startswith("SALES") or not w.get("type"):
            return w.get("id", "")
    whs = get_warehouses()
    return whs[0]["id"] if whs else ""


@_cache(ttl=900, show_spinner=False)
def fetch_all_tiktok_products(status: str = "ALL") -> list[dict]:
    """
    Busca todos os produtos do TikTok Shop (paginado).
    status: ALL | ACTIVATE | DEACTIVATED | SELLER_DEACTIVATED | DRAFT | ...
    """
    products = []
    page_token = ""
    while True:
        query = {"page_size": "100"}
        if page_token:
            query["page_token"] = page_token
        body = {} if status == "ALL" else {"status": status}
        data = _request(
            "POST", f"/product/{API_VERSION}/products/search",
            query=query, body=body,
        )
        products.extend(data.get("products", []))
        page_token = data.get("next_page_token", "")
        if not page_token:
            break
    return products


# ── Normalização / casamento com a Nuvemshop ──────────────────────────────────
def normalize_name(name: str) -> str:
    """Normaliza um nome de produto para casar Nuvemshop x TikTok."""
    name = (name or "").lower().strip()
    name = re.sub(r"\s*\([^)]*\)", "", name)            # remove parênteses
    name = re.sub(r"[^\w\s]", " ", name, flags=re.UNICODE)  # pontuação
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _tiktok_titles() -> set[str]:
    """Conjunto de títulos normalizados já existentes no TikTok Shop."""
    return {normalize_name(p.get("title", "")) for p in fetch_all_tiktok_products()}


def _is_pronta_entrega(ns_product: dict) -> bool:
    """
    Heurística: 'pronta entrega' = produto com estoque físico disponível.
    Considera pronta entrega se o nome menciona 'pronta entrega' OU se há
    estoque (>0) em alguma variante.
    """
    name = ns_product.get("name", "")
    if isinstance(name, dict):
        name = name.get("pt", "") or next(iter(name.values()), "")
    if "pronta entrega" in str(name).lower():
        return True
    for v in (ns_product.get("variants") or []):
        try:
            if int(v.get("stock") or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _ns_name(ns_product: dict) -> str:
    name = ns_product.get("name", "")
    if isinstance(name, dict):
        return name.get("pt", "") or next(iter(name.values()), "")
    return str(name or "")


def _ns_total_stock(ns_product: dict) -> int:
    total = 0
    variants = ns_product.get("variants") or []
    if variants:
        for v in variants:
            try:
                total += max(0, int(v.get("stock") or 0))
            except (TypeError, ValueError):
                pass
    else:
        try:
            total += max(0, int(ns_product.get("stock") or 0))
        except (TypeError, ValueError):
            pass
    return total


# ── Escrita: inventário e criação de produto ──────────────────────────────────
def update_inventory(product_id: str, skus: list[dict]) -> dict:
    """
    Atualiza a quantidade em estoque de SKUs de um produto.
    skus: [{"id": <sku_id>, "quantity": <int>}]
    """
    warehouse_id = _resolve_warehouse_id()
    if not warehouse_id:
        raise TikTokError("Nenhum warehouse_id disponível para atualizar estoque.")
    body = {
        "skus": [
            {
                "id": s["id"],
                "inventory": [
                    {"warehouse_id": warehouse_id, "quantity": int(s["quantity"])}
                ],
            }
            for s in skus
        ]
    }
    return _request(
        "POST",
        f"/product/{API_VERSION}/products/{product_id}/inventory/update",
        body=body,
    )


def create_product(product: dict) -> dict:
    """
    Cria um produto no TikTok Shop. `product` já deve estar no formato esperado
    pela API (title, description, category_id, package_weight, skus, main_images...).
    Retorna o `data` com o product_id criado.
    """
    return _request("POST", f"/product/{API_VERSION}/products", body=product)


def build_product_payload(ns_product: dict, category_id: str = "",
                          warehouse_id: str = "") -> dict:
    """
    Monta um payload de criação de produto a partir de um produto Nuvemshop.
    Observação: a TikTok Shop exige category_id e (idealmente) imagens já
    enviadas via /product/{ver}/images/upload — aqui montamos a estrutura base
    e deixamos imagens/category configuráveis.
    """
    category_id = category_id or CATEGORY_ID
    warehouse_id = warehouse_id or _resolve_warehouse_id()
    name = _ns_name(ns_product)

    try:
        base_price = float(str(ns_product.get("price") or 0).replace(",", "."))
    except (TypeError, ValueError):
        base_price = 0.0

    skus = []
    for v in (ns_product.get("variants") or []):
        try:
            price = float(str(v.get("price") or base_price).replace(",", "."))
        except (TypeError, ValueError):
            price = base_price
        try:
            qty = max(0, int(v.get("stock") or 0))
        except (TypeError, ValueError):
            qty = 0
        sales_attrs = []
        for val in (v.get("values") or []):
            txt = val.get("pt") if isinstance(val, dict) else str(val)
            if txt:
                sales_attrs.append({"name": "Variação", "value_name": txt})
        skus.append({
            "seller_sku": str(v.get("sku") or v.get("id") or ""),
            "price": {"amount": f"{price:.2f}", "currency": "BRL"},
            "inventory": [{"warehouse_id": warehouse_id, "quantity": qty}],
            "sales_attributes": sales_attrs,
        })

    if not skus:  # produto simples, sem variantes
        skus.append({
            "seller_sku": str(ns_product.get("id") or ""),
            "price": {"amount": f"{base_price:.2f}", "currency": "BRL"},
            "inventory": [{
                "warehouse_id": warehouse_id,
                "quantity": _ns_total_stock(ns_product),
            }],
            "sales_attributes": [],
        })

    description = ns_product.get("description") or name
    if isinstance(description, dict):
        description = description.get("pt", "") or name

    return {
        "title": name[:255],
        "description": f"<p>{description}</p>",
        "category_id": category_id,
        "skus": skus,
        # main_images precisa de URIs já enviadas ao TikTok; preenchido na sync
        "main_images": [],
        "package_weight": {"value": "0.5", "unit": "KILOGRAM"},
    }


# ── Orquestração: plano de sincronização ──────────────────────────────────────
def plan_sync(ns_products: list[dict]) -> dict:
    """
    Compara o catálogo Nuvemshop com o TikTok Shop e devolve um plano (dry-run):
      • novos:           produtos que ainda não existem no TikTok
      • atualizar_estoque: produtos pronta entrega já existentes, com estoque a ajustar
    Não executa nenhuma escrita.
    """
    existing = _tiktok_titles()

    novos = []
    atualizar = []
    for p in ns_products:
        nome = _ns_name(p)
        norm = normalize_name(nome)
        if not norm:
            continue
        if norm not in existing:
            novos.append({
                "nome": nome,
                "variantes": len(p.get("variants") or []),
                "estoque": _ns_total_stock(p),
                "pronta_entrega": _is_pronta_entrega(p),
                "_ns": p,
            })
        elif _is_pronta_entrega(p):
            atualizar.append({
                "nome": nome,
                "estoque": _ns_total_stock(p),
                "_ns": p,
            })

    return {
        "novos": novos,
        "atualizar_estoque": atualizar,
        "total_tiktok": len(existing),
        "total_ns": len(ns_products),
    }


def _index_tiktok_by_title() -> dict[str, dict]:
    """Mapa {titulo_normalizado: produto_tiktok} para casamento rápido."""
    return {
        normalize_name(p.get("title", "")): p
        for p in fetch_all_tiktok_products()
    }


def _ns_variant_qty_by_sku(ns_product: dict) -> dict[str, int]:
    """Mapa {sku: quantidade} das variantes de um produto Nuvemshop."""
    out = {}
    for v in (ns_product.get("variants") or []):
        sku = str(v.get("sku") or "").strip()
        if not sku:
            continue
        try:
            out[sku] = max(0, int(v.get("stock") or 0))
        except (TypeError, ValueError):
            out[sku] = 0
    return out


def apply_inventory_sync(atualizar: list[dict]) -> list[dict]:
    """
    Executa a atualização de estoque dos produtos pronta entrega.
    Casa as variantes Nuvemshop x SKUs TikTok pelo seller_sku.
    Retorna um relatório por produto: {nome, status, detalhe, skus_atualizados}.
    """
    tt_index = _index_tiktok_by_title()
    report = []
    for item in atualizar:
        ns_p = item["_ns"]
        nome = item["nome"]
        tt = tt_index.get(normalize_name(nome))
        if not tt:
            report.append({"nome": nome, "status": "ignorado",
                           "detalhe": "produto não encontrado no TikTok"})
            continue

        ns_by_sku = _ns_variant_qty_by_sku(ns_p)
        skus_update = []
        for sku in tt.get("skus", []):
            seller_sku = str(sku.get("seller_sku") or "").strip()
            if seller_sku and seller_sku in ns_by_sku:
                skus_update.append({"id": sku["id"], "quantity": ns_by_sku[seller_sku]})

        if not skus_update:
            # fallback: produto simples / SKU único recebe o estoque total
            tt_skus = tt.get("skus", [])
            if len(tt_skus) == 1:
                skus_update.append({
                    "id": tt_skus[0]["id"],
                    "quantity": _ns_total_stock(ns_p),
                })

        if not skus_update:
            report.append({"nome": nome, "status": "ignorado",
                           "detalhe": "nenhum SKU correspondente (seller_sku)"})
            continue

        try:
            update_inventory(tt["id"], skus_update)
            report.append({"nome": nome, "status": "ok",
                           "detalhe": f"{len(skus_update)} SKU(s) atualizado(s)",
                           "skus_atualizados": len(skus_update)})
        except Exception as e:  # noqa: BLE001
            report.append({"nome": nome, "status": "erro", "detalhe": str(e)})
    return report


def apply_new_products(novos: list[dict], category_id: str = "") -> list[dict]:
    """
    Tenta criar os produtos novos no TikTok Shop (como rascunho).
    Requer category_id (env TIKTOK_CATEGORY_ID ou argumento). Sem categoria,
    o produto é marcado como 'pendente' para cadastro manual.
    Retorna relatório por produto.
    """
    category_id = category_id or CATEGORY_ID
    report = []
    for item in novos:
        nome = item["nome"]
        if not category_id:
            report.append({"nome": nome, "status": "pendente",
                           "detalhe": "defina TIKTOK_CATEGORY_ID para criação automática"})
            continue
        try:
            payload = build_product_payload(item["_ns"], category_id=category_id)
            data = create_product(payload)
            report.append({"nome": nome, "status": "criado",
                           "detalhe": f"product_id={data.get('product_id', '?')}"})
        except Exception as e:  # noqa: BLE001
            report.append({"nome": nome, "status": "erro", "detalhe": str(e)})
    return report

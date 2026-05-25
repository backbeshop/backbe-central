"""
Notion API helper — Backbe Central
Busca o calendário de conteúdo da semana a partir da estrutura:
  Planejamento de Conteúdo > Calendário - meses > [Mês] > [Conteúdos DD/MM a DD/MM]
"""
import os, requests
from datetime import datetime, timedelta
from functools import lru_cache

NOTION_TOKEN     = os.getenv("NOTION_TOKEN", "")
NOTION_VERSION   = "2022-06-28"
BASE_URL         = "https://api.notion.com/v1"

# ID fixo do banco "Calendário - meses" (descoberto via MCP)
CALENDAR_MONTHS_DB = "362aaf96-7c51-804f-ba23-dc511049f4c1"

DIAS_PT = {
    "segunda": 0, "terça": 1, "terca": 1,
    "quarta": 2, "quinta": 3, "sexta": 4,
    "sábado": 5, "sabado": 5, "domingo": 6,
}

PLATAFORMA_ICON = {
    "Stories": "📸", "Feed": "🖼️", "Reels": "🎬",
    "TikTok": "🎵", "YouTube": "▶️",
}


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def notion_ok() -> bool:
    return bool(NOTION_TOKEN)


def _get(path: str, **kwargs) -> dict:
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), timeout=10, **kwargs)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(),
                      json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def _query_db(db_id: str, filter_body: dict = None) -> list:
    """Query a Notion database. Returns list of page objects."""
    body = {"page_size": 100}
    if filter_body:
        body["filter"] = filter_body
    data = _post(f"/databases/{db_id}/query", body)
    return data.get("results", [])


def _prop(page: dict, key: str) -> str:
    """Extract plain-text value from a Notion page property."""
    props = page.get("properties", {})
    p = props.get(key)
    if not p:
        return ""
    t = p.get("type", "")
    if t == "title":
        return "".join(r["plain_text"] for r in p.get("title", []))
    if t == "rich_text":
        return "".join(r["plain_text"] for r in p.get("rich_text", []))
    if t == "select":
        s = p.get("select")
        return s["name"] if s else ""
    if t == "multi_select":
        return ", ".join(o["name"] for o in p.get("multi_select", []))
    if t == "date":
        d = p.get("date")
        return d["start"] if d else ""
    if t == "status":
        s = p.get("status")
        return s["name"] if s else ""
    if t == "checkbox":
        return "sim" if p.get("checkbox") else "nao"
    return ""


def _get_month_page_id(year: int, month: int) -> str | None:
    """Finds the month page (e.g. 'Maio') in the Calendário - meses database."""
    pages = _query_db(CALENDAR_MONTHS_DB)
    month_names_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março",   4: "Abril",
        5: "Maio",    6: "Junho",     7: "Julho",    8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    target = month_names_pt.get(month, "").lower()
    for p in pages:
        nome = _prop(p, "Nome").lower().strip()
        if nome == target:
            return p["id"]
    return None


def _get_child_databases(page_id: str) -> list[dict]:
    """Get all child database blocks of a page."""
    data = _get(f"/blocks/{page_id}/children", params={"page_size": 100})
    return [
        b for b in data.get("results", [])
        if b.get("type") == "child_database"
    ]


def _week_range(ref_date: datetime) -> tuple[str, str]:
    """Returns (start_label, end_label) for the week containing ref_date."""
    start = ref_date - timedelta(days=ref_date.weekday())  # Monday
    end   = start + timedelta(days=6)
    return start.strftime("%d/%m"), end.strftime("%d/%m")


def _find_week_db(child_dbs: list[dict], ref_date: datetime) -> str | None:
    """Find the database whose title contains dates of the current week."""
    start_str, _ = _week_range(ref_date)
    # Try to match by start date in title (e.g. "Conteúdos 25/05 a 30/05")
    for db in child_dbs:
        title = db.get("child_database", {}).get("title", "")
        if start_str in title or "conteúdos" in title.lower():
            return db["id"]
    # Fallback: return latest database found
    if child_dbs:
        return child_dbs[-1]["id"]
    return None


def get_week_content(ref_date: datetime = None) -> list[dict]:
    """
    Returns the content calendar posts for the week containing ref_date.
    Each item: {titulo, plataforma, dia, status, detalhes, url, dia_num, data_post}
    """
    if not notion_ok():
        return []

    if ref_date is None:
        ref_date = datetime.now()

    try:
        # 1. Find this month's page
        month_page_id = _get_month_page_id(ref_date.year, ref_date.month)
        if not month_page_id:
            return []

        # 2. Get child databases in that month page
        child_dbs = _get_child_databases(month_page_id)
        if not child_dbs:
            return []

        # 3. Find the current week's database
        week_db_id = _find_week_db(child_dbs, ref_date)
        if not week_db_id:
            return []

        # 4. Query posts in that database
        posts_raw = _query_db(week_db_id)

        # 5. Parse and enrich
        week_start = ref_date - timedelta(days=ref_date.weekday())
        posts = []
        for p in posts_raw:
            titulo    = _prop(p, "Conteúdo") or _prop(p, "Nome") or "Sem título"
            plataforma = _prop(p, "Plataforma") or "Feed"
            dia_txt    = _prop(p, "Dia").strip()
            status     = _prop(p, "Status") or "Pendente"
            detalhes   = _prop(p, "Detalhes") or ""
            url        = p.get("url", "")

            # Map weekday name to date
            dia_num = DIAS_PT.get(dia_txt.lower(), None)
            data_post = None
            if dia_num is not None:
                data_post = (week_start + timedelta(days=dia_num)).date()

            posts.append({
                "titulo":     titulo,
                "plataforma": plataforma,
                "icon":       PLATAFORMA_ICON.get(plataforma, "📌"),
                "dia":        dia_txt,
                "dia_num":    dia_num,
                "data_post":  data_post,
                "status":     status,
                "detalhes":   detalhes[:300] if detalhes else "",
                "url":        url,
            })

        return sorted(posts, key=lambda x: (x["dia_num"] or 99))

    except Exception as e:
        return [{"_error": str(e)}]

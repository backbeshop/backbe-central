"""
Gerador de arquivo ICS (iCalendar) para o Backbe Central.
Inclui: datas comerciais/moda/fiscal, ordens de produção e posts do Notion.
O arquivo pode ser importado no Google Calendar, que sincroniza com o celular.
"""
from datetime import datetime, timedelta, date as dt_date
import re


def _sanitize(s: str) -> str:
    """Remove chars that break ICS SUMMARY/DESCRIPTION."""
    return re.sub(r'[\r\n,;\\]', ' ', str(s or "")).strip()


def _ics_date(d) -> str:
    """Format date as YYYYMMDD."""
    if isinstance(d, datetime):
        return d.strftime("%Y%m%d")
    if isinstance(d, dt_date):
        return d.strftime("%Y%m%d")
    return str(d).replace("-", "")


def _ics_datetime(dt: datetime) -> str:
    """Format datetime as YYYYMMDDTHHmmssZ (UTC)."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _uid(prefix: str, key: str) -> str:
    return f"{prefix}-{re.sub(r'[^a-zA-Z0-9]', '', key)}@backbe.central"


def build_ics(
    datas_especiais: list[dict],
    ordens: list[dict],
    notion_posts: list[dict],
    include_producao: bool = True,
    include_conteudo: bool = True,
) -> str:
    """
    Builds a complete ICS string.

    datas_especiais: list of {data: 'YYYY-MM-DD', nome: str, tipo: str}
    ordens: list of production orders with data_entrada, produto, status
    notion_posts: list from notion_api.get_week_content()
    """
    now_str = _ics_datetime(datetime.utcnow())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Backbe Central//PT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Backbe — Calendário",
        "X-WR-TIMEZONE:America/Sao_Paulo",
        "X-WR-CALDESC:Datas comerciais\\, produção e conteúdo Backbe",
    ]

    # ── Datas comerciais / moda / fiscal ──────────────────────────────────────
    TIPO_LABEL = {
        "comercial": "🛍️ Comercial",
        "moda":      "👗 Moda",
        "fiscal":    "📋 Fiscal",
        "feriado":   "🗓️ Feriado",
    }
    for ev in datas_especiais:
        d_str = ev.get("data", "")
        nome  = _sanitize(ev.get("nome", "Evento"))
        tipo  = ev.get("tipo", "comercial")
        label = TIPO_LABEL.get(tipo, tipo.title())
        try:
            d_obj   = datetime.strptime(d_str, "%Y-%m-%d")
            d_next  = d_obj + timedelta(days=1)
            d_fmt   = _ics_date(d_obj)
            d_fmt_n = _ics_date(d_next)
        except ValueError:
            continue

        # Reminder: 3 days before for commercial/moda, 1 day for fiscal
        reminder_days = 3 if tipo in ("comercial", "moda") else 1

        lines += [
            "BEGIN:VEVENT",
            f"UID:{_uid('evt', d_str + nome)}",
            f"DTSTAMP:{now_str}",
            f"DTSTART;VALUE=DATE:{d_fmt}",
            f"DTEND;VALUE=DATE:{d_fmt_n}",
            f"SUMMARY:{label} — {nome}",
            f"DESCRIPTION:Tipo: {tipo}\\nBackbe Central",
            f"CATEGORIES:{label}",
            "BEGIN:VALARM",
            "TRIGGER;RELATED=START:-P" + str(reminder_days) + "D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Lembrete: {nome} em {reminder_days} dia(s)",
            "END:VALARM",
            "END:VEVENT",
        ]

    # ── Ordens de produção ────────────────────────────────────────────────────
    if include_producao:
        for o in ordens:
            try:
                start = datetime.strptime(str(o.get("data_entrada", ""))[:10], "%Y-%m-%d")
            except ValueError:
                start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

            if o.get("data_prevista"):
                try:
                    end = datetime.strptime(str(o["data_prevista"])[:10], "%Y-%m-%d")
                except ValueError:
                    qty = max(1, o.get("quantidade") or 1)
                    end = start + timedelta(days=max(5, (qty // 7) + 5))
            else:
                qty = max(1, o.get("quantidade") or 1)
                end = start + timedelta(days=max(5, (qty // 7) + 5))

            produto  = _sanitize(o.get("produto", "Ordem"))
            status   = _sanitize(o.get("status", ""))
            qty_val  = o.get("quantidade", 1)
            uid_key  = f"prod{o.get('id', produto)}"

            lines += [
                "BEGIN:VEVENT",
                f"UID:{_uid('prod', uid_key)}",
                f"DTSTAMP:{now_str}",
                f"DTSTART;VALUE=DATE:{_ics_date(start)}",
                f"DTEND;VALUE=DATE:{_ics_date(end + timedelta(days=1))}",
                f"SUMMARY:🏭 {produto} ×{qty_val}",
                f"DESCRIPTION:Status: {status}\\nQuantidade: {qty_val}\\nBackbe Central",
                "CATEGORIES:Produção",
                "BEGIN:VALARM",
                "TRIGGER;RELATED=START:-P1D",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Lembrete: {produto} entra em produção amanhã",
                "END:VALARM",
                "END:VEVENT",
            ]

    # ── Posts do Notion ───────────────────────────────────────────────────────
    if include_conteudo:
        for post in notion_posts:
            if post.get("_error"):
                continue
            data_post = post.get("data_post")
            if not data_post:
                continue
            try:
                d_obj   = datetime.combine(data_post, datetime.min.time())
                d_next  = d_obj + timedelta(days=1)
            except Exception:
                continue

            titulo     = _sanitize(post.get("titulo", "Post"))
            plataforma = _sanitize(post.get("plataforma", ""))
            status     = _sanitize(post.get("status", ""))
            icon       = post.get("icon", "📌")

            lines += [
                "BEGIN:VEVENT",
                f"UID:{_uid('notion', str(data_post) + titulo)}",
                f"DTSTAMP:{now_str}",
                f"DTSTART;VALUE=DATE:{_ics_date(d_obj)}",
                f"DTEND;VALUE=DATE:{_ics_date(d_next)}",
                f"SUMMARY:{icon} {plataforma} — {titulo}",
                f"DESCRIPTION:Plataforma: {plataforma}\\nStatus: {status}\\nBackbe Central",
                "CATEGORIES:Conteúdo",
                "BEGIN:VALARM",
                "TRIGGER;RELATED=START:-PT2H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Hoje: {plataforma} — {titulo}",
                "END:VALARM",
                "END:VEVENT",
            ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def gcal_link(nome: str, data_str: str, descricao: str = "") -> str:
    """
    Generates a 'Add to Google Calendar' URL for a single event.
    data_str: 'YYYY-MM-DD'
    """
    from urllib.parse import quote
    try:
        d = datetime.strptime(data_str, "%Y-%m-%d")
        d_next = d + timedelta(days=1)
        dates = f"{_ics_date(d)}/{_ics_date(d_next)}"
    except ValueError:
        return ""
    base = "https://calendar.google.com/calendar/render"
    params = (
        f"?action=TEMPLATE"
        f"&text={quote(nome)}"
        f"&dates={dates}"
        f"&details={quote(descricao or 'Backbe Central')}"
        f"&sf=true&output=xml"
    )
    return base + params

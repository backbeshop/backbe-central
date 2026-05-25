"""
Parser de extratos bancários para calcular receita bruta MEI.
Suporta:
  - Nubank conta corrente PJ/PF (extrato anual/mensal)
  - InfinitePay / CloudWalk (relatório de movimentações)
"""
import re
import unicodedata
from datetime import datetime
from io import BytesIO
import pdfplumber


# ── Meses em português ────────────────────────────────────────────────────────
MESES_PT = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
}

# ── Regex ─────────────────────────────────────────────────────────────────────
# Cabeçalho de dia Nubank: "05 MAI 2025" ou "05 MAI 2025 Total de entradas..."
_RE_DIA_NUBANK = re.compile(
    r"^(\d{2})\s+(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+(\d{4})",
    re.IGNORECASE,
)
# Transação InfinitePay com data: "03 Jun, 2025 00:38 Depósito de vendas ... +172,21"
_RE_TX_INF = re.compile(
    r"^(\d{2})\s+(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ),?\s+(\d{4})\s+(\d{2}:\d{2})\s+(.+)",
    re.IGNORECASE,
)
# Linha só com hora InfinitePay (transação extra no mesmo dia): "00:59 Depósito... +126,78"
_RE_HORA_INF = re.compile(r"^(\d{2}:\d{2})\s+(.+)")

# Valor monetário BR no final da linha: "1.500,00" ou "+172,21" ou "-840,81"
_RE_VALOR_FIM = re.compile(r"\s([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$")

# Remove valor do final para obter só a descrição
_RE_REMOVE_VALOR = re.compile(r"\s+[+-]?\d{1,3}(?:\.\d{3})*,\d{2}\s*$")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _ptdate(day: str, mon: str, year: str) -> str:
    m = MESES_PT.get(mon.lower(), "00")
    return f"{day.zfill(2)}/{m}/{year}"


def _sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _parse_valor(linha: str) -> float | None:
    mv = _RE_VALOR_FIM.search(linha)
    if not mv:
        return None
    try:
        return float(mv.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _classificar_nubank(desc: str) -> str:
    """Classifica transação Nubank pela descrição (valores sempre positivos no extrato)."""
    dl = _sem_acento(desc.lower())
    # Entradas
    if any(k in dl for k in ["recebida", "recebido", "entrada", "credito"]):
        return "entrada"
    # Saídas — inclui pagamentos de fatura/boleto, transferências enviadas, débitos
    if any(k in dl for k in [
        "enviada", "enviado", "saida", "debito",
        "pagamento de", "pagamento efetuado",
        "imposto", "tarifa", "das ", "saque",
    ]):
        return "saida"
    # Default conservador: se não identificou, trata como entrada
    # (o usuário pode desmarcar na tabela)
    return "entrada"


def _classificar_infinitepay(valor: float) -> str:
    """InfinitePay usa sinal no valor (+/-)."""
    return "entrada" if valor >= 0 else "saida"


# ── Parser Nubank ─────────────────────────────────────────────────────────────
_SKIP_NUBANK_EXACT = {
    "saldo do dia", "total de entradas", "total de saidas",
    "tem alguma duvida", "caso a solucao", "extrato gerado",
    "rendimento", "saldo inicial", "saldo final",
    "movimentacoes", "0800", "nubank.com", "atendimento",
}
_SKIP_NUBANK_CONTAINS = [
    "cnpj", "agencia 0001", "01 de janeiro", "31 de dezembro",
]
_SKIP_NUBANK_START = re.compile(
    r"^(agencia|conta:|ip ltda|s\.a\.|banco|de \d{2})", re.I
)


def _parse_nubank(linhas: list[str]) -> list[dict]:
    transacoes = []
    data_atual = None

    for linha in linhas:
        l = linha.strip()
        if not l:
            continue

        # Detecta cabeçalho de dia
        m = _RE_DIA_NUBANK.match(l)
        if m:
            data_atual = _ptdate(m.group(1), m.group(2), m.group(3))
            continue

        if data_atual is None:
            continue

        ll_raw = l.lower()
        ll = _sem_acento(ll_raw)

        # Pula linhas irrelevantes
        if any(ll.startswith(s) or ll == s for s in _SKIP_NUBANK_EXACT):
            continue
        if any(s in ll for s in _SKIP_NUBANK_CONTAINS):
            continue
        if _SKIP_NUBANK_START.match(ll):
            continue

        # Extrai valor do final da linha
        valor = _parse_valor(l)
        if valor is None:
            continue

        # Monta descrição
        desc = _RE_REMOVE_VALOR.sub("", l).strip()
        if len(desc) < 5:
            continue

        tipo = _classificar_nubank(desc)
        transacoes.append({
            "data": data_atual,
            "descricao": desc[:120],
            "valor": abs(valor),
            "tipo": tipo,
        })

    return transacoes


# ── Parser InfinitePay/CloudWalk ──────────────────────────────────────────────
_SKIP_INF = ["central de ajuda", "pagina ", "pag. ", "a central"]


def _parse_infinitepay(linhas: list[str]) -> list[dict]:
    transacoes = []
    data_atual = None

    for linha in linhas:
        l = linha.strip()
        if not l:
            continue

        ll = l.lower()
        if "saldo do dia" in ll or "data hora" in ll:
            continue
        if any(s in ll for s in _SKIP_INF):
            continue

        # Linha com data completa: "DD Mmm, YYYY HH:MM ..."
        m = _RE_TX_INF.match(l)
        if m:
            data_atual = _ptdate(m.group(1), m.group(2), m.group(3))
            valor = _parse_valor(l)
            if valor is not None:
                desc = _RE_REMOVE_VALOR.sub("", m.group(5)).strip()
                transacoes.append({
                    "data": data_atual,
                    "descricao": desc[:120],
                    "valor": abs(valor),
                    "tipo": _classificar_infinitepay(valor),
                })
            continue

        # Linha com só hora (transação extra no mesmo dia): "HH:MM ..."
        if data_atual:
            mh = _RE_HORA_INF.match(l)
            if mh:
                valor = _parse_valor(l)
                if valor is not None:
                    desc = _RE_REMOVE_VALOR.sub("", mh.group(2)).strip()
                    if "saldo do dia" not in desc.lower():
                        transacoes.append({
                            "data": data_atual,
                            "descricao": desc[:120],
                            "valor": abs(valor),
                            "tipo": _classificar_infinitepay(valor),
                        })

    return transacoes


# ── Extração de texto do PDF ──────────────────────────────────────────────────
def _extrair_linhas(pdf_bytes: bytes) -> list[str]:
    linhas = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                linhas.extend(text.split("\n"))
    return linhas


# ── Função pública ────────────────────────────────────────────────────────────
def parse_nubank_pdf(pdf_bytes: bytes, nome_arquivo: str = "") -> dict:
    """
    Faz parse de extrato Nubank (conta corrente PJ/PF) ou relatório InfinitePay.

    Retorna:
        transacoes     : list[{data, descricao, valor, tipo}]
        entradas       : list de entradas
        saidas         : list de saídas
        total_entradas : soma das entradas
        total_saidas   : soma das saídas
        ano_detectado  : ano predominante nas transações
        erros          : list de mensagens de erro
    """
    erros: list[str] = []
    transacoes: list[dict] = []

    try:
        linhas = _extrair_linhas(pdf_bytes)
        texto_top = _sem_acento(" ".join(linhas[:30]).lower())

        if "infinitepay" in texto_top or (
            "cloudwalk" in texto_top and "relatorio" in texto_top
        ):
            transacoes = _parse_infinitepay(linhas)
        else:
            transacoes = _parse_nubank(linhas)

        # Fallback: tenta o outro formato se encontrou menos de 3 transações
        if len(transacoes) < 3:
            alt = (
                _parse_infinitepay(linhas)
                if not transacoes
                else _parse_nubank(linhas)
            )
            if len(alt) > len(transacoes):
                transacoes = alt

    except Exception as e:
        erros.append(f"Erro ao processar PDF: {e}")

    if not transacoes:
        erros.append(
            "Nenhuma transação encontrada. "
            "Verifique se o PDF é um extrato Nubank ou InfinitePay válido."
        )

    # Detecta ano predominante
    anos: list[int] = []
    for t in transacoes:
        if t.get("data"):
            try:
                anos.append(int(t["data"].split("/")[2]))
            except Exception:
                pass
    ano_detectado = max(set(anos), key=anos.count) if anos else datetime.now().year

    entradas = [t for t in transacoes if t["tipo"] == "entrada"]
    saidas = [t for t in transacoes if t["tipo"] == "saida"]

    return {
        "transacoes": transacoes,
        "entradas": entradas,
        "saidas": saidas,
        "total_entradas": sum(t["valor"] for t in entradas),
        "total_saidas": sum(t["valor"] for t in saidas),
        "ano_detectado": ano_detectado,
        "erros": erros,
    }

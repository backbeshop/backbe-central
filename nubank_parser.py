"""
Parser de extratos Nubank (conta corrente PJ/PF) para calcular receita bruta MEI.
Suporta extratos mensais e anuais em PDF.
"""
import re
import pdfplumber
from datetime import datetime
from io import BytesIO


# Regex para valor monetário brasileiro: 1.500,00 ou -1.500,00 ou +1.500,00
_RE_VALOR = re.compile(r"([+-]?\s*[\d]{1,3}(?:\.\d{3})*,\d{2})")

# Regex para data: DD/MM/YYYY ou DD/MM/YY
_RE_DATA = re.compile(r"\b(\d{2}/\d{2}/(?:\d{4}|\d{2}))\b")

# Palavras que indicam entrada (receita)
_PALAVRAS_ENTRADA = [
    "transferência recebida", "pix recebido", "pix enviado para você",
    "depósito", "recebimento", "credito", "crédito", "pagamento recebido",
    "ted recebida", "doc recebido", "recebido", "entrada",
    "nuvemshop", "nuvem shop", "bagy", "mercado pago", "picpay",
    "shopee", "ame digital", "ifood", "stone", "cielo", "pagseguro",
    "getnet", "rede ", "adyen", "stripe",
]

# Palavras que indicam saída (despesa)
_PALAVRAS_SAIDA = [
    "pagamento efetuado", "pix enviado", "transferência enviada",
    "ted enviada", "doc enviado", "débito", "debito", "saque",
    "tarifa", "iof", "das ", "imposto", "fatura", "boleto pago",
]


def _parse_valor(texto: str) -> float | None:
    """Converte string monetária brasileira em float."""
    m = _RE_VALOR.search(texto)
    if not m:
        return None
    s = m.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_data(texto: str) -> str | None:
    """Extrai primeira data DD/MM/YYYY do texto."""
    m = _RE_DATA.search(texto)
    if not m:
        return None
    d = m.group(1)
    if len(d) == 8:  # DD/MM/YY
        d = d[:6] + "20" + d[6:]
    return d


def _classificar(descricao: str, valor: float) -> str:
    """Retorna 'entrada' ou 'saida' baseado na descrição e sinal do valor."""
    desc = descricao.lower()
    if valor > 0:
        return "entrada"
    if valor < 0:
        return "saida"
    # valor == 0 — tenta inferir pela descrição
    for p in _PALAVRAS_ENTRADA:
        if p in desc:
            return "entrada"
    for p in _PALAVRAS_SAIDA:
        if p in desc:
            return "saida"
    return "entrada" if valor >= 0 else "saida"


def _extrair_linhas_pdf(pdf_bytes: bytes) -> list[str]:
    """Extrai todas as linhas de texto do PDF."""
    linhas = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                linhas.extend(text.split("\n"))
    return linhas


def _tentar_tabelas(pdf_bytes: bytes) -> list[dict]:
    """Tenta extrair via tabela estruturada do pdfplumber."""
    transacoes = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    row = [str(c).strip() if c else "" for c in row]
                    texto = " ".join(row)
                    data = _parse_data(texto)
                    valor = _parse_valor(texto)
                    if data and valor is not None:
                        desc = " ".join(
                            c for c in row
                            if c and not _RE_DATA.search(c) and not _RE_VALOR.search(c)
                        ).strip()
                        transacoes.append({
                            "data": data,
                            "descricao": desc or texto[:80],
                            "valor": valor,
                            "tipo": _classificar(desc, valor),
                        })
    return transacoes


def _tentar_texto(linhas: list[str]) -> list[dict]:
    """Faz parse linha por linha quando não há tabelas estruturadas."""
    transacoes = []
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if not linha:
            i += 1
            continue

        data = _parse_data(linha)
        valor = _parse_valor(linha)

        if data and valor is not None:
            # Tudo nesta linha
            desc = re.sub(r"\d{2}/\d{2}/\d{2,4}", "", linha)
            desc = re.sub(_RE_VALOR.pattern, "", desc).strip(" |-+R$")
            transacoes.append({
                "data": data,
                "descricao": desc[:100],
                "valor": valor,
                "tipo": _classificar(desc, valor),
            })
        elif data and i + 1 < len(linhas):
            # Data na linha atual, valor pode estar na próxima
            prox = linhas[i + 1].strip()
            valor2 = _parse_valor(prox)
            if valor2 is not None:
                desc = re.sub(r"\d{2}/\d{2}/\d{2,4}", "", linha).strip()
                transacoes.append({
                    "data": data,
                    "descricao": desc[:100],
                    "valor": valor2,
                    "tipo": _classificar(desc, valor2),
                })
                i += 1
        i += 1
    return transacoes


def parse_nubank_pdf(pdf_bytes: bytes, nome_arquivo: str = "") -> dict:
    """
    Faz parse de um extrato Nubank PDF.
    Retorna dict com:
      - transacoes: list de {data, descricao, valor, tipo}
      - total_entradas: soma das entradas
      - total_saidas: soma das saídas (positivo)
      - ano_detectado: ano mais frequente nas transações
      - erros: list de mensagens de problema
    """
    erros = []
    transacoes = []

    try:
        # Tenta tabelas primeiro (mais preciso)
        transacoes = _tentar_tabelas(pdf_bytes)

        # Se não encontrou nada com tabela, tenta texto
        if len(transacoes) < 3:
            linhas = _extrair_linhas_pdf(pdf_bytes)
            transacoes = _tentar_texto(linhas)

    except Exception as e:
        erros.append(f"Erro ao processar PDF: {e}")

    if not transacoes:
        erros.append("Nenhuma transação encontrada. Verifique se o PDF é um extrato Nubank válido.")

    # Detecta ano predominante
    anos = []
    for t in transacoes:
        if t["data"]:
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
        "total_entradas": sum(abs(t["valor"]) for t in entradas),
        "total_saidas": sum(abs(t["valor"]) for t in saidas),
        "ano_detectado": ano_detectado,
        "erros": erros,
    }

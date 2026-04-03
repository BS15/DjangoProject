"""Pure Python string manipulation and monetary comparison helpers.

No PDFs, no databases — just deterministic data normalization.
"""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal


def _digits_only(value):
    """Retorna apenas dígitos de ``value`` para comparações determinísticas."""
    return re.sub(r"\D", "", value or "")


def normalize_document(value):
    """Normaliza CPF/CNPJ para string numérica sem máscara."""
    return _digits_only(value)


def normalize_account(agencia, conta):
    """Normaliza dados bancários (agência/conta) para comparação segura."""
    agencia_norm = (agencia or "").strip().replace(" ", "")
    conta_norm = (conta or "").strip().replace(" ", "").replace(".", "")
    return agencia_norm.upper(), conta_norm.upper()


def normalize_name_for_match(value):
    """Normaliza nomes removendo acentos e padronizando caixa/espaços."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", value.upper())
    no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", no_accents).strip()


def names_bidirectional_match(left, right):
    """Retorna True quando um nome contém o outro após normalização."""
    left_norm = normalize_name_for_match(left)
    right_norm = normalize_name_for_match(right)
    if not left_norm or not right_norm:
        return False
    return left_norm in right_norm or right_norm in left_norm


def decimals_equal_money(left, right):
    """Compara valores monetários com precisão de centavos."""
    if left is None or right is None:
        return False
    return Decimal(left).quantize(Decimal("0.01")) == Decimal(right).quantize(Decimal("0.01"))


def safe_split(line, keyword, index=1):
    """Divide ``line`` por ``keyword`` e devolve a parte desejada com ``strip`` seguro."""
    parts = line.split(keyword)
    if len(parts) > index:
        return parts[index].strip()
    return ""


def parse_br_date(date_str):
    """Converte data brasileira ``DD/MM/AAAA`` para ``AAAA-MM-DD``."""
    try:
        if not date_str:
            return None
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_text_between(full_text, start_anchor, end_anchor):
    """Extrai texto entre âncoras, com fallback para quebra de linha."""
    try:
        start_idx = full_text.find(start_anchor)
        if start_idx == -1:
            return ""
        start_idx += len(start_anchor)
        end_idx = full_text.find(end_anchor, start_idx)
        if end_idx == -1:
            end_idx = full_text.find("\n", start_idx)
        return full_text[start_idx:end_idx].replace("\n", "").strip()
    except Exception:
        return ""

"""Price parsing and currency conversion. Deterministic; used by the heuristic LLM and as a post-check on model output."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Approximate USD per unit of currency. XOF is pegged to EUR (655.957); others drift, so prices carry observed_at.
USD_PER_UNIT = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "XOF": 1.08 / 655.957,
    "XAF": 1.08 / 655.957,
    "NGN": 1 / 1550.0,
    "GMD": 1 / 69.0,
    "GNF": 1 / 8600.0,
    "MRU": 1 / 40.0,
    "CAD": 0.73,
}

COUNTRY_CURRENCY = {
    "SN": "XOF", "ML": "XOF", "CI": "XOF", "BJ": "XOF", "TG": "XOF", "BF": "XOF", "NE": "XOF",
    "NG": "NGN", "GN": "GNF", "GM": "GMD", "MR": "MRU",
    "FR": "EUR", "IT": "EUR", "BE": "EUR", "NL": "EUR", "ES": "EUR", "GB": "GBP", "US": "USD", "CA": "CAD",
}


def to_usd(amount: float | None, currency: str | None) -> float | None:
    if amount is None or not currency:
        return None
    rate = USD_PER_UNIT.get(currency.upper())
    return round(amount * rate, 2) if rate else None


@dataclass
class ParsedPrice:
    amount: float
    currency: str
    currency_inferred: bool
    unit: str
    evidence: str


NUM = r"(\d{1,3}(?:[  .,]\d{3})+|\d+(?:[.,]\d{1,2})?)\s*(k)?"
UNIT_RE = re.compile(r"(?:/|par|per|le|la|the)?\s*(m(?:è|e)tre|m\b|yard|yd|pi(?:è|e)ce|outfit|tenue|ensemble)", re.I)

PATTERNS = [
    # currency after the number
    (re.compile(NUM + r"\s*(fcfa|f\s?cfa|cfa|francs?|f\b)", re.I), "XOF", False),
    (re.compile(NUM + r"\s*(€|euros?|eur\b)", re.I), "EUR", False),
    (re.compile(NUM + r"\s*(\$|usd|dollars?)", re.I), "USD", False),
    (re.compile(NUM + r"\s*(£|gbp|pounds?)", re.I), "GBP", False),
    (re.compile(NUM + r"\s*(₦|naira|ngn)", re.I), "NGN", False),
    (re.compile(NUM + r"\s*(gnf)", re.I), "GNF", False),
    (re.compile(NUM + r"\s*(dalasis?|gmd)", re.I), "GMD", False),
    # currency before the number
    (re.compile(r"(€)\s*" + NUM, re.I), "EUR", True),
    (re.compile(r"(\$)\s*" + NUM, re.I), "USD", True),
    (re.compile(r"(£)\s*" + NUM, re.I), "GBP", True),
    (re.compile(r"(₦|\bN)\s*" + NUM, re.I), "NGN", True),
    (re.compile(r"(cfa|fcfa)\s*" + NUM, re.I), "XOF", True),
]
BARE_PRICE = re.compile(r"(?:prix|price|à|a|:|=|for|pour)\s*" + NUM + r"(?![\d%])", re.I)


def _to_number(raw: str, k: str | None) -> float | None:
    s = raw.replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        s = re.sub(r"[.,]", "", s)
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if k:
        v *= 1000
    return v


def _unit_after(text: str, end: int) -> str:
    tail = text[end : end + 14]
    m = UNIT_RE.match(tail.strip()) or UNIT_RE.search(tail)
    if not m:
        return "unknown"
    u = m.group(1).lower()
    if u.startswith("m"):
        return "metre"
    if u.startswith("y"):
        return "yard"
    if u.startswith("pi"):
        return "piece"
    return "outfit"


def parse_prices(text: str | None, default_currency: str | None = None) -> list[ParsedPrice]:
    """Find prices in a caption. Amounts under 100 XOF/NGN or over 50M are ignored as noise."""
    if not text:
        return []
    out: list[ParsedPrice] = []
    spans: list[tuple[int, int]] = []
    for pat, currency, currency_first in PATTERNS:
        for m in pat.finditer(text):
            groups = m.groups()
            if currency_first:
                raw, k = groups[1], groups[2]
            else:
                raw, k = groups[0], groups[1]
            amount = _to_number(raw, k)
            if amount is None:
                continue
            if any(a <= m.start() < b or a < m.end() <= b for a, b in spans):
                continue
            if currency in ("XOF", "NGN", "GNF") and amount < 100:
                continue
            if amount > 50_000_000:
                continue
            spans.append((m.start(), m.end()))
            out.append(ParsedPrice(amount, currency, False, _unit_after(text, m.end()), text[max(0, m.start() - 30) : m.end() + 20].strip()))
    if not out and default_currency:
        for m in BARE_PRICE.finditer(text):
            amount = _to_number(m.group(1), m.group(2))
            if amount is None:
                continue
            if default_currency in ("XOF", "NGN") and amount < 1000:
                continue
            if default_currency in ("EUR", "USD", "GBP") and (amount < 5 or amount > 20000):
                continue
            out.append(ParsedPrice(amount, default_currency, True, _unit_after(text, m.end()), text[max(0, m.start() - 30) : m.end() + 20].strip()))
    return out

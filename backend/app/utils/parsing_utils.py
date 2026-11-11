import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

_CURRENCY_WORDS = re.compile(r"\b(usd|eur|gbp|inr|cad|aud|rs|rupees?)\b\.?", re.IGNORECASE)
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})$")
_NAMED_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y",
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d-%b-%Y", "%d-%B-%Y",
)


def parse_amount(value: Any) -> Optional[Decimal]:
    """'$9,834' -> 9834, '9.834,50' -> 9834.50, '(100)' -> -100, 'abc' -> None."""
    if value is None:
        return None
    text = _CURRENCY_WORDS.sub("", str(value)).strip()
    if not text or re.search(r"[A-Za-z]", text):
        return None
    negative = ("(" in text and ")" in text) or bool(re.match(r"^[^\d]*-", text))
    text = re.sub(r"[^\d,.]", "", text)
    if not re.search(r"\d", text):
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):       # 1.234,56
            text = text.replace(".", "").replace(",", ".")
        else:                                        # 1,234.56
            text = text.replace(",", "")
    elif "," in text:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", text):  # 1,234
            text = text.replace(",", "")
        elif re.fullmatch(r"\d+,\d{1,2}", text):     # 12,5
            text = text.replace(",", ".")
        else:
            return None
    if text.count(".") > 1:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):  # 1.234.567
            text = text.replace(".", "")
        else:
            return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def parse_integer(value: Any) -> Optional[int]:
    number = parse_amount(value)
    if number is None or number != number.to_integral_value():
        return None
    return int(number)


def parse_date_candidates(value: Any) -> set[date]:
    """All valid interpretations of a date string. Numeric dd/mm vs mm/dd can yield two."""
    if value is None:
        return set()
    text = re.sub(r"\s+", " ", _ORDINAL.sub("", str(value))).strip()
    if not text:
        return set()

    match = _NUMERIC_DATE.match(text)
    if match:
        a, b, year = int(match[1]), int(match[2]), int(match[3])
        if year < 100:
            year += 2000
        found = set()
        for month, day in ((a, b), (b, a)):
            try:
                found.add(date(year, month, day))
            except ValueError:
                pass
        return found

    for fmt in _NAMED_FORMATS:
        try:
            return {datetime.strptime(text, fmt).date()}
        except ValueError:
            continue
    return set()
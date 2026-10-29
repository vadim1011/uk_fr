"""Извлечение пределов лишения свободы («от X до Y лет») из текста санкции."""
import re

UNITS = {"одного": 1, "одному": 1, "двух": 2, "трех": 3, "трёх": 3, "четырех": 4, "четырёх": 4,
         "пяти": 5, "шести": 6, "семи": 7, "восьми": 8, "девяти": 9, "десяти": 10,
         "одиннадцати": 11, "двенадцати": 12, "тринадцати": 13, "четырнадцати": 14,
         "пятнадцати": 15, "шестнадцати": 16, "семнадцати": 17, "восемнадцати": 18,
         "девятнадцати": 19, "двадцати": 20, "тридцати": 30}
TENS = {"двадцати": 20, "тридцати": 30}


def words_to_number(s):
    """'пятнадцати' -> 15, 'двадцати пяти' -> 25, '8' -> 8. Не распознали -> None."""
    s = s.strip().lower()
    if re.fullmatch(r"\d+", s):
        return int(s)
    total, seen = 0, False
    for tok in s.split():
        if tok in UNITS:
            total += UNITS[tok]
            seen = True
        else:
            return None
    return total if seen else None


_PATTERN = re.compile(
    r"лишени\w+\s+свободы(?:\s+на\s+срок)?(?:\s+от\s+(?P<min>[\w ё]+?))?\s+до\s+(?P<max>[\w ё]+?)\s+(?:лет|года|год)\b",
    re.IGNORECASE)


def parse_prison(text):
    """Возвращает (min_years, max_years) по всем частям статьи; None, если лишения свободы нет."""
    if not text:
        return None, None
    lows, highs = [], []
    for m in _PATTERN.finditer(text):
        hi = words_to_number(m.group("max"))
        lo = words_to_number(m.group("min")) if m.group("min") else None
        if hi is not None:
            highs.append(hi)
            lows.append(lo if lo is not None else 0)
    if not highs:
        return None, None
    return min(lows), max(highs)

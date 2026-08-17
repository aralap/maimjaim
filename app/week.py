from datetime import date, timedelta

WEEKDAY_LABELS = (
    (0, "LUNES"),
    (1, "MARTES"),
    (2, "MIÉRC."),
    (3, "JUEVES"),
    (4, "VIERNES"),
    (5, "SÁBADO"),
    (6, "DOMINGO"),
)


def monday_of(day: date | None = None) -> date:
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def week_end(monday: date) -> date:
    return monday + timedelta(days=6)


def parse_week_start(raw: str | None) -> date:
    if not raw:
        return monday_of()
    return monday_of(date.fromisoformat(raw))


def iso_week_number(monday: date) -> int:
    return monday.isocalendar().week


def weekday_dates(monday: date) -> list[tuple[date, str]]:
    return [(monday + timedelta(days=offset), label) for offset, label in WEEKDAY_LABELS]


def product_short_code(name: str) -> str:
    skip = {"lechuga", "de", "la", "el", "del", "revisada"}
    tokens = [part for part in name.replace("/", " ").split() if part]
    tokens = [token for token in tokens if token.lower() not in skip] or tokens
    word = tokens[-1]
    letters = "".join(ch for ch in word if ch.isalpha())
    if len(letters) <= 2:
        return letters.upper()
    if len(tokens) > 1:
        return "".join(t[0] for t in tokens if t[0].isalpha())[:3].upper()
    return letters[:2].upper()

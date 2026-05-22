import datetime as dt

from dateutil.relativedelta import relativedelta


def advance(rule: str, start: dt.date) -> dt.date:
    if rule == "weekly":
        return start + dt.timedelta(weeks=1)
    if rule == "monthly":
        return start + relativedelta(months=1)
    if rule == "quarterly":
        return start + relativedelta(months=3)
    if rule == "semiannual":
        return start + relativedelta(months=6)
    if rule == "annual":
        return start + relativedelta(years=1)
    raise ValueError(f"Unknown rule: {rule}")


def suffix_for(rule: str, date: dt.date) -> str:
    if rule == "weekly":
        return f"Week of {date.isoformat()}"
    if rule == "monthly":
        return f"{date.strftime('%B')} {date.year}"
    if rule == "quarterly":
        q = (date.month - 1) // 3 + 1
        return f"Q{q} {date.year}"
    if rule == "semiannual":
        h = 1 if date.month <= 6 else 2
        return f"H{h} {date.year}"
    if rule == "annual":
        return f"{date.year}"
    raise ValueError(f"Unknown rule: {rule}")

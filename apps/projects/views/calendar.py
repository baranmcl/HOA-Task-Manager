"""Month-view calendar page for projects."""
import calendar as stdlib_calendar
import datetime as dt

_CAL = stdlib_calendar.Calendar(firstweekday=stdlib_calendar.SUNDAY)


def build_month_grid(year: int, month: int) -> tuple[dt.date, dt.date, list[list[dt.date]]]:
    """Build the 6×7 (sometimes 5×7) date grid for a calendar month view.

    Returns:
        (first_visible_date, last_visible_date, weeks)
        weeks is a list of weeks; each week is a list of 7 dates (Sun-Sat).
        Adjacent-month days are real dates outside the requested month — the
        caller dims them in the template.
    """
    weeks = _CAL.monthdatescalendar(year, month)
    first = weeks[0][0]
    last = weeks[-1][-1]
    return first, last, weeks

"""Pure-function report computations.

compute_completion_report(from_date, to_date) returns:
{
    "from_date": dt.date,
    "to_date": dt.date,
    "summary": {
        "completed": int,
        "total_spent": Decimal,
        "over_budget": int,
        "avg_days_to_complete": int | None,
    },
    "by_category": [
        {"name": str, "count": int, "total_spent": Decimal, "avg_cost": Decimal},
        ...
    ],
}
"""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from apps.projects.models import Project, ProjectStatus

ZERO = Decimal("0")


def compute_completion_report(from_date: dt.date, to_date: dt.date) -> dict:
    qs = (
        Project.instances
        .filter(
            status=ProjectStatus.COMPLETED,
            actual_completion_date__gte=from_date,
            actual_completion_date__lte=to_date,
        )
        .select_related("category")
    )

    total_spent = ZERO
    over_budget = 0
    days_to_complete = []
    by_cat_count = defaultdict(int)
    by_cat_spent = defaultdict(lambda: ZERO)
    cat_names = {}

    completed_count = 0
    for p in qs:
        completed_count += 1
        cost = p.actual_cost if p.actual_cost is not None else ZERO
        total_spent += cost
        if (
            p.budget_amount is not None
            and p.actual_cost is not None
            and p.actual_cost > p.budget_amount
        ):
            over_budget += 1
        delta = (p.actual_completion_date - p.created_at.date()).days
        days_to_complete.append(delta)
        by_cat_count[p.category_id] += 1
        by_cat_spent[p.category_id] += cost
        cat_names[p.category_id] = p.category.name

    avg_days = (
        round(sum(days_to_complete) / len(days_to_complete))
        if days_to_complete else None
    )

    by_category = []
    for cat_id, count in by_cat_count.items():
        spent = by_cat_spent[cat_id]
        avg = (spent / count).quantize(Decimal("1")) if count else ZERO
        by_category.append({
            "name": cat_names[cat_id],
            "count": count,
            "total_spent": spent,
            "avg_cost": avg,
        })
    by_category.sort(key=lambda r: (-r["count"], r["name"]))

    return {
        "from_date": from_date,
        "to_date": to_date,
        "summary": {
            "completed": completed_count,
            "total_spent": total_spent,
            "over_budget": over_budget,
            "avg_days_to_complete": avg_days,
        },
        "by_category": by_category,
    }

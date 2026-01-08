from __future__ import annotations

from .series import clamp_days

# Shared defaults for Prophet UI and bulk updates.
PROPHET_DAY_OPTIONS = (0, 1825, 1095, 730, 365)
PROPHET_DAY_LABELS = {
    0: "All",
    1825: "5 years",
    1095: "3 years",
    730: "2 years",
    365: "1 year",
}
PROPHET_DEFAULT_DAYS = 365
PROPHET_DEFAULT_YEARLY = "true"
PROPHET_DEFAULT_CHANGEPOINT = 0.001
PROPHET_DEFAULT_SEASONALITY = 1.0
PROPHET_DEFAULT_CHANGEPOINT_RANGE = 0.9


def resolve_prophet_defaults(
    selected_days: int | None, max_days: int
) -> dict[str, object]:
    if selected_days in PROPHET_DAY_OPTIONS:
        days_value = selected_days
    else:
        days_value = PROPHET_DEFAULT_DAYS
    days_value = clamp_days(str(days_value), max_days)
    return {
        "days": days_value,
        "yearly": PROPHET_DEFAULT_YEARLY,
        "changepoint": PROPHET_DEFAULT_CHANGEPOINT,
        "seasonality": PROPHET_DEFAULT_SEASONALITY,
        "changepoint_range": PROPHET_DEFAULT_CHANGEPOINT_RANGE,
        "day_options": PROPHET_DAY_OPTIONS,
        "day_labels": PROPHET_DAY_LABELS,
    }

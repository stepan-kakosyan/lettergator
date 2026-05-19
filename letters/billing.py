import calendar
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

RATE_PER_YEAR_USD = Decimal("0.50")
MIN_LONG_SCHEDULE_BALANCE_USD = Decimal("1.00")

# SMS pricing
SMS_BASE_PRICE_USD = Decimal("1.00")
SMS_EXTRA_YEAR_PRICE_USD = Decimal("0.20")


def _replace_year_safely(dt, year):
    try:
        return dt.replace(year=year)
    except ValueError:
        last_day = calendar.monthrange(year, dt.month)[1]
        return dt.replace(year=year, day=last_day)


def long_schedule_cutoff(now=None):
    current_date = (now or timezone.now()).date()
    # Keep this under one full year to hide/disable the 1-year preset too.
    return current_date + timedelta(days=364)


def compute_schedule_cost(delivery_at, now=None):
    current_date = (now or timezone.now()).date()
    delivery_date = delivery_at.date()

    one_year_mark = _replace_year_safely(current_date, current_date.year + 1)
    if delivery_date < one_year_mark:
        return Decimal("0.00")

    years = delivery_date.year - current_date.year
    candidate = _replace_year_safely(current_date, current_date.year + years)
    if candidate < delivery_date:
        years += 1
    return RATE_PER_YEAR_USD * Decimal(years)


def compute_sms_price(scheduled_at, now=None):
    """1 USD base + 0.20 USD per year beyond the first year."""
    current_date = (now or timezone.now()).date()
    delivery_date = scheduled_at.date()

    years = delivery_date.year - current_date.year
    candidate = _replace_year_safely(current_date, current_date.year + years)
    if candidate < delivery_date:
        years += 1
    years = max(years, 1)
    extra_years = max(0, years - 1)
    return SMS_BASE_PRICE_USD + SMS_EXTRA_YEAR_PRICE_USD * Decimal(extra_years)
